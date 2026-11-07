"""Create and verify a privacy-bounded, exact-commit uv source candidate.

This is preparation only. It never creates a tag or GitHub Release.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

# Only version-controlled runtime sources/configuration and directly linked
# operator/QA guides; do not include the full docs tree.
# In particular, never archive tracked personal/sample Excel files in the root.
RUNTIME_PATHS = (
    "app",
    "config",
    "resources",
    "policy",
    "educational_master.ssot.yaml",
    "educational_validation_rules.yaml",
    "policy.yaml",
    "policy_sample.yaml",
    ".python-version",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "CHANGELOG.md",
    "docs/SmartAlloc_GUI_Operator_Guide.fa.md",
    "docs/SmartAlloc_E2E_QA_Checklist.fa.md",
    "docs/SmartAlloc_Dev_QA_Notes.md",
    "run_gui.py",
    "Launch_Matrix3.cmd",
    "Matrix-Personal.cmd",
    "tools/personal_release.py",
    "docs/PERSONAL_RELEASE_GIT_UV.fa.md",
    "tools/ci",
    "tests/infra/test_cli_database_preparation.py",
    "tests/integration/test_build_matrix_school_expansion.py",
    "tests/integration/test_groupcode_runtime_authority.py",
    "tests/test_excel_export_smoke.py",
)
REQUIRED_FILES = {
    "app/main.py",
    "app/ui/main_window.py",
    "app/ui/assets/font_data_vazirmatn.py",
    "app/ui/styles.qss",
    "config/policy.json",
    "resources/translations/ui_texts.json",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "README.md",
    "CHANGELOG.md",
    "docs/SmartAlloc_GUI_Operator_Guide.fa.md",
    "docs/SmartAlloc_E2E_QA_Checklist.fa.md",
    "docs/SmartAlloc_Dev_QA_Notes.md",
    "docs/PERSONAL_RELEASE_GIT_UV.fa.md",
    "tools/personal_release.py",
    "Matrix-Personal.cmd",
    "tests/test_excel_export_smoke.py",
    "tests/infra/test_cli_database_preparation.py",
    "tests/integration/test_build_matrix_school_expansion.py",
    "tests/integration/test_groupcode_runtime_authority.py",
}
SAFE_QUALIFICATION_TESTS = {"tests/infra/test_cli_database_preparation.py", "tests/integration/test_build_matrix_school_expansion.py", "tests/test_excel_export_smoke.py", "tests/integration/test_groupcode_runtime_authority.py"}
REJECTED_EXTENSIONS = {
    ".xlsx", ".xls", ".xlsm", ".csv", ".tsv", ".sqlite", ".db",
    ".pem", ".key", ".p12", ".pfx", ".log", ".zip",
}
REJECTED_NAMES = {".env", "id_rsa", "id_ed25519"}
# These tracked configurations contain center-manager fields. Source qualification
# does NOT constitute an approval to expose them in an official release.
PRIVACY_REVIEW_PATHS = ("config/policy.json", "policy.yaml", "policy_sample.yaml")

# High-confidence, non-exhaustive credential signatures. Never log matched bytes.
CREDENTIAL_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?<![A-Za-z0-9])ghp_[A-Za-z0-9]{36}(?![A-Za-z0-9])"),
    re.compile(rb"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{50,}(?![A-Za-z0-9])"),
    re.compile(rb"(?<![A-Z0-9])AKIA[A-Z0-9]{16}(?![A-Z0-9])"),
)



def validate_version_identity(
    pyproject_bytes: bytes,
    lock_bytes: bytes,
    python_bytes: bytes,
    changelog_bytes: bytes,
    *,
    required_release_version: str | None = None,
) -> tuple[str, str]:
    """Use package metadata as the provisional SSoT; never infer a release from history."""

    project = tomllib.loads(pyproject_bytes.decode("utf-8"))["project"]
    lock = tomllib.loads(lock_bytes.decode("utf-8"))
    version = project.get("version")
    if not isinstance(version, str) or not re.fullmatch(
        r"\d+\.\d+\.\d+(?:[A-Za-z0-9.+-]*)?", version
    ):
        raise RuntimeError("Invalid application package version in pyproject.toml")
    if project.get("name") != "smart-student-allocation":
        raise RuntimeError("Unexpected project identity in pyproject.toml")
    root = [p for p in lock.get("package", []) if p.get("name") == project["name"]]
    if len(root) != 1 or root[0].get("version") != version:
        raise RuntimeError("uv.lock project version disagrees with pyproject.toml")
    if lock.get("requires-python") != project.get("requires-python"):
        raise RuntimeError("uv.lock Python requirement disagrees with pyproject.toml")
    requirement = project.get("requires-python")
    match = (
        re.fullmatch(r">=(0|[1-9]\d*)\.(0|[1-9]\d*)", requirement)
        if isinstance(requirement, str) else None
    )
    if match is None:
        raise RuntimeError("Unsupported requires-python (expected >=major.minor)")
    python_version = python_bytes.decode("utf-8").strip()
    pin = re.fullmatch(
        r"(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?",
        python_version,
    )
    if pin is None:
        raise RuntimeError("Pinned .python-version is missing or ambiguous")
    if (int(pin[1]), int(pin[2])) < (int(match[1]), int(match[2])):
        raise RuntimeError("Pinned .python-version does not satisfy requires-python")
    changelog = changelog_bytes.decode("utf-8")
    if "## [Unreleased]" not in changelog:
        raise RuntimeError("Changelog needs an Unreleased section")
    if required_release_version is not None:
        if required_release_version != version:
            raise RuntimeError("Requested release version differs from package version")
        if not re.search(r"(?m)^## \["
                         + re.escape(version) + r"\]\s+-\s+\d{4}-\d{2}-\d{2}\s*$", changelog):
            raise RuntimeError("Requested release version has no dated changelog entry")
    return version, python_version



def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def _selected_git_blobs(source_sha: str) -> dict[str, str]:
    """Canonical selected-file inventory for the exact checked-out Git commit.

    The tree, not the prepared ZIP/manifest, owns each file's identity.
    """
    if git("rev-parse", "HEAD").decode().strip() != source_sha:
        raise RuntimeError("Checkout HEAD differs from approved source SHA")
    # Compare archive bytes against exact Git *blob objects*, not git-show text
    # streams (which can differ under Windows console newline translation).
    entries = git("ls-tree", "-r", "-z", source_sha, "--", *RUNTIME_PATHS)
    expected_blobs: dict[str, str] = {}
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, kind, object_id = metadata.split(b" ", 2)
        if kind != b"blob" or mode not in {b"100644", b"100755"}:
            raise RuntimeError(f"Unsupported Git tree entry: {path_bytes!r}")
        expected_blobs[path_bytes.decode("utf-8")] = object_id.decode("ascii")
    expected_paths = set(expected_blobs)
    missing = REQUIRED_FILES - expected_paths
    if missing:
        raise RuntimeError(f"Required runtime files missing: {sorted(missing)}")
    forbidden = sorted(
        path for path in expected_paths
        if Path(path).suffix.lower() in REJECTED_EXTENSIONS
        or Path(path).name.casefold() in REJECTED_NAMES
        or Path(path).name.casefold().startswith((".env.", "credentials.", "secret."))
        or path.startswith("/") or "\\" in path or ".." in Path(path).parts
        or (path.startswith("tests/") and path not in SAFE_QUALIFICATION_TESTS)
        or path.startswith(("ci/golden_datasets/", "evidence/"))
    )
    if forbidden:
        raise RuntimeError(f"Unsafe source candidate entries: {forbidden}")

    return expected_blobs


def _build_candidate_in_staging(
    output_dir: Path, *, required_release_version: str | None = None
) -> dict[str, object]:
    """Construct and validate both candidate files before they are visible."""
    source_sha = git("rev-parse", "HEAD").decode().strip()
    expected_blobs = _selected_git_blobs(source_sha)
    expected_paths = set(expected_blobs)

    archive = output_dir / f"matrix-uv-source-{source_sha[:12]}.zip"
    subprocess.run(
        ["git", "archive", "--format=zip", f"--output={archive}", "HEAD",
         "--", *RUNTIME_PATHS],
        check=True,
    )
    with zipfile.ZipFile(archive) as source:
        if source.testzip():
            raise RuntimeError("ZIP CRC verification failed")
        archived_paths = {entry.filename for entry in source.infolist() if not entry.is_dir()}
        if archived_paths != expected_paths:
            raise RuntimeError(
                f"Archive file list mismatch: missing={sorted(expected_paths - archived_paths)}, "
                f"unexpected={sorted(archived_paths - expected_paths)}"
            )
        # Git's immutable tree is the authority for all content, not filenames alone.
        for name in sorted(expected_paths):
            data = source.read(name)
            header = f"blob {len(data)}\0".encode()
            archive_blob = hashlib.sha1(header + data).hexdigest()
            if archive_blob != expected_blobs[name]:
                raise RuntimeError(
                    f"Archive blob differs from reviewed Git tree: {name} "
                    f"(archive {archive_blob}; tree {expected_blobs[name]})"
                )
            if any(pattern.search(data) for pattern in CREDENTIAL_PATTERNS):
                raise RuntimeError(f"Potential credential in archive source: {name}")

    with zipfile.ZipFile(archive) as source:
        pyproject_bytes = source.read("pyproject.toml")
        lock_bytes = source.read("uv.lock")
    with zipfile.ZipFile(archive) as source:
        python_bytes = source.read(".python-version")
        changelog_bytes = source.read("CHANGELOG.md")
    version, python_version = validate_version_identity(
        pyproject_bytes, lock_bytes, python_bytes, changelog_bytes,
        required_release_version=required_release_version,
    )
    manifest = {
        "source_sha": source_sha,
        "candidate_identity": f"{version}+source.{source_sha[:12]}",
        "candidate_package_version_not_official_release": version,
        "python_version": python_version,
        "version_source": "pyproject.toml (checked against uv.lock)",
        "release_version_check": (
            "MATCHED_REQUESTED_VERSION_NOT_PUBLICATION_AUTHORITY"
            if required_release_version else "NOT_REQUESTED"
        ),
        "archive": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "uv_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "python_version_file_sha256": hashlib.sha256(python_bytes).hexdigest(),
        "files_checked_against_git_tree": len(expected_paths),
        "archive_files": sorted(expected_paths),
        "privacy_review_paths": [
            path for path in PRIVACY_REVIEW_PATHS if path in expected_paths
        ],
        "privacy_status": "REVIEW_REQUIRED_BEFORE_PUBLICATION",
        "credential_scan": "HIGH_CONFIDENCE_PASS_NOT_PRIVACY_APPROVAL",
        "publication": "NOT_AUTHORIZED",
    }
    (output_dir / "candidate-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def _promote_staging(staging: Path, destination: Path) -> None:
    """Atomically install a fresh directory without replacing another occupant."""
    if os.name == "nt":
        staging.rename(destination)  # Win32 rename rejects an existing target.
        return
    if sys.platform != "linux":
        raise RuntimeError("Atomic no-replace directory promotion is unsupported")
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as exc:
        raise RuntimeError("Atomic no-replace directory promotion unavailable") from exc
    renameat2.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint
    ]
    renameat2.restype = ctypes.c_int
    # renameat2(AT_FDCWD, source, AT_FDCWD, destination, RENAME_NOREPLACE)
    if renameat2(-100, os.fsencode(staging), -100, os.fsencode(destination), 1) != 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), str(destination))


def build_candidate(
    output_dir: Path, *, required_release_version: str | None = None
) -> dict[str, object]:
    """Promote only a fully verified archive and manifest to a fresh directory."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"Candidate destination already exists: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}.staging-", dir=output_dir.parent
    ) as staging:
        manifest = _build_candidate_in_staging(
            Path(staging), required_release_version=required_release_version
        )
        if output_dir.exists() or output_dir.is_symlink():
            raise FileExistsError(f"Candidate destination became occupied: {output_dir}")
        _promote_staging(Path(staging), output_dir)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--require-release-version",
        help="Check an explicitly supplied version against package/lock/changelog; never publishes",
    )
    args = parser.parse_args()
    print(json.dumps(build_candidate(
        args.output_dir, required_release_version=args.require_release_version
    ), indent=2))


if __name__ == "__main__":
    main()
