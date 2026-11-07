"""No-publication qualification for the Matrix GitHub Release lifecycle."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from tools.ci import github_release as release


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
    _write("pyproject.toml", '[project]\nname = "smart-student-allocation"\n'
           'version = "1.2.3"\nrequires-python = ">=3.11"\n')
    _write("uv.lock", 'version = 1\nrequires-python = ">=3.11"\n'
           '[[package]]\nname = "smart-student-allocation"\n'
           'version = "1.2.3"\nsource = { virtual = "." }\n')
    _write(".python-version", "3.11\n")
    _write("CHANGELOG.md", "# Changelog\n## [Unreleased]\n"
           "## [1.2.3] - 2026-11-07\n- Verified synthetic changes.\n")
    _write("app/main.py", "VERSION = 'synthetic'\n")
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


def test_candidate_archive_and_manifest_checks(tmp_path: Path) -> None:
    home = tmp_path / "prepared" / "candidate"
    home.mkdir(parents=True)
    archive = home / ("matrix-uv-source-" + "a" * 12 + ".zip")
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("app/", b"")
        z.writestr("uv.lock", b"lock")
        z.writestr(".python-version", b"3.11\n")
    def digest(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()
    manifest = {
        "archive": archive.name, "source_sha": "a" * 40,
        "candidate_package_version_not_official_release": "1.2.3",
        "archive_sha256": digest(archive.read_bytes()), "publication": "NOT_AUTHORIZED",
        "privacy_status": "REVIEW_REQUIRED_BEFORE_PUBLICATION",
        "archive_files": [".python-version", "uv.lock"],
        "uv_lock_sha256": digest(b"lock"),
        "python_version_file_sha256": digest(b"3.11\n"),
    }
    (home / "candidate-manifest.json").write_text(json.dumps(manifest))
    path, _ = release.verify_candidate(tmp_path / "prepared", "1.2.3", "a" * 40)
    assert path == archive
    archive.write_bytes(b"tampered")
    with pytest.raises(release.PublicationError, match="checksum"):
        release.verify_candidate(tmp_path / "prepared", "1.2.3", "a" * 40)


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
    monkeypatch.setattr(release, "gh_api", lambda path: {"object": {"sha": "a" * 40}})
    monkeypatch.setattr(release, "gh_optional", lambda path: None)
    with pytest.raises(release.PublicationError, match="already exists"):
        release.check_remote("v1.2.3", "a" * 40, "new")
    release.check_remote("v1.2.3", "a" * 40, "resume-tag-only")
    monkeypatch.setattr(release, "gh_api", lambda path: {"object": {"sha": "b" * 40}})
    with pytest.raises(release.PublicationError, match="exact-source"):
        release.check_remote("v1.2.3", "b" * 40, "resume-tag-only")
    monkeypatch.setattr(release, "gh_api", lambda path: {"object": {"sha": "a" * 40}})
    monkeypatch.setattr(release, "gh_optional", lambda path: {"id": 1})
    with pytest.raises(release.PublicationError, match="Release already exists"):
        release.check_remote("v1.2.3", "a" * 40, "resume-tag-only")
    monkeypatch.setattr(release, "gh_api", lambda path: {"object": {"sha": "b" * 40}})
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
    monkeypatch.setattr(release, "snapshot_risks", lambda x: [])
    monkeypatch.setattr(release, "verify_candidate",
                        lambda *x: (directory / "candidate" / "fake.zip", {}))
    monkeypatch.setattr(release, "sha256", lambda x: "fake")
    monkeypatch.setattr(release, "notes_for", lambda *x: "approved notes")
    monkeypatch.setattr(release, "check_remote", lambda *x: None)
    events: list[str] = []
    monkeypatch.setattr(release, "create_tag", lambda *x: events.append("tag"))
    if verification_fails:
        monkeypatch.setattr(release, "run", lambda *x: b"")
        def fail(*args: object) -> str:
            raise release.PublicationError("synthetic verification failure")
        monkeypatch.setattr(release, "verify_published", fail)
    else:
        def fail_run(*args: str) -> bytes:
            raise release.PublicationError("synthetic permission or network failure")
        monkeypatch.setattr(release, "run", fail_run)
    with pytest.raises(release.PublicationError, match=(
        "RELEASE_CREATED_VERIFICATION_FAILED" if verification_fails else "TAG_ONLY_POSSIBLE"
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
    monkeypatch.setattr(release, "snapshot_risks", lambda x: [])
    monkeypatch.setattr(release, "sha256", lambda x: "fake")
    monkeypatch.setattr(release, "notes_for", lambda *x: "approved notes")
    monkeypatch.setattr(release, "verify_candidate", lambda *x: (
        directory / "candidate" / "fixture.zip", {}))
    monkeypatch.setattr(release, "check_remote", lambda *x: None)

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
    data = b"synthetic selected source candidate"
    asset = candidate / "fixture.zip"
    asset.write_bytes(data)
    checksum = hashlib.sha256(data).hexdigest()
    source_blob = b"this is the entire synthetic Git-tracked README"
    git_oid = hashlib.sha1(
        f"blob {len(source_blob)}\0".encode() + source_blob
    ).hexdigest()
    sha = "a" * 40
    tag = "v1.2.3"
    provenance = {
        "tag": tag,
        "source_sha": sha,
        "archive": asset.name,
        "archive_sha256": checksum,
        "full_source_snapshot_risk_count": 0,
        "preparation_state": "CREATED_BEFORE_PUBLICATION",
    }
    (directory / "release-provenance.json").write_text(json.dumps(provenance))
    notes = (
        f"Matrix v1.2.3\n"
        f"Commit: https://github.com/{release.REPO}/commit/{sha}\n"
        f"Tag: https://github.com/{release.REPO}/tree/{tag}\n"
    )
    (directory / "release-notes.md").write_text(notes)
    link = "https://github.com/rezahh107/Matrix-V3.0/releases/tag/v1.2.3"
    release_record = {
        "tag_name": tag, "target_commitish": sha, "draft": False,
        "prerelease": False, "body": notes, "html_url": link,
        "assets": [{"name": "fixture.zip"}, {"name": "release-provenance.json"}],
    }
    monkeypatch.setattr(release, "checked_identity", lambda *x: tag)
    monkeypatch.setattr(release, "snapshot_risks", lambda x: [])
    monkeypatch.setattr(release, "tree_blobs", lambda: {"README.md": git_oid})
    monkeypatch.setattr(release, "notes_for", lambda *x: notes)
    monkeypatch.setattr(release, "verify_candidate", lambda *x: (asset, {}))
    monkeypatch.setattr(release, "sha256", release.sha256)
    monkeypatch.setattr(release, "check_remote", lambda *x: None)
    monkeypatch.setattr(release, "create_tag", lambda *x: None)
    monkeypatch.setattr(release, "gh_api", lambda *x: release_record)
    monkeypatch.setattr(release, "remote_tag", lambda *x: (True, sha))

    events: list[str] = []

    def fake_command(*args: str) -> bytes:
        assert args[0] == "gh"
        if args[1:3] == ("release", "create"):
            events.append("created")
            return b""
        assert args[1:3] == ("release", "download")
        dest = Path(args[args.index("-D") + 1])
        dest.mkdir(exist_ok=True)
        if "--archive" in args:
            fmt = args[args.index("--archive") + 1]
            if fmt == "zip":
                output = dest / "github-auto-source.zip"
                with zipfile.ZipFile(output, "w") as archive:
                    archive.writestr("Matrix-V3.0-abc/README.md", source_blob)
            else:
                output = dest / "github-auto-source.tar.gz"
                with tarfile.open(output, "w:gz") as archive:
                    member = tarfile.TarInfo("Matrix-V3.0-abc/README.md")
                    member.size = len(source_blob)
                    archive.addfile(member, io.BytesIO(source_blob))
            events.append(f"download-{fmt}")
        else:
            selected = args[args.index("-p") + 1]
            (dest / selected).write_bytes(
                (directory / "release-provenance.json").read_bytes()
                if selected == "release-provenance.json" else asset.read_bytes()
            )
            events.append(f"download-{selected}")
        return b""

    monkeypatch.setattr(release, "run", fake_command)
    release.publish(
        "1.2.3", sha, directory, mode="new",
        publish_confirmation="PUBLISH-v1.2.3",
        rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED",
    )
    assert events == [
        "created", "download-fixture.zip", "download-release-provenance.json",
        "download-zip", "download-tar.gz",
    ]
    events.clear()
    # Tag-only recovery skips tag creation; the same verification still runs.
    release.publish(
        "1.2.3", sha, directory, mode="resume-tag-only",
        publish_confirmation="PUBLISH-v1.2.3",
        rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED",
    )
    assert events == [
        "created", "download-fixture.zip", "download-release-provenance.json",
        "download-zip", "download-tar.gz",
    ]
