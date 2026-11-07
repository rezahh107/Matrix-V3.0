"""Release lifecycle safety without GitHub writes or real publication."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from tools.ci import github_release as release

TAG = "v1.2.3"
SHA = "a" * 40
README = b"synthetic public full Git source"  # no private records
OID = hashlib.sha1(f"blob {len(README)}\0".encode() + README).hexdigest()
NOTES = (f"Matrix 1.2.3\nhttps://github.com/{release.REPO}/commit/{SHA}\n"
         f"https://github.com/{release.REPO}/tree/{TAG}\n")


class MockGitHub:
    def __init__(self, directory: Path, *, existing_tag: bool = False,
                 existing_release: bool = False, draft: bool = False,
                 stale_main: bool = False, different_target_commitish: object = None,
                 corrupt_format: str = "", wrong_asset: str = "", missing_asset: bool = False,
                 no_permission: bool = False, interrupt_draft: bool = False,
                 interrupt_transition: bool = False, wrong_tag: bool = False,
                 corrupt_ref: str = "", advance_after_draft: bool = False,
                 incomplete_asset_state: bool = False,
                 replace_asset_ids_after_download: bool = False) -> None:
        self.directory = directory
        self.tag = existing_tag
        self.live = existing_release and not draft
        self.draft = existing_release and draft
        self.stale_main = stale_main
        self.target_commitish = different_target_commitish
        self.corrupt_format = corrupt_format
        self.wrong_asset = wrong_asset
        self.missing_asset = missing_asset
        self.no_permission = no_permission
        self.interrupt_draft = interrupt_draft
        self.interrupt_transition = interrupt_transition
        self.wrong_tag = wrong_tag
        self.corrupt_ref = corrupt_ref
        self.advance_after_draft = advance_after_draft
        self.incomplete_asset_state = incomplete_asset_state
        self.replace_asset_ids_after_download = replace_asset_ids_after_download
        self.events: list[str] = []
        self.tags_created = 0
        self.transitions = 0
        self.readbacks = 0

    def assets(self) -> list[dict]:
        archive = self.directory / "candidate" / "fixture.zip"
        records = [archive, self.directory / "release-provenance.json"]
        if self.missing_asset:
            records.pop()
        replacement = (10 if self.replace_asset_ids_after_download and sum(
            1 for event in self.events if event.startswith("get:releases/assets/")
        ) >= 2 else 0)
        return [dict(id=idx + 1 + replacement, name=file.name,
                     state="starter" if self.incomplete_asset_state else "uploaded",
                     size=file.stat().st_size,
                     digest=f"sha256:{release.sha256(file)}")
                for idx, file in enumerate(records)]

    def record(self) -> dict:
        return dict(id=101, tag_name=TAG, name=f"Matrix {TAG}",
                    body=NOTES, draft=self.draft, prerelease=False,
                    target_commitish=self.target_commitish,
                    html_url=f"https://github.com/{release.REPO}/releases/tag/{TAG}",
                    assets=self.assets())

    def gh_api(self, path: str, *, fields: tuple[str, ...] = (),
               method: str | None = None) -> object:
        self.events.append(f"api:{method or 'GET'}:{path}")
        if self.no_permission:
            raise release.PublicationError("HTTP 403 insufficient permissions")
        if path == "git/ref/heads/main":
            return {"object": {"sha": "b" * 40 if self.stale_main else SHA}}
        if path == "releases?per_page=100":
            return [self.record()] if self.live or self.draft else []
        if path == f"releases/tags/{TAG}":
            return self.record()
        if path == "releases/101" and method == "PATCH":
            assert fields == ("-F", "draft=false")
            self.transitions += 1
            if self.interrupt_transition:
                raise release.PublicationError("synthetic interrupted PATCH")
            if not self.draft or self.live:
                raise AssertionError("Unverified/duplicate publication")
            self.draft = False
            self.live = True
            return self.record()
        raise AssertionError(f"Unexpected API call: {path} {method}")

    def remote_tag(self, tag: str) -> tuple[bool, str | None]:
        assert tag == TAG
        self.events.append("tag-read")
        return self.tag, "b" * 40 if self.wrong_tag else SHA if self.tag else None

    def create_tag(self, tag: str, sha: str) -> None:
        assert (tag, sha) == (TAG, SHA)
        if self.tag:
            raise AssertionError("Tag overwriting attempted")
        self.tags_created += 1
        self.tag = True
        self.events.append("tag-created")

    def download_hosted(self, path: str, destination: Path, *, accept: str) -> None:
        self.events.append(f"get:{path}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path.startswith("releases/assets/"):
            assert self.draft and not self.live
            idx = int(path.rsplit("/", 1)[-1]) - 1
            filename = self.assets()[idx]["name"]
            source = (self.directory / "candidate" / filename if filename == "fixture.zip"
                      else self.directory / filename)
            content = source.read_bytes()
            if filename == self.wrong_asset:
                content += b"CORRUPTED on hosted server"
            destination.write_bytes(content)
            return
        assert path.startswith(("zipball/", "tarball/"))
        is_tar = path.startswith("tarball/")
        assert accept == "application/vnd.github+json"
        reference = path.split("/", 1)[1]
        assert reference in (SHA, TAG)
        payload = (b"wrong source bytes" if self.corrupt_format == (
            "tar" if is_tar else "zip") and (
                not self.corrupt_ref or self.corrupt_ref == reference
            ) else README)
        if is_tar:
            with tarfile.open(destination, "w:gz") as t:
                item = tarfile.TarInfo("Matrix-synthetic/README.md")
                item.size = len(payload)
                t.addfile(item, io.BytesIO(payload))
        else:
            with zipfile.ZipFile(destination, "w") as z:
                z.writestr("Matrix-synthetic/README.md", payload)

    def run(self, *args: str, data: bytes | None = None) -> bytes:
        assert args[:2] == ("gh", "release")
        if args[2] == "create":
            assert "--draft" in args and "--verify-tag" in args
            assert not self.live and not self.draft
            assert self.tag
            self.events.append("draft-create")
            self.draft = True
            if self.advance_after_draft:
                self.stale_main = True
            if self.interrupt_draft:
                raise release.PublicationError("synthetic interrupted upload")
            return b"draft-created"
        if args[2] == "download":
            assert self.live and not self.draft  # post-publish readback only
            destination = Path(args[args.index("-D")+1])
            destination.mkdir(parents=True, exist_ok=True)
            if "--archive" in args:
                fmt = args[args.index("--archive")+1]
                self.download_hosted(("zipball/" if fmt == "zip" else "tarball/") + TAG,
                                     destination / f"source.{fmt}",
                                     accept="application/vnd.github+json")
            else:
                name = args[args.index("-p")+1]
                source = (self.directory / "candidate" / name if name == "fixture.zip"
                          else self.directory / name)
                (destination / name).write_bytes(source.read_bytes())
            self.readbacks += 1
            return b""
        raise AssertionError("Unrecognized gh operation")


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, MockGitHub]:
    directory = tmp_path / "prepared"
    candidate = directory / "candidate"
    candidate.mkdir(parents=True)
    file = candidate / "fixture.zip"
    file.write_bytes(b"verified selective synthetic archive")
    record = {
        "tag": TAG, "source_sha": SHA, "archive": file.name,
        "archive_sha256": release.sha256(file),
        "full_source_snapshot_risk_count": 0,
        "preparation_state": "CREATED_BEFORE_PUBLICATION",
    }
    (directory / "release-provenance.json").write_text(json.dumps(record))
    (directory / "release-notes.md").write_text(NOTES)
    mock = MockGitHub(directory)
    monkeypatch.setattr(release, "checked_identity", lambda *args: TAG)
    monkeypatch.setattr(release, "notes_for", lambda *args: NOTES)
    monkeypatch.setattr(release, "verify_candidate", lambda *args: (file, {}))
    monkeypatch.setattr(release, "snapshot_risks", lambda objects: [])
    monkeypatch.setattr(release, "tree_blobs", lambda: {"README.md": OID})
    monkeypatch.setattr(release, "public_snapshot_blobs", lambda objects: objects)
    monkeypatch.setattr(release, "gh_api", mock.gh_api)
    monkeypatch.setattr(release, "remote_tag", mock.remote_tag)
    monkeypatch.setattr(release, "create_tag", mock.create_tag)
    monkeypatch.setattr(release, "download_hosted", mock.download_hosted)
    monkeypatch.setattr(release, "run", mock.run)
    return directory, mock


def publish(directory: Path, *, mode: str = "new") -> None:
    release.publish("1.2.3", SHA, directory, mode=mode,
                    publish_confirmation=f"PUBLISH-{TAG}",
                    rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED")


def test_success_draft_assets_and_archives_verified_before_only_transition(
    prepared: tuple[Path, MockGitHub],
) -> None:
    directory, mock = prepared
    publish(directory)
    assert mock.tags_created == 1
    assert mock.transitions == 1 and mock.live and not mock.draft
    assert mock.readbacks == 4  # asset x2 + GitHub Source code ZIP and TAR
    events = mock.events
    idx = events.index("api:PATCH:releases/101")
    assert "draft-create" in events[:idx]
    assert "get:zipball/" + SHA in events[:idx]
    assert "get:tarball/" + SHA in events[:idx]
    assert "get:zipball/" + TAG in events[:idx]
    assert "get:tarball/" + TAG in events[:idx]
    assert "get:releases/assets/1" in events[:idx]
    assert "get:releases/assets/2" in events[:idx]
    assert any(e.startswith("get:zipball/") for e in events[idx:])  # additional readback


@pytest.mark.parametrize("fmt", ["zip", "tar"])
def test_bad_exact_sha_archive_blocks_tag_and_draft(
    prepared: tuple[Path, MockGitHub], fmt: str,
) -> None:
    directory, mock = prepared
    mock.corrupt_format = fmt
    with pytest.raises(release.PublicationError, match="blob mismatch"):
        publish(directory)
    assert not mock.tag and not mock.draft and not mock.live
    assert mock.transitions == 0


@pytest.mark.parametrize("bad_asset", ["fixture.zip", "release-provenance.json"])
def test_corrupt_draft_asset_stays_unpublished(
    prepared: tuple[Path, MockGitHub], bad_asset: str,
) -> None:
    directory, mock = prepared
    mock.wrong_asset = bad_asset
    with pytest.raises(release.PublicationError, match="DRAFT_UNPUBLISHED_VERIFICATION_FAILED"):
        publish(directory)
    assert mock.draft and not mock.live and mock.transitions == 0


def test_missing_draft_asset_stays_unpublished(prepared: tuple[Path, MockGitHub]) -> None:
    directory, mock = prepared
    mock.missing_asset = True
    with pytest.raises(release.PublicationError, match="DRAFT_UNPUBLISHED_VERIFICATION_FAILED"):
        publish(directory)
    assert mock.draft and not mock.live and mock.transitions == 0


@pytest.mark.parametrize("target_commitish", ["main", "refs/heads/main", "b" * 40, SHA, None])
def test_target_commitish_is_not_tag_proof(
    prepared: tuple[Path, MockGitHub], target_commitish: object,
) -> None:
    directory, mock = prepared
    mock.target_commitish = target_commitish
    publish(directory)
    assert mock.live and mock.transitions == 1


def test_moved_annotated_tag_cannot_pass_draft_gate(prepared: tuple[Path, MockGitHub]) -> None:
    directory, mock = prepared
    mock.wrong_tag = True
    with pytest.raises(release.PublicationError, match="TAG_ONLY_PREPUBLICATION_FAILED"):
        publish(directory)
    assert not mock.draft and mock.transitions == 0


def test_tag_only_recovery_does_not_rewrite_tag(prepared: tuple[Path, MockGitHub]) -> None:
    directory, mock = prepared
    mock.tag = True
    publish(directory, mode="resume-tag-only")
    assert mock.tags_created == 0 and mock.transitions == 1


@pytest.mark.parametrize("existing", ["draft", "published"])
def test_repeated_or_partial_draft_never_auto_resume(
    prepared: tuple[Path, MockGitHub], existing: str,
) -> None:
    directory, mock = prepared
    mock.tag = True
    mock.draft = existing == "draft"
    mock.live = existing == "published"
    with pytest.raises(release.PublicationError, match="Existing"):
        publish(directory, mode="resume-tag-only")
    assert mock.transitions == 0 and mock.tags_created == 0


def test_stale_main_refused_before_tag(prepared: tuple[Path, MockGitHub]) -> None:
    directory, mock = prepared
    mock.stale_main = True
    with pytest.raises(release.PublicationError, match="Remote main advanced"):
        publish(directory)
    assert not mock.tag and not mock.live and mock.transitions == 0


def test_permission_failure_does_not_enter_public_state(
    prepared: tuple[Path, MockGitHub],
) -> None:
    directory, mock = prepared
    mock.no_permission = True
    with pytest.raises(release.PublicationError, match="403"):
        publish(directory)
    assert mock.transitions == 0 and not mock.live


@pytest.mark.parametrize("where", ["create", "transition"])
def test_interrupted_publication_reports_partial_state_without_replaying(
    prepared: tuple[Path, MockGitHub], where: str,
) -> None:
    directory, mock = prepared
    mock.interrupt_draft = where == "create"
    mock.interrupt_transition = where == "transition"
    with pytest.raises(release.PublicationError, match=(
        "DRAFT_CREATION_UNCERTAIN" if where == "create" else "PUBLICATION_TRANSITION_UNCERTAIN"
    )):
        publish(directory)
    assert mock.draft and not mock.live
    assert mock.transitions == (0 if where == "create" else 1)


def test_preparation_does_not_write_remote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(release, "checked_identity", lambda *args: TAG)
    monkeypatch.setattr(release, "tree_blobs", lambda: {"README.md": OID})
    monkeypatch.setattr(release, "public_snapshot_blobs", lambda objects: objects)
    monkeypatch.setattr(release, "snapshot_risks", lambda *args: [])
    monkeypatch.setattr(release, "notes_for", lambda *args: NOTES)
    monkeypatch.setattr(release, "gh_api", lambda *args, **kw: pytest.fail("GH API during prepare"))
    monkeypatch.setattr(release, "run", lambda *args, **kw: pytest.fail("GH mutation during prepare"))
    monkeypatch.setattr(release, "build_candidate", lambda *args, **kw: None)
    monkeypatch.setattr(release, "verify_candidate", lambda *args: (
        tmp_path / "source.zip", {"archive_sha256": "digest", "uv_lock_sha256": "digest",
                                  "python_version": "3.11", "python_version_file_sha256": "digest",
                                  "files_checked_against_git_tree": 1}))
    folder = tmp_path / "prepared"
    release.prepare("1.2.3", SHA, folder, enforce=True,
                    publish_confirmation="PUBLISH-v1.2.3",
                    rights_confirmation="PUBLIC-SNAPSHOT-AND-RIGHTS-REVIEWED")
    assert (folder / "release-provenance.json").is_file()
    assert not (folder / "candidate" / "draft-release").exists()


@pytest.mark.parametrize("fmt", ["zip", "tar"])
def test_tag_archive_mismatch_blocks_draft_after_creating_valid_tag(
    prepared: tuple[Path, MockGitHub], fmt: str,
) -> None:
    directory, mock = prepared
    mock.corrupt_format = fmt
    mock.corrupt_ref = TAG  # SHA preflight succeeds; actual tag archive is wrong.
    with pytest.raises(release.PublicationError, match="TAG_ONLY_PREPUBLICATION_FAILED"):
        publish(directory)
    assert mock.tag and mock.tags_created == 1
    assert not mock.draft and not mock.live and mock.transitions == 0


def test_incomplete_asset_upload_state_blocks_public_transition(
    prepared: tuple[Path, MockGitHub],
) -> None:
    directory, mock = prepared
    mock.incomplete_asset_state = True
    with pytest.raises(release.PublicationError, match="DRAFT_UNPUBLISHED_VERIFICATION_FAILED"):
        publish(directory)
    assert mock.draft and not mock.live and mock.transitions == 0


def test_main_advancing_after_draft_verification_blocks_public_transition(
    prepared: tuple[Path, MockGitHub],
) -> None:
    directory, mock = prepared
    mock.advance_after_draft = True
    with pytest.raises(release.PublicationError, match="DRAFT_UNPUBLISHED_VERIFICATION_FAILED"):
        publish(directory)
    assert mock.draft and not mock.live and mock.transitions == 0


def test_github_binary_fetch_without_auth_token_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with pytest.raises(release.PublicationError, match="authentication"):
        release.download_hosted(f"zipball/{SHA}", tmp_path / "out.zip",
                                accept="application/vnd.github+json")
    assert not (tmp_path / "out.zip").exists()


def test_redirect_cannot_exfiltrate_github_token() -> None:
    import urllib.request

    redirect = release._GitHubRedirects()
    request = urllib.request.Request(
        "https://api.github.com/repos/example/example/zipball",
        headers={"Authorization": "Bearer synthetic-not-real"},
    )
    with pytest.raises(release.PublicationError, match="untrusted host"):
        redirect.redirect_request(request, None, 302, "redirect", {},
                                  "https://malicious.invalid/collect")


def test_asset_replaced_between_verification_and_public_transition_stays_draft(
    prepared: tuple[Path, MockGitHub],
) -> None:
    directory, mock = prepared
    mock.replace_asset_ids_after_download = True
    with pytest.raises(release.PublicationError, match="DRAFT_UNPUBLISHED_VERIFICATION_FAILED"):
        publish(directory)
    assert mock.draft and not mock.live and mock.transitions == 0


def test_hosted_binary_download_uses_authenticated_https_and_saves_exact_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    class Response:
        status = 200

        def __init__(self) -> None:
            self.parts = [b"exact-hosted-payload", b""]

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def geturl(self) -> str:
            return "https://codeload.github.com/synthetic/source"

        def read(self, amount: int) -> bytes:
            assert amount == 1024 * 1024
            return self.parts.pop(0)

    class Opener:
        def open(self, request: object, timeout: int) -> Response:
            assert timeout == 90
            assert request.get_header("Authorization") == "Bearer synthetic-token"
            return Response()

    monkeypatch.setenv("GH_TOKEN", "synthetic-token")
    monkeypatch.setattr(release.url_request, "build_opener", lambda *x: Opener())
    destination = tmp_path / "source.zip"
    release.download_hosted(f"zipball/{SHA}", destination,
                            accept="application/vnd.github+json")
    assert destination.read_bytes() == b"exact-hosted-payload"
    with pytest.raises(release.PublicationError, match="overwrite"):
        release.download_hosted(f"zipball/{SHA}", destination,
                                accept="application/vnd.github+json")
