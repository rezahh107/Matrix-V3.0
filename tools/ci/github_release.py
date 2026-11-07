"""Owner-gated GitHub Release for a previously reviewed Matrix source commit.

The prepare command never publishes. Live publication is intentionally blocked
when the full GitHub-generated repository archive has unreviewed data-like paths.
Only the dedicated manual GitHub Actions publish job should invoke publish.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.ci.qualify_uv_source import (
    CREDENTIAL_PATTERNS,
    build_candidate,
    validate_version_identity,
)

REPO = "rezahh107/Matrix-V3.0"
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
SOURCE_SHA = re.compile(r"[a-f0-9]{40}\Z")
DATA_EXTENSIONS = {".xls", ".xlsx", ".xlsm", ".csv", ".tsv", ".sqlite", ".db",
                   ".pem", ".key", ".p12", ".pfx", ".env"}
SENSITIVE_NAMES = re.compile(
    r"(^|[/_.-])(private|secret|credentials|student.records?|sabt.profile)([/_.-]|$)",
    re.IGNORECASE,
)


class PublicationError(RuntimeError):
    """A refusal or an accurately reported partial publication failure."""


def run(*args: str, data: bytes | None = None) -> bytes:
    try:
        return subprocess.run(
            args, input=data, capture_output=True, check=True
        ).stdout
    except subprocess.CalledProcessError as exc:
        # Never echo potential secrets returned by external tools.
        raise PublicationError(f"Command failed: {args[0]} {args[1] if len(args) > 1 else ''}"
                               f" (exit {exc.returncode})") from exc


def git(*args: str) -> bytes:
    return run("git", *args)


def checked_identity(version: str, sha: str) -> str:
    if VERSION.fullmatch(version) is None or SOURCE_SHA.fullmatch(sha) is None:
        raise PublicationError("Expected a canonical vMAJOR.MINOR.PATCH and a full lowercase SHA")
    if git("rev-parse", "HEAD").decode().strip() != sha:
        raise PublicationError("Checkout differs from explicitly approved source SHA")
    if git("status", "--porcelain", "--untracked-files=no").strip():
        raise PublicationError("Tracked checkout is dirty; refusing publication")
    actual, _ = validate_version_identity(
        Path("pyproject.toml").read_bytes(), Path("uv.lock").read_bytes(),
        Path(".python-version").read_bytes(), Path("CHANGELOG.md").read_bytes(),
        required_release_version=version,
    )
    if actual != version:
        raise PublicationError("Version differs from package, lock or dated changelog")
    return f"v{version}"


def tree_blobs() -> dict[str, str]:
    """Read the whole Git tree, not the selective CI candidate."""
    objects: dict[str, str] = {}
    for line in git("ls-tree", "-rz", "HEAD").split(b"\0"):
        if not line:
            continue
        meta, name = line.split(b"\t", 1)
        mode, kind, oid = meta.split(b" ")
        path = name.decode("utf-8")
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise PublicationError(f"Unsafe Git snapshot entry type: {path}")
        objects[path] = oid.decode("ascii")
    return objects


def snapshot_risks(objects: dict[str, str]) -> list[str]:
    """No content values are printed or stored in the report."""
    risks: list[str] = []
    for path, oid in sorted(objects.items()):
        leaf = Path(path).name.lower()
        if (Path(path).suffix.lower() in DATA_EXTENSIONS or leaf == ".env"
                or leaf.startswith((".env.", "id_rsa", "id_ed25519"))
                or SENSITIVE_NAMES.search(path)):
            risks.append(path)
            continue
        size = int(git("cat-file", "-s", oid).decode())
        if size > 8_000_000:
            # Large uninspected files must not be silently marked safe.
            risks.append(path)
            continue
        blob = git("cat-file", "blob", oid)
        if any(signature.search(blob) for signature in CREDENTIAL_PATTERNS):
            risks.append(path)
    return risks


def notes_for(version: str, sha: str) -> str:
    text = Path("CHANGELOG.md").read_text(encoding="utf-8")
    headings = list(re.finditer(r"(?m)^## \[([^\]\n]+)\].*$", text))
    sections = [i for i, item in enumerate(headings) if item.group(1) == version]
    if len(sections) != 1:
        raise PublicationError("Missing or repeated version changelog section")
    index = sections[0]
    begin = headings[index].end()
    end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
    section = text[begin:end].strip()
    if not section or re.search(
        r"proposed first|NOT an approved or published release|"
        r"no official tag|public downloadable release|not approved for publication",
        section, re.IGNORECASE,
    ):
        raise PublicationError("Changelog still labels this version an unapproved candidate")
    return (
        f"Matrix personal Windows application v{version}\n\n"
        f"Exact reviewed source: https://github.com/{REPO}/commit/{sha}\n"
        f"Immutable version tag: https://github.com/{REPO}/tree/v{version}\n\n"
        f"Installation/updates: Git + uv, with explicit Matrix-Personal.cmd activation.\n"
        f"GitHub's automatic Source code ZIP/TAR contains the FULL repository tree; "
        f"the attached matrix-uv-source ZIP is selective.\n\n"
        f"## Changes\n{section}\n"
    )


def verify_candidate(directory: Path, version: str, sha: str) -> tuple[Path, dict]:
    manifest_file = directory / "candidate" / "candidate-manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    archive = directory / "candidate" / str(manifest["archive"])
    if (manifest["source_sha"] != sha
            or manifest["candidate_package_version_not_official_release"] != version
            or manifest["publication"] != "NOT_AUTHORIZED"
            or manifest["privacy_status"] != "REVIEW_REQUIRED_BEFORE_PUBLICATION"):
        raise PublicationError("Candidate provenance or review-only status mismatch")
    if archive.name != f"matrix-uv-source-{sha[:12]}.zip":
        raise PublicationError("Unexpected candidate archive name")
    if sha256(archive) != manifest["archive_sha256"]:
        raise PublicationError("Candidate archive checksum mismatch")
    with zipfile.ZipFile(archive) as source:
        if source.testzip():
            raise PublicationError("Candidate archive CRC invalid")
        files = {i.filename for i in source.infolist() if not i.is_dir()}
        if files != set(manifest["archive_files"]):
            raise PublicationError("Candidate manifest does not match archive paths")
        for name, expected in (("uv.lock", "uv_lock_sha256"),
                               (".python-version", "python_version_file_sha256")):
            if hashlib.sha256(source.read(name)).hexdigest() != manifest[expected]:
                raise PublicationError(f"Candidate {name} hash mismatch")
    return archive, manifest


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(version: str, sha: str, directory: Path, *, enforce: bool,
            publish_confirmation: str, rights_confirmation: str) -> None:
    tag = checked_identity(version, sha)
    if directory.exists():
        raise PublicationError("Prepare output must be a fresh directory")
    directory.mkdir(parents=True)
    try:
        objects = tree_blobs()
        risks = snapshot_risks(objects)
        (directory / "public-snapshot-review.json").write_text(
            json.dumps({"source_sha": sha, "tracked_files": len(objects),
                        "blocked_paths": risks, "rights_status": "OWNER_REVIEW_REQUIRED"},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        if enforce:
            if publish_confirmation != f"PUBLISH-{tag}":
                raise PublicationError("Explicit Owner publication confirmation missing")
            if rights_confirmation != "PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED":
                raise PublicationError("Explicit full-source/privacy/rights clearance missing")
            if risks:
                raise PublicationError(
                    "Full public repository source ZIP/TAR has unreviewed data-like paths: "
                    + ", ".join(risks[:20])
                    + (" (more omitted)" if len(risks) > 20 else "")
                )
        notes = notes_for(version, sha)
        (directory / "release-notes.md").write_text(notes, encoding="utf-8")
        build_candidate(directory / "candidate", required_release_version=version)
        archive, candidate = verify_candidate(directory, version, sha)
        provenance = {
            "tag": tag, "source_sha": sha, "version": version,
            "archive": archive.name, "archive_sha256": candidate["archive_sha256"],
            "uv_lock_sha256": candidate["uv_lock_sha256"],
            "python_version": candidate["python_version"],
            "python_version_file_sha256": candidate["python_version_file_sha256"],
            "candidate_files_checked_against_git_tree": candidate["files_checked_against_git_tree"],
            "full_source_snapshot_files_reviewed": len(objects),
            "full_source_snapshot_risk_count": len(risks),
            "publication_method": "EXPLICIT_MANUAL_GITHUB_WORKFLOW_ONLY",
            "preparation_state": "CREATED_BEFORE_PUBLICATION",
        }
        (directory / "release-provenance.json").write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        print(f"PREPARED {tag} {sha}; full-snapshot risky paths={len(risks)}; "
              "NO PUBLICATION")
    except Exception:
        # Keep the bounded privacy review report available when a gate refuses.
        raise


def gh_api(path: str, *, fields: tuple[str, ...] = ()) -> dict:
    argv = ["gh", "api", f"repos/{REPO}/{path}"]
    if fields:
        argv += ["-X", "POST", *fields]
    result = run(*argv)
    return json.loads(result.decode("utf-8"))


def gh_optional(path: str) -> dict | None:
    result = subprocess.run(
        ["gh", "api", f"repos/{REPO}/{path}"],
        capture_output=True, check=False,
    )
    if result.returncode == 0:
        return json.loads(result.stdout.decode("utf-8"))
    if b"HTTP 404" in result.stderr:
        return None
    raise PublicationError("Cannot safely determine remote GitHub state (not a confirmed 404)")


def remote_tag(tag: str) -> tuple[bool, str | None]:
    ref = gh_optional(f"git/ref/tags/{tag}")
    if ref is None:
        return False, None
    if ref.get("object", {}).get("type") != "tag":
        raise PublicationError("Existing tag is not annotated; refusing")
    annotated = gh_api(f"git/tags/{ref['object']['sha']}")
    if annotated.get("tag") != tag or annotated.get("object", {}).get("type") != "commit":
        raise PublicationError("Existing annotated tag is malformed")
    return True, annotated["object"]["sha"]


def check_remote(tag: str, sha: str, mode: str) -> None:
    main = gh_api("git/ref/heads/main")
    if main.get("object", {}).get("sha") != sha:
        raise PublicationError("Remote main advanced or differs from approved source SHA")
    exists, target = remote_tag(tag)
    existing_release = gh_optional(f"releases/tags/{tag}")
    if existing_release is not None:
        raise PublicationError("A Release already exists: never reupload or overwrite assets")
    if mode == "new":
        if exists:
            raise PublicationError("Tag already exists (use explicit tag-only recovery if valid)")
    elif mode == "resume-tag-only":
        if not exists or target != sha:
            raise PublicationError("Tag-only recovery needs an annotated exact-source existing tag")
    else:
        raise PublicationError("Invalid publication/recovery mode")


def create_tag(tag: str, sha: str) -> None:
    item = gh_api("git/tags", fields=(
        "-f", f"tag={tag}", "-f", f"message=Owner-approved Matrix {tag}; source {sha}",
        "-f", f"object={sha}", "-f", "type=commit",
    ))
    # The annotated tag object exists, but has no public ref yet.
    gh_api("git/refs", fields=("-f", f"ref=refs/tags/{tag}", "-f", f"sha={item['sha']}"))
    print(f"TAG_CREATED {tag} -> {sha} (do not force-move; release still pending)")


def verify_full_snapshot(archive: Path, expected: dict[str, str]) -> None:
    records: dict[str, bytes] = {}
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as source:
            if source.testzip():
                raise PublicationError("GitHub source ZIP CRC invalid")
            for entry in source.infolist():
                if entry.is_dir():
                    continue
                name = entry.filename.split("/", 1)[-1]
                if name in records:
                    raise PublicationError("Duplicate file in GitHub automatic source ZIP")
                records[name] = source.read(entry)
    else:
        with tarfile.open(archive, "r:gz") as source:
            for entry in source:
                if entry.isdir():
                    continue
                if not entry.isfile():
                    raise PublicationError("GitHub source TAR has unexpected non-file entry")
                data = source.extractfile(entry)
                if data is None:
                    raise PublicationError("Cannot read GitHub source TAR entry")
                name = entry.name.split("/", 1)[-1]
                if name in records:
                    raise PublicationError("Duplicate file in GitHub automatic source TAR")
                records[name] = data.read()
    if set(records) != set(expected):
        raise PublicationError("GitHub automatic source archive differs from exact Git tree")
    for path, blob in records.items():
        computed = hashlib.sha1(f"blob {len(blob)}\0".encode() + blob).hexdigest()
        if computed != expected[path]:
            raise PublicationError(f"GitHub automatic source blob mismatch: {path}")


def verify_published(tag: str, sha: str, directory: Path) -> str:
    provenance = json.loads((directory / "release-provenance.json").read_text())
    asset = directory / "candidate" / provenance["archive"]
    if sha256(asset) != provenance["archive_sha256"]:
        raise PublicationError("Local release asset checksum changed")
    release = gh_api(f"releases/tags/{tag}")
    expected_names = {asset.name, "release-provenance.json"}
    names = {a["name"] for a in release.get("assets", [])}
    if (release.get("tag_name") != tag or release.get("draft") is not False
            or release.get("prerelease") is not False
            or release.get("target_commitish") != sha
            or names != expected_names
            or f"https://github.com/{REPO}/commit/{sha}" not in release.get("body", "")
            or f"https://github.com/{REPO}/tree/{tag}" not in release.get("body", "")
            or not release.get("html_url", "").endswith(f"/releases/tag/{tag}")):
        raise PublicationError("Published Release identity, body, target or asset list differs")
    exists, target = remote_tag(tag)
    if not exists or target != sha:
        raise PublicationError("Published tag is missing, lightweight or moved")
    with TemporaryDirectory(prefix="matrix-release-verify-") as temp:
        root = Path(temp)
        (root / "assets").mkdir()
        run("gh", "release", "download", tag, "-R", REPO, "-p", asset.name,
            "-D", str(root / "assets"))
        run("gh", "release", "download", tag, "-R", REPO,
            "-p", "release-provenance.json", "-D", str(root / "assets"))
        if (sha256(root / "assets" / asset.name) != provenance["archive_sha256"]
                or (root / "assets" / "release-provenance.json").read_bytes()
                != (directory / "release-provenance.json").read_bytes()):
            raise PublicationError("Downloaded published asset does not match prepared bytes")
        blobs = tree_blobs()
        for fmt in ("zip", "tar.gz"):
            folder = root / fmt.replace(".", "-")
            folder.mkdir()
            run("gh", "release", "download", tag, "-R", REPO, "--archive", fmt,
                "-D", str(folder))
            files = [p for p in folder.iterdir() if p.is_file()]
            if len(files) != 1:
                raise PublicationError("Ambiguous downloaded GitHub source archive")
            verify_full_snapshot(files[0], blobs)
    return release["html_url"]


def publish(version: str, sha: str, directory: Path, *, mode: str,
            publish_confirmation: str, rights_confirmation: str) -> None:
    tag = checked_identity(version, sha)
    if publish_confirmation != f"PUBLISH-{tag}" or rights_confirmation != (
        "PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED"
    ):
        raise PublicationError("Owner confirmation for public publication is missing")
    provenance = json.loads((directory / "release-provenance.json").read_text())
    if provenance.get("tag") != tag or provenance.get("source_sha") != sha:
        raise PublicationError("Prepared release provenance refers to another source")
    if snapshot_risks(tree_blobs()):
        raise PublicationError("Public source snapshot still has unreviewed paths")
    if (provenance.get("full_source_snapshot_risk_count") != 0
            or provenance.get("preparation_state") != "CREATED_BEFORE_PUBLICATION"):
        raise PublicationError("Prepared provenance is not a cleared publication candidate")
    archive, _ = verify_candidate(directory, version, sha)
    if archive.name != provenance["archive"] or sha256(archive) != provenance["archive_sha256"]:
        raise PublicationError("Release asset mismatches provenance")
    if (directory / "release-notes.md").read_text() != notes_for(version, sha):
        raise PublicationError("Release notes changed since preparation")
    check_remote(tag, sha, mode)
    if mode == "new":
        try:
            create_tag(tag, sha)
        except (PublicationError, OSError) as exc:
            raise PublicationError(
                f"TAG_CREATION_UNCERTAIN: inspect refs/tags/{tag} and GitHub Releases "
                "before any retry. Never delete or move a possible tag."
            ) from exc
    # No catch-and-delete: partial visible state must remain inspectable.
    try:
        run("gh", "release", "create", tag, str(archive),
            str(directory / "release-provenance.json"), "-R", REPO,
            "--verify-tag", "--target", sha, "--title", f"Matrix {tag}",
            "--notes-file", str(directory / "release-notes.md"))
    except (PublicationError, OSError) as exc:
        raise PublicationError(
            f"TAG_ONLY_POSSIBLE: {tag} may exist at {sha}; inspect remote tag and "
            "Release before explicit resume-tag-only. No tag deletion or force update."
        ) from exc
    try:
        url = verify_published(tag, sha, directory)
    except Exception as exc:
        raise PublicationError(
            f"RELEASE_CREATED_VERIFICATION_FAILED: {tag}; do not advertise, "
            "overwrite assets or auto-retry. Inspect release and downloaded assets."
        ) from exc
    print("PUBLISHED_AND_VERIFIED", url, sha)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "publish", "verify"))
    parser.add_argument("--version", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--mode", default="new", choices=("new", "resume-tag-only"))
    parser.add_argument("--publish-confirmation", default="")
    parser.add_argument("--rights-confirmation", default="")
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            prepare(args.version, args.sha, args.directory,
                    enforce=not args.audit_only,
                    publish_confirmation=args.publish_confirmation,
                    rights_confirmation=args.rights_confirmation)
        elif args.action == "publish":
            publish(args.version, args.sha, args.directory, mode=args.mode,
                    publish_confirmation=args.publish_confirmation,
                    rights_confirmation=args.rights_confirmation)
        else:
            checked_identity(args.version, args.sha)
            url = verify_published(f"v{args.version}", args.sha, args.directory)
            print("VERIFIED_EXISTING_RELEASE", url)
        return 0
    except (PublicationError, RuntimeError, OSError, ValueError, KeyError,
            zipfile.BadZipFile, tarfile.TarError, json.JSONDecodeError) as exc:
        print(f"GITHUB RELEASE REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
