"""No-publication qualification for the Matrix GitHub Release lifecycle."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
import warnings
import zipfile
from pathlib import Path

import pytest

from tools.ci import github_release as release, qualify_uv_source as candidate_source


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def _write(path: str, contents: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(contents, encoding="utf-8")


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.chdir(tmp_path)
    _git("init", "-b", "main")
    _git("config", "user.name", "Synthetic Release Test")
    _git("config", "user.email", "synthetic@example.invalid")
    # Do not inherit Windows core.autocrlf when creating synthetic Git archives.
    _git("config", "core.autocrlf", "false")
    _write("pyproject.toml", '[project]\nname = "smart-student-allocation"\n'
           'version = "1.2.3"\nrequires-python = ">=3.11"\n')
    _write("uv.lock", 'version = 1\nrequires-python = ">=3.11"\n'
           '[[package]]\nname = "smart-student-allocation"\n'
           'version = "1.2.3"\nsource = { virtual = "." }\n')
    _write(".python-version", "3.11\n")
    _write("CHANGELOG.md", "# Changelog\n## [Unreleased]\n"
           "## [1.2.3] - 2026-11-07\n- Verified synthetic changes.\n")
    _write("app/main.py", "VERSION = 'synthetic'\n")
    for required in sorted(candidate_source.REQUIRED_FILES):
        if not Path(required).exists():
            _write(required, "synthetic source fixture\n")
    for included in candidate_source.RUNTIME_PATHS:
        if not Path(included).exists():
            if included in {"policy", "tools/ci"}:  # directory selections
                _write(f"{included}/synthetic.py", "synthetic source fixture\n")
            else:
                _write(included, "synthetic source fixture\n")
    _git("add", ".")
    _git("commit", "-m", "synthetic fixtures only")
    return _git("rev-parse", "HEAD")


def test_exact_sha_version_lock_and_changelog_gate(checkout: str) -> None:
    assert release.checked_identity("1.2.3", checkout) == "v1.2.3"
    with pytest.raises(release.PublicationError, match="canonical"):
        release.checked_identity("01.2.3", checkout)
    with pytest.raises(release.PublicationError, match="differs"):
        release.checked_identity("1.2.3", "a" * 40)
    with pytest.raises(RuntimeError, match="Requested release version"):
        release.checked_identity("1.2.4", checkout)
    _write("pyproject.toml", Path("pyproject.toml").read_text().replace(
        'version = "1.2.3"', 'version = "9.9.9"'))
    with pytest.raises(release.PublicationError, match="dirty"):
        release.checked_identity("1.2.3", checkout)


def test_manifest_rejects_duplicate_version_and_candidate_words(checkout: str) -> None:
    assert "Verified synthetic changes" in release.notes_for("1.2.3", checkout)
    with pytest.raises(release.PublicationError, match="changelog"):
        release.notes_for("8.8.8", checkout)
    _write("CHANGELOG.md", Path("CHANGELOG.md").read_text()
           + "## [1.2.3] - 2026-11-08\n- Duplicate\n")
    with pytest.raises(release.PublicationError, match="repeated"):
        release.notes_for("1.2.3", checkout)
    _write("CHANGELOG.md", "# Changelog\n## [Unreleased]\n"
           "## [1.2.3] - 2026-11-07\n> Proposed first NOT an approved or published release\n")
    with pytest.raises(release.PublicationError, match="candidate"):
        release.notes_for("1.2.3", checkout)


def test_public_snapshot_detects_tracked_data_and_secret_without_exposing_bytes(
    checkout: str,
) -> None:
    _write("0918.xlsx", "synthetic-student-record")
    _write("test/fixture.csv", "synthetic,only")
    _write("config/secret_token.txt", "PRIVATE-MARKER")
    _write("config/allowed_policy.json", '{"manager":"approved"}')
    _write("app/credential_blob.py", "-----BEGIN PRIVATE KEY-----")
    _git("add", ".")
    _git("commit", "-m", "synthetic unreviewed paths")
    risks = release.snapshot_risks(release.tree_blobs())
    assert "0918.xlsx" in risks
    assert "test/fixture.csv" in risks
    assert "config/secret_token.txt" in risks
    assert "app/credential_blob.py" in risks
    assert "config/allowed_policy.json" not in risks
    assert "synthetic-student-record" not in str(risks)


def test_git_archive_omission_does_not_break_tracked_golden_inputs(
    checkout: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(".gitattributes", "/sample/private.xlsx export-ignore\n")
    _write("sample/private.xlsx", "synthetic unreviewed placeholder")
    _write("sample/reviewed.csv", "id\ns1\n")
    _git("add", ".")
    _git("commit", "-m", "synthetic archive policy")
    objects = release.tree_blobs()
    monkeypatch.setattr(release, "REVIEWED_ARCHIVE_OMISSIONS", {"sample/private.xlsx"})
    monkeypatch.setattr(release, "REVIEWED_SAFE_DATA_BLOBS",
                        {"sample/reviewed.csv": objects["sample/reviewed.csv"]})
    archived = release.public_snapshot_blobs(objects)
    assert "sample/private.xlsx" in objects
    assert "sample/private.xlsx" not in archived
    assert "sample/reviewed.csv" in archived
    assert release.snapshot_risks(archived) == []
    _write(".gitattributes",
           "/sample/private.xlsx export-ignore\n/sample/reviewed.csv export-ignore\n")
    _git("add", ".")
    _git("commit", "-m", "synthetic unreviewed hidden file")
    with pytest.raises(release.PublicationError, match="Unreviewed export-ignore"):
        release.public_snapshot_blobs(release.tree_blobs())


def test_content_changed_or_credential_in_reviewed_csv_fails_closed(
    checkout: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write("sample/reviewed.csv", "id\ns1\n")
    _git("add", ".")
    _git("commit", "-m", "synthetic original CSV")
    original = release.tree_blobs()
    monkeypatch.setattr(release, "REVIEWED_SAFE_DATA_BLOBS",
                        {"sample/reviewed.csv": original["sample/reviewed.csv"]})
    assert "sample/reviewed.csv" not in release.snapshot_risks(original)
    _write("sample/reviewed.csv", "id\ns2\n")
    _git("add", ".")
    _git("commit", "-m", "synthetic modified CSV")
    assert "sample/reviewed.csv" in release.snapshot_risks(release.tree_blobs())
    _write("sample/reviewed.csv", "-----BEGIN PRIVATE KEY-----\n")
    _git("add", ".")
    _git("commit", "-m", "synthetic credential replacement")
    monkeypatch.setattr(release, "REVIEWED_SAFE_DATA_BLOBS",
                        {"sample/reviewed.csv": release.tree_blobs()["sample/reviewed.csv"]})
    assert "sample/reviewed.csv" in release.snapshot_risks(release.tree_blobs())


def test_strict_gate_stops_before_candidate_generation(
    checkout: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write("data/student.xlsx", "synthetic")
    _git("add", ".")
    _git("commit", "-m", "synthetic fixture requiring source clearance")
    sha = _git("rev-parse", "HEAD")

    def never_build(*args: object, **kwargs: object) -> None:
        pytest.fail("Do not build and potentially upload when full snapshot is blocked")

    monkeypatch.setattr(release, "build_candidate", never_build)
    out = tmp_path / "review"
    with pytest.raises(release.PublicationError, match="unreviewed"):
        release.prepare("1.2.3", sha, out, enforce=True,
                        publish_confirmation="PUBLISH-v1.2.3",
                        rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED")
    report = json.loads((out / "public-snapshot-review.json").read_text())
    assert report["blocked_paths"] == ["data/student.xlsx"]
    assert not (out / "candidate").exists()
    with pytest.raises(release.PublicationError, match="fresh"):
        release.prepare("1.2.3", sha, out, enforce=False,
                        publish_confirmation="", rights_confirmation="")


def test_owner_confirmations_mandatory(checkout: str, tmp_path: Path) -> None:
    with pytest.raises(release.PublicationError, match="publication confirmation"):
        release.prepare("1.2.3", checkout, tmp_path / "no-confirm", enforce=True,
                        publish_confirmation="", rights_confirmation="")
    with pytest.raises(release.PublicationError, match="clearance"):
        release.prepare("1.2.3", checkout, tmp_path / "no-rights", enforce=True,
                        publish_confirmation="PUBLISH-v1.2.3",
                        rights_confirmation="")


def _build_synthetic_candidate(checkout: str, root: Path) -> Path:
    candidate_source.build_candidate(root / "candidate", required_release_version="1.2.3")
    return root


def _rewrite_candidate(root: Path, change: str) -> None:
    """Coherently edit both archive and manifest to exercise the trust boundary."""
    manifest_path = root / "candidate" / "candidate-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    archive_path = root / "candidate" / manifest["archive"]
    with zipfile.ZipFile(archive_path) as original:
        entries = [(item.filename, original.read(item)) for item in original.infolist()
                   if not item.is_dir()]
    if change in {"app", "lock", "python"}:
        target = {"app": "app/main.py", "lock": "uv.lock",
                  "python": ".python-version"}[change]
        entries = [(name, contents + b"\nTAMPERED" if name == target else contents)
                   for name, contents in entries]
    elif change == "missing":
        entries = [(name, data) for name, data in entries if name != "app/main.py"]
    elif change == "extra":
        entries.append(("app/unauthorized.py", b"synthetic extra"))
    elif change == "duplicate":
        entries.append(("app/main.py", dict(entries)["app/main.py"]))
    elif change == "unexpected-dir":
        entries.append(("unexpected-path/", b""))
    else:
        raise AssertionError(change)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(archive_path, "w") as output:
            for name, data in entries:
                output.writestr(name, data)
    manifest["archive_files"] = sorted({name for name, _ in entries if not name.endswith("/")})
    if change == "lock":
        manifest["uv_lock_sha256"] = hashlib.sha256(dict(entries)["uv.lock"]).hexdigest()
    if change == "python":
        manifest["python_version_file_sha256"] = hashlib.sha256(
            dict(entries)[".python-version"]).hexdigest()
    manifest["archive_sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    provenance_path = root / "release-provenance.json"
    if provenance_path.exists():
        provenance = json.loads(provenance_path.read_text())
        provenance["archive_sha256"] = manifest["archive_sha256"]
        provenance_path.write_text(json.dumps(provenance))


def test_candidate_archive_and_manifest_checks(checkout: str, tmp_path: Path) -> None:
    root = _build_synthetic_candidate(checkout, tmp_path / "prepared")
    archive, manifest = release.verify_candidate(root, "1.2.3", checkout)
    assert archive.is_file()
    assert manifest["files_checked_against_git_tree"] == len(manifest["archive_files"])
    assert manifest["archive_files"] == sorted(candidate_source._selected_git_blobs(checkout))
    archive.write_bytes(b"tampered")
    with pytest.raises(release.PublicationError, match="checksum"):
        release.verify_candidate(root, "1.2.3", checkout)


@pytest.mark.parametrize("mutation", ["app", "lock", "python", "missing", "extra",
                                     "duplicate", "unexpected-dir"])
def test_consumer_rejects_consistent_but_non_git_candidate(
    checkout: str, tmp_path: Path, mutation: str,
) -> None:
    root = _build_synthetic_candidate(checkout, tmp_path / "prepared")
    assert release.verify_candidate(root, "1.2.3", checkout)[0].exists()
    _rewrite_candidate(root, mutation)
    with pytest.raises(release.PublicationError, match="Git|archive|Duplicate|[Uu]nexpected|mismatch|missing"):
        release.verify_candidate(root, "1.2.3", checkout)


def test_candidate_wrong_approved_head_rejected(checkout: str, tmp_path: Path) -> None:
    root = _build_synthetic_candidate(checkout, tmp_path / "prepared")
    with pytest.raises((release.PublicationError, RuntimeError), match="HEAD|Git|SHA|provenance"):
        release.verify_candidate(root, "1.2.3", "a" * 40)
    with pytest.raises(RuntimeError, match="Checkout HEAD"):
        candidate_source._selected_git_blobs("a" * 40)


def test_publish_integrity_gate_before_any_remote_write(
    checkout: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "prepared"
    release.prepare("1.2.3", checkout, root, enforce=True,
                    publish_confirmation="PUBLISH-v1.2.3",
                    rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED")
    remote: list[str] = []

    def remote_gate(*args: object, **kwargs: object) -> None:
        remote.append("preflight")
        raise release.PublicationError("mock read-only remote preflight stopped")

    monkeypatch.setattr(release, "check_remote", remote_gate)
    monkeypatch.setattr(release, "create_tag", lambda *args: pytest.fail("tag write attempted"))
    original_run = release.run

    def no_remote_run(*args: str, data: bytes | None = None) -> bytes:
        if args[0] != "git":
            pytest.fail("remote write attempted")
        return original_run(*args, data=data)

    monkeypatch.setattr(release, "run", no_remote_run)
    monkeypatch.setattr(release, "gh_api", lambda *args, **kw: pytest.fail("API called"))
    with pytest.raises(release.PublicationError, match="mock read-only remote"):
        release.publish("1.2.3", checkout, root, mode="new",
                        publish_confirmation="PUBLISH-v1.2.3",
                        rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED")
    assert remote == ["preflight"]  # positive proof: valid archive crossed integrity gate

    _rewrite_candidate(root, "app")
    remote.clear()
    with pytest.raises(release.PublicationError, match="Git|blob|mismatch"):
        release.publish("1.2.3", checkout, root, mode="new",
                        publish_confirmation="PUBLISH-v1.2.3",
                        rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED")
    assert remote == []  # tampered archive stopped before any remote preflight/write


def test_github_full_source_zip_and_tar_match_exact_blobs(tmp_path: Path) -> None:
    data = b"source bytes"
    good = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    expected = {"README.md": good}
    path = tmp_path / "source.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("Matrix-V3.0-abc/README.md", data)
    release.verify_full_snapshot(path, expected)
    with pytest.raises(release.PublicationError, match="differs"):
        release.verify_full_snapshot(path, {"wrong.txt": good})
    tar = tmp_path / "source.tar.gz"
    with tarfile.open(tar, "w:gz") as t:
        entry = tarfile.TarInfo("Matrix-V3.0-abc/README.md")
        entry.size = len(data)
        t.addfile(entry, io.BytesIO(data))
    release.verify_full_snapshot(tar, expected)
    with pytest.raises(release.PublicationError, match="blob mismatch"):
        release.verify_full_snapshot(tar, {"README.md": "0" * 40})


def test_existing_release_and_tag_recovery_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(release, "remote_tag", lambda tag: (True, "a" * 40))
    listings: list[dict] = []
    main_sha = {"value": "a" * 40}

    def fake_api(path: str) -> object:
        if path == "releases?per_page=100":
            return listings
        assert path == "git/ref/heads/main"
        return {"object": {"sha": main_sha["value"]}}

    monkeypatch.setattr(release, "gh_api", fake_api)
    with pytest.raises(release.PublicationError, match="Tag already exists"):
        release.check_remote("v1.2.3", "a" * 40, "new")
    release.check_remote("v1.2.3", "a" * 40, "resume-tag-only")
    main_sha["value"] = "b" * 40
    with pytest.raises(release.PublicationError, match="exact-source"):
        release.check_remote("v1.2.3", "b" * 40, "resume-tag-only")
    main_sha["value"] = "a" * 40
    listings.append({"tag_name": "v1.2.3", "draft": True, "id": 101})
    with pytest.raises(release.PublicationError, match="Existing Draft"):
        release.check_remote("v1.2.3", "a" * 40, "resume-tag-only")
    listings.clear()
    main_sha["value"] = "b" * 40
    with pytest.raises(release.PublicationError, match="Remote main advanced"):
        release.check_remote("v1.2.3", "a" * 40, "resume-tag-only")


def test_403_not_treated_as_absent_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(args: list[str], **kw: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(args, 1, b"", b"gh: Forbidden (HTTP 403)")
    monkeypatch.setattr(release.subprocess, "run", fake)
    with pytest.raises(release.PublicationError, match="not a confirmed 404"):
        release.gh_optional("git/ref/tags/v1.2.3")


def _mock_prepared_publish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                           *, verification_fails: bool) -> list[str]:
    directory = tmp_path / "prepared"
    (directory / "candidate").mkdir(parents=True)
    (directory / "release-provenance.json").write_text(
        json.dumps({"tag": "v1.2.3", "source_sha": "a" * 40,
                    "archive": "fake.zip", "archive_sha256": "fake",
                    "full_source_snapshot_risk_count": 0,
                    "preparation_state": "CREATED_BEFORE_PUBLICATION"}))
    (directory / "release-notes.md").write_text("approved notes")
    (directory / "candidate" / "fake.zip").write_bytes(b"fixture")
    monkeypatch.setattr(release, "checked_identity", lambda *x: "v1.2.3")
    monkeypatch.setattr(release, "tree_blobs", lambda: {})
    monkeypatch.setattr(release, "public_snapshot_blobs", lambda objects: objects)
    monkeypatch.setattr(release, "snapshot_risks", lambda x: [])
    monkeypatch.setattr(release, "verify_candidate",
                        lambda *x: (directory / "candidate" / "fake.zip", {}))
    monkeypatch.setattr(release, "sha256", lambda x: "fake")
    monkeypatch.setattr(release, "notes_for", lambda *x: "approved notes")
    monkeypatch.setattr(release, "check_remote", lambda *x: None)
    monkeypatch.setattr(release, "remote_tag", lambda *x: (True, "a" * 40))
    # Hosted ZIP/TAR and asset-byte verification are exercised by the independent
    # lifecycle tests; this regression isolates the existing partial-state behavior.
    monkeypatch.setattr(release, "verify_hosted_archives", lambda *x: None)
    monkeypatch.setattr(release, "verify_draft", lambda *x: (101, {}))
    monkeypatch.setattr(release, "check_publication_preconditions", lambda *x: None)
    events: list[str] = []
    monkeypatch.setattr(release, "create_tag", lambda *x: events.append("tag"))
    if verification_fails:
        monkeypatch.setattr(release, "run", lambda *x: b"")
        def fail(*args: object) -> str:
            raise release.PublicationError("synthetic verification failure")
        monkeypatch.setattr(release, "verify_published", fail)
        monkeypatch.setattr(release, "gh_api", lambda *x, **kw:
                            {"id": 101, "draft": False})
    else:
        def fail_run(*args: str) -> bytes:
            raise release.PublicationError("synthetic draft upload failure")
        monkeypatch.setattr(release, "run", fail_run)
    with pytest.raises(release.PublicationError, match=(
        "PUBLISHED_UNVERIFIED" if verification_fails else "DRAFT_CREATION_UNCERTAIN"
    )):
        release.publish("1.2.3", "a" * 40, directory, mode="new",
                        publish_confirmation="PUBLISH-v1.2.3",
                        rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED")
    return events


@pytest.mark.parametrize("verification_fails", [False, True])
def test_partial_failure_never_moves_tag_or_overwrites_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verification_fails: bool,
) -> None:
    assert _mock_prepared_publish(tmp_path, monkeypatch,
                                  verification_fails=verification_fails) == ["tag"]


def test_version_rejects_non_ascii_numerals(checkout: str) -> None:
    with pytest.raises(release.PublicationError, match="canonical"):
        release.checked_identity("1.۲.3", checkout)


def test_annotated_tag_write_failure_is_reported_as_uncertain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "prepared"
    (directory / "candidate").mkdir(parents=True)
    (directory / "candidate" / "fixture.zip").write_bytes(b"candidate")
    (directory / "release-provenance.json").write_text(
        json.dumps({"tag": "v1.2.3", "source_sha": "a" * 40, "archive": "fixture.zip",
                    "archive_sha256": "fake", "full_source_snapshot_risk_count": 0,
                    "preparation_state": "CREATED_BEFORE_PUBLICATION"}))
    (directory / "release-notes.md").write_text("approved notes")
    monkeypatch.setattr(release, "checked_identity", lambda *x: "v1.2.3")
    monkeypatch.setattr(release, "tree_blobs", lambda: {})
    monkeypatch.setattr(release, "public_snapshot_blobs", lambda objects: objects)
    monkeypatch.setattr(release, "snapshot_risks", lambda x: [])
    monkeypatch.setattr(release, "sha256", lambda x: "fake")
    monkeypatch.setattr(release, "notes_for", lambda *x: "approved notes")
    monkeypatch.setattr(release, "verify_candidate", lambda *x: (
        directory / "candidate" / "fixture.zip", {}))
    monkeypatch.setattr(release, "check_remote", lambda *x: None)
    monkeypatch.setattr(release, "verify_hosted_archives", lambda *x: None)

    def uncertain_tag(*args: str) -> None:
        raise OSError("synthetic API interruption after possibly creating the tag")

    monkeypatch.setattr(release, "create_tag", uncertain_tag)
    with pytest.raises(release.PublicationError, match="TAG_CREATION_UNCERTAIN"):
        release.publish("1.2.3", "a" * 40, directory, mode="new",
                        publish_confirmation="PUBLISH-v1.2.3",
                        rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED")


def test_positive_mocked_publication_and_full_download_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "prepared"
    candidate = directory / "candidate"
    candidate.mkdir(parents=True)
    asset = candidate / "fixture.zip"
    asset.write_bytes(b"synthetic candidate")
    (directory / "release-provenance.json").write_text(json.dumps({
        "tag": "v1.2.3", "source_sha": "a" * 40, "archive": asset.name,
        "archive_sha256": "hash", "preparation_state": "CREATED_BEFORE_PUBLICATION",
        "full_source_snapshot_risk_count": 0,
    }))
    (directory / "release-notes.md").write_text("synthetic approved notes")
    monkeypatch.setattr(release, "checked_identity", lambda *x: "v1.2.3")
    monkeypatch.setattr(release, "snapshot_risks", lambda *x: [])
    monkeypatch.setattr(release, "tree_blobs", lambda: {})
    monkeypatch.setattr(release, "public_snapshot_blobs", lambda objects: objects)
    monkeypatch.setattr(release, "notes_for", lambda *x: "synthetic approved notes")
    monkeypatch.setattr(release, "verify_candidate", lambda *x: (asset, {}))
    monkeypatch.setattr(release, "sha256", lambda *x: "hash")
    monkeypatch.setattr(release, "check_remote", lambda *x: None)
    monkeypatch.setattr(release, "remote_tag", lambda *x: (True, "a" * 40))
    events: list[str] = []
    monkeypatch.setattr(release, "create_tag", lambda *x: events.append("tag"))
    monkeypatch.setattr(release, "verify_hosted_archives",
                        lambda ref, objects: events.append(f"archive:{ref}"))

    def draft(tag: str, sha: str, output: Path) -> tuple[int, dict[str, int]]:
        assert events[-1] == "draft-created"
        events.append("verified-hosted-draft-assets")
        return 101, {}

    monkeypatch.setattr(release, "verify_draft", draft)
    monkeypatch.setattr(release, "check_publication_preconditions",
                        lambda *x: events.append("second-tag-and-draft-check"))

    def api(path: str, *, method: str | None = None, fields: tuple[str, ...] = ()) -> dict:
        assert (path, method, fields) == ("releases/101", "PATCH", ("-F", "draft=false"))
        assert events[-1] == "second-tag-and-draft-check"
        events.append("draft-to-public")
        return {"id": 101, "draft": False}

    monkeypatch.setattr(release, "gh_api", api)
    def gh_run(*args: str) -> bytes:
        assert "--draft" in args and "--verify-tag" in args
        assert args[:3] == ("gh", "release", "create")
        assert events[-1] == "archive:v1.2.3"
        events.append("draft-created")
        return b""

    monkeypatch.setattr(release, "run", gh_run)
    monkeypatch.setattr(release, "verify_published",
                        lambda *x: events.append("post-public-readback") or "verified")
    release.publish("1.2.3", "a" * 40, directory, mode="new",
                    publish_confirmation="PUBLISH-v1.2.3",
                    rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED")
    assert events == [
        "archive:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "tag",
        "archive:v1.2.3", "draft-created", "verified-hosted-draft-assets",
        "second-tag-and-draft-check", "draft-to-public", "post-public-readback",
    ]
