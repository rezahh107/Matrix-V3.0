"""Synthetic annotated-tag upgrade/rollback; only disposable local Git repositories."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import personal_release as release
from tools.ci.probe_personal_release_actual_windows import select_candidate_identity
from tools.ci.qualify_uv_source import validate_version_identity


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()


def _write(root: Path, path: str, text: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-b", "main")
    _git(seed, "config", "user.email", "synthetic@example.invalid")
    _git(seed, "config", "user.name", "Synthetic Test")
    _write(seed, ".gitignore", ".matrix-personal/\n.venv/\n__pycache__/\n*.pyc\n")
    _write(seed, ".python-version", "3.11\n")
    _write(seed, "app/__init__.py", "")
    _write(seed, "app/main.py", "VERSION = 1\n")
    _write(seed, "config/policy.json", '{"synthetic":true}\n')
    _write(seed, "CHANGELOG.md", "## [Unreleased]\n## [1.0.0] - 2026-11-05\n")
    for version in ("1.0.0", "1.1.0"):
        _write(seed, "pyproject.toml", '[project]\nname="smart-student-allocation"\n'
               f'version="{version}"\nrequires-python=">=3.11"\n')
        _write(seed, "uv.lock", 'version = 1\nrequires-python = ">=3.11"\n'
               '[[package]]\nname = "smart-student-allocation"\n'
               f'version = "{version}"\nsource = {{ virtual = "." }}\n')
        _git(seed, "add", ".")
        _git(seed, "commit", "-m", f"fixture {version}")
        _git(seed, "tag", "-a", f"v{version}", "-m", "synthetic approved version")
        if version == "1.0.0":
            _write(seed, "app/main.py", "VERSION = 2\n")
            _write(seed, "CHANGELOG.md", "## [Unreleased]\n"
                   "## [1.1.0] - 2026-11-05\n## [1.0.0] - 2026-11-05\n")
    _git(seed, "tag", "v9.0.0")  # invalid lightweight tag, not a release
    remote = tmp_path / "remote.git"
    _git(tmp_path, "clone", "--bare", str(seed), str(remote))
    client = tmp_path / "client"
    _git(tmp_path, "clone", str(remote), str(client))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    database = fake_home / ".smart_alloc" / "years" / "smart_alloc_1405.sqlite"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE personal (value TEXT)")
        conn.execute("INSERT INTO personal VALUES ('synthetic-kept')")
    (fake_home / ".smart_alloc" / "user_settings.json").write_text(
        '{"synthetic":"kept"}', encoding="utf-8"
    )
    return client


@pytest.fixture
def fake_uv(monkeypatch: pytest.MonkeyPatch):
    real_command = release.command
    events: list[tuple[str, str]] = []
    fail_sync = {"value": False}

    def execute(argv: list[str], *, cwd: Path, capture: bool = True) -> str:
        if argv[0] != "uv":
            return real_command(argv, cwd=cwd, capture=capture)
        events.append((" ".join(argv[:2]), cwd.name))
        if argv[1] == "sync":
            if fail_sync["value"]:
                raise release.ReleaseError("Synthetic uv sync error")
            (cwd / ".venv").mkdir(exist_ok=True)
        if argv[1] == "run":
            assert (cwd / ".venv").is_dir()
            assert (cwd / "app" / "main.py").is_file()
        return ""

    monkeypatch.setattr(release, "command", execute)
    return events, fail_sync


def _state(client: Path) -> dict:
    return json.loads((client / ".matrix-personal" / "state.json").read_text(encoding="utf-8"))


def test_selected_upgrade_rollback_and_preserved_data(checkout: Path, fake_uv) -> None:
    events, _ = fake_uv
    release.activate(checkout, "v1.0.0")
    v1 = _state(checkout)["current"]
    assert v1["tag"] == "v1.0.0"
    release.activate(checkout, "v1.1.0")
    assert _state(checkout)["current"]["tag"] == "v1.1.0"
    assert _state(checkout)["previous"] == v1
    assert (checkout / ".matrix-personal" / "versions" /
            f"v1.0.0--{v1['sha'][:12]}" / "app" / "main.py").read_text() == "VERSION = 1\n"
    release.rollback(checkout)
    assert _state(checkout)["current"] == v1
    assert _state(checkout)["previous"] is None
    assert (Path.home() / ".smart_alloc" / "user_settings.json").read_text() == '{"synthetic":"kept"}'
    with sqlite3.connect(Path.home() / ".smart_alloc" / "years" /
                         "smart_alloc_1405.sqlite") as conn:
        assert conn.execute("SELECT value FROM personal").fetchone()[0] == "synthetic-kept"
    assert any(e[0] == "uv sync" for e in events)
    backups = list((checkout / ".matrix-personal" / "backups").iterdir())
    assert len(backups) == 2
    for directory in backups:
        with sqlite3.connect(directory / "smart_alloc_1405.sqlite") as conn:
            assert conn.execute("SELECT value FROM personal").fetchone()[0] == "synthetic-kept"
        assert (directory / "user_settings.json").read_text() == '{"synthetic":"kept"}'


def test_dirty_worktree_blocks_activation_without_data_loss(checkout: Path, fake_uv) -> None:
    release.activate(checkout, "v1.0.0")
    current = _state(checkout)["current"]
    target = release.record_dir(checkout, current)
    (target / "config" / "policy.json").write_text('{"owner-edit":"keep"}')
    with pytest.raises(release.ReleaseError, match="Local edits"):
        release.activate(checkout, "v1.1.0")
    assert _state(checkout)["current"] == current
    assert (target / "config" / "policy.json").read_text() == '{"owner-edit":"keep"}'


def test_untracked_private_file_blocks_activation(checkout: Path, fake_uv) -> None:
    (checkout / "private_sabt_profile.xlsx").write_text("synthetic")
    with pytest.raises(release.ReleaseError, match="untracked"):
        release.activate(checkout, "v1.0.0")
    assert not (checkout / ".matrix-personal" / "state.json").exists()


def test_sync_failure_retains_old_version(checkout: Path, fake_uv) -> None:
    _, fail = fake_uv
    release.activate(checkout, "v1.0.0")
    before = _state(checkout)
    fail["value"] = True
    with pytest.raises(release.ReleaseError, match="Synthetic uv sync error"):
        release.activate(checkout, "v1.1.0")
    assert _state(checkout) == before
    fail["value"] = False
    release.activate(checkout, "v1.1.0")
    assert _state(checkout)["previous"] == before["current"]


def test_broken_sqlite_backup_does_not_activate_new_version(checkout: Path, fake_uv) -> None:
    release.activate(checkout, "v1.0.0")
    original = _state(checkout)
    invalid = Path.home() / ".smart_alloc" / "years" / "broken.sqlite"
    invalid.write_bytes(b"not a valid SQLite database")
    with pytest.raises(sqlite3.DatabaseError):
        release.activate(checkout, "v1.1.0")
    assert _state(checkout) == original
    assert invalid.read_bytes() == b"not a valid SQLite database"


def test_invalid_unqualified_version_and_missing_rollback(checkout: Path, fake_uv) -> None:
    for tag in ("main", "v1.1.1", "v9.0.0", "../../v1.0.0"):
        with pytest.raises(release.ReleaseError):
            release.activate(checkout, tag)
    assert not (checkout / ".matrix-personal" / "state.json").exists()
    with pytest.raises(release.ReleaseError, match="No previous"):
        release.rollback(checkout)


def test_reentrant_operation_guard_refuses_parallel_updates(checkout: Path, fake_uv) -> None:
    """A second invocation cannot read old state and concurrently overwrite it."""
    with release.operation_guard(checkout):
        with pytest.raises(release.ReleaseError, match="Another Matrix operation"):
            release.activate(checkout, "v1.0.0")
        with pytest.raises(release.ReleaseError, match="Another Matrix operation"):
            release.rollback(checkout)
        assert not (checkout / ".matrix-personal" / "state.json").exists()
    assert not (checkout / ".matrix-personal" / ".operation-lock").exists()
    release.activate(checkout, "v1.0.0")
    assert _state(checkout)["current"]["tag"] == "v1.0.0"


def test_stale_lock_fails_closed_without_deletion(checkout: Path, fake_uv) -> None:
    marker = checkout / ".matrix-personal" / ".operation-lock"
    marker.mkdir(parents=True)
    with pytest.raises(release.ReleaseError, match="stale operation lock"):
        release.activate(checkout, "v1.0.0")
    assert marker.is_dir()
    assert not (checkout / ".matrix-personal" / "state.json").exists()

def test_dirty_initial_checkout_blocks_git_write(checkout: Path, fake_uv) -> None:
    (checkout / "config" / "policy.json").write_text('{"changed":true}')
    with pytest.raises(release.ReleaseError, match="Local edits"):
        release.activate(checkout, "v1.0.0")
    assert not (checkout / ".matrix-personal").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Real Windows Git+uv integration")
def test_real_windows_uv_upgrade_rollback(checkout: Path) -> None:
    """Exercise actual Git fetch, uv Python setup, uv locked sync and import on Windows."""
    release.activate(checkout, "v1.0.0")
    initial = _state(checkout)["current"]
    assert (release.record_dir(checkout, initial) / ".venv").is_dir()
    release.activate(checkout, "v1.1.0")
    second = _state(checkout)["current"]
    assert second["tag"] == "v1.1.0" and second["sha"] != initial["sha"]
    assert (release.record_dir(checkout, second) / ".venv").is_dir()
    release.rollback(checkout)
    assert _state(checkout)["current"] == initial
    assert (release.record_dir(checkout, initial) / ".venv").is_dir()
    assert (release.record_dir(checkout, initial) / "app/main.py").read_text() == "VERSION = 1\n"


@pytest.mark.parametrize("malformed", [{}, [], False, 0, ""])
def test_read_state_rejects_falsy_current_records(tmp_path: Path, malformed) -> None:
    """Only explicit JSON null can mean no installed release."""
    path = tmp_path / "state.json"
    payload = {"current": malformed, "previous": None}
    original = json.dumps(payload).encode("utf-8")
    path.write_bytes(original)
    with pytest.raises(release.ReleaseError, match="Invalid installed release record"):
        release.read_state(path)
    assert path.read_bytes() == original


@pytest.mark.parametrize("malformed", [{}, [], False, 0, "", {"tag": "v1.0.0"},
                                       {"tag": "v1.0.0", "sha": "bad", "version": "1.0.0", "python": "3.11"},
                                       {"tag": "v1.0.0", "sha": "a" * 40, "version": "1.0.0", "python": []}])
def test_read_state_rejects_malformed_previous(tmp_path: Path, malformed) -> None:
    path = tmp_path / "state.json"
    current = {"tag": "v1.1.0", "sha": "b" * 40, "version": "1.1.0", "python": "3.11"}
    path.write_text(json.dumps({"current": current, "previous": malformed}), encoding="utf-8")
    with pytest.raises(release.ReleaseError, match="Invalid installed"):
        release.read_state(path)


@pytest.mark.parametrize("record", [
    {"tag": "v1.0.0", "sha": "a" * 40, "version": "9.0.0", "python": "3.11"},
    {"tag": "v1.0.0", "sha": "a" * 40, "version": "1.0.0", "python": "anything"},
    {"tag": "v01.0.0", "sha": "a" * 40, "version": "01.0.0", "python": "3.11"},
    {"tag": "v1.0.0", "sha": "A" * 40, "version": "1.0.0", "python": "3.11"},
    {"tag": "v1.0.0", "sha": "a" * 40, "version": "1.0.0", "python": "3.11", "extra": 1},
])
def test_read_state_rejects_invalid_record_fields(tmp_path: Path, record) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"current": record, "previous": None}), encoding="utf-8")
    with pytest.raises(release.ReleaseError, match="Invalid installed"):
        release.read_state(path)


def test_read_state_rejects_previous_without_current(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    previous = {"tag": "v1.0.0", "sha": "a" * 40, "version": "1.0.0", "python": "3.11"}
    path.write_text(json.dumps({"current": None, "previous": previous}), encoding="utf-8")
    with pytest.raises(release.ReleaseError, match="Previous.*current"):
        release.read_state(path)


@pytest.mark.parametrize("same_field", ["tag", "sha"])
def test_read_state_rejects_indistinguishable_releases(tmp_path: Path, same_field: str) -> None:
    path = tmp_path / "state.json"
    current = {"tag": "v1.0.0", "sha": "a" * 40, "version": "1.0.0", "python": "3.11"}
    previous = {"tag": "v1.1.0", "sha": "b" * 40, "version": "1.1.0", "python": "3.11"}
    if same_field == "tag":
        previous["tag"] = current["tag"]
        previous["version"] = current["version"]
    else:
        previous["sha"] = current["sha"]
    path.write_text(json.dumps({"current": current, "previous": previous}), encoding="utf-8")
    with pytest.raises(release.ReleaseError, match="distinct"):
        release.read_state(path)


def test_read_state_accepts_only_supported_state_relations(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    current = {"tag": "v1.1.0", "sha": "b" * 40, "version": "1.1.0", "python": "3.11.8"}
    previous = {"tag": "v1.0.0", "sha": "a" * 40, "version": "1.0.0", "python": "3.11"}
    assert release.read_state(path) == {"current": None, "previous": None}
    for state in ({"current": None, "previous": None},
                  {"current": current, "previous": None},
                  {"current": current, "previous": previous},
                  {"current": previous, "previous": current}):
        path.write_text(json.dumps(state), encoding="utf-8")
        assert release.read_state(path) == state


@pytest.mark.parametrize("malformed_target", ["current", "previous"])
def test_malformed_state_blocks_activation_without_mutations(
    checkout: Path, fake_uv, malformed_target: str
) -> None:
    events, _ = fake_uv
    release.activate(checkout, "v1.0.0")
    initial = _state(checkout)
    corrupted = {**initial, malformed_target: {}}
    state_path = checkout / ".matrix-personal" / "state.json"
    raw = (json.dumps(corrupted, sort_keys=True) + "\n").encode()
    state_path.write_bytes(raw)
    db = Path.home() / ".smart_alloc" / "years" / "smart_alloc_1405.sqlite"
    settings = Path.home() / ".smart_alloc" / "user_settings.json"
    db_bytes, settings_bytes = db.read_bytes(), settings.read_bytes()
    before_versions = sorted(x.name for x in (checkout / ".matrix-personal" / "versions").iterdir())
    before_backups = sorted(x.name for x in (checkout / ".matrix-personal" / "backups").iterdir())
    before_events = list(events)
    with pytest.raises(release.ReleaseError, match="Invalid installed release record"):
        release.activate(checkout, "v1.1.0")
    assert state_path.read_bytes() == raw
    assert db.read_bytes() == db_bytes
    assert settings.read_bytes() == settings_bytes
    assert sorted(x.name for x in (checkout / ".matrix-personal" / "versions").iterdir()) == before_versions
    assert sorted(x.name for x in (checkout / ".matrix-personal" / "backups").iterdir()) == before_backups
    assert events == before_events
    assert not (checkout / ".matrix-personal" / ".operation-lock").exists()


def test_malformed_state_rejected_by_status_and_rollback(checkout: Path, fake_uv) -> None:
    release.activate(checkout, "v1.0.0")
    release.activate(checkout, "v1.1.0")
    state_path = checkout / ".matrix-personal" / "state.json"
    state = _state(checkout)
    state["previous"] = []
    raw = json.dumps(state).encode()
    state_path.write_bytes(raw)
    with pytest.raises(release.ReleaseError, match="Invalid installed release record"):
        release.status(checkout)
    with pytest.raises(release.ReleaseError, match="Invalid installed release record"):
        release.rollback(checkout)
    assert state_path.read_bytes() == raw


def test_dangling_state_symlink_is_not_uninitialized(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    try:
        path.symlink_to(tmp_path / "missing.json")
    except (OSError, NotImplementedError):
        pytest.skip("OS does not allow creating a test symlink")
    with pytest.raises(release.ReleaseError, match="symlinked personal release state"):
        release.read_state(path)
    assert path.is_symlink()


@pytest.mark.parametrize("payload", [
    '{"current":{}, "current":null, "previous":null}',
    '{"current":{"tag":"v1.0.0","tag":"v1.0.0","sha":"' + 'a' * 40
    + '","version":"1.0.0","python":"3.11"},"previous":null}',
])
def test_read_state_rejects_ambiguous_duplicate_json_keys(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "state.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(release.ReleaseError, match="Release state is invalid"):
        release.read_state(path)
    assert path.read_text(encoding="utf-8") == payload


def test_malformed_initial_state_is_not_reinitialized(checkout: Path, fake_uv) -> None:
    state_path = checkout / ".matrix-personal" / "state.json"
    state_path.parent.mkdir()
    original = b'{"current":{},"previous":null}\n'
    state_path.write_bytes(original)
    db = Path.home() / ".smart_alloc" / "years" / "smart_alloc_1405.sqlite"
    before_data = db.read_bytes()
    with pytest.raises(release.ReleaseError, match="Invalid installed release record"):
        release.activate(checkout, "v1.0.0")
    assert state_path.read_bytes() == original
    assert db.read_bytes() == before_data
    assert not (checkout / ".matrix-personal" / "versions").exists()
    assert not (checkout / ".matrix-personal" / "backups").exists()
    assert not (checkout / ".matrix-personal" / ".operation-lock").exists()


def test_valid_status_does_not_mutate_state(checkout: Path, fake_uv, capsys) -> None:
    release.status(checkout)
    assert json.loads(capsys.readouterr().out) == {"current": None, "previous": None}
    assert not (checkout / ".matrix-personal" / "state.json").exists()
    release.activate(checkout, "v1.0.0")
    state_path = checkout / ".matrix-personal" / "state.json"
    before = state_path.read_bytes()
    capsys.readouterr()
    release.status(checkout)
    assert json.loads(capsys.readouterr().out) == _state(checkout)
    assert state_path.read_bytes() == before


# The real Windows probe must use the candidate HEAD version, not the first
# proposed release's number. These fixtures never create Git tags or publish.
def _candidate_metadata(
    root: Path,
    version: str,
    *,
    lock_version: str | None = None,
    dated_entry: bool = True,
    python_pin: str = "3.11",
) -> None:
    _write(root, "pyproject.toml",
           '[project]\nname = "smart-student-allocation"\n'
           f'version = "{version}"\nrequires-python = ">=3.11"\n')
    _write(root, "uv.lock",
           'version = 1\nrequires-python = ">=3.11"\n'
           '[[package]]\nname = "smart-student-allocation"\n'
           f'version = "{lock_version if lock_version is not None else version}"\n'
           'source = { virtual = "." }\n')
    _write(root, ".python-version", python_pin + "\n")
    _write(root, "CHANGELOG.md", "## [Unreleased]\n"
           + (f"## [{version}] - 2026-11-07\n" if dated_entry else ""))


@pytest.mark.parametrize("version", ["0.1.0", "0.1.1"])
def test_candidate_version_selection_uses_valid_metadata(
    tmp_path: Path, version: str
) -> None:
    _candidate_metadata(tmp_path, version)
    assert select_candidate_identity(tmp_path) == (version, "3.11", f"v{version}")


def test_original_hardcoded_gate_rejects_valid_future_version(tmp_path: Path) -> None:
    """Direct discriminator: the old literal rejects a properly qualified 0.1.1."""
    _candidate_metadata(tmp_path, "0.1.1")
    files = [(tmp_path / name).read_bytes() for name in (
        "pyproject.toml", "uv.lock", ".python-version", "CHANGELOG.md"
    )]
    with pytest.raises(RuntimeError, match="Requested release version differs"):
        validate_version_identity(*files, required_release_version="0.1.0")
    assert select_candidate_identity(tmp_path) == ("0.1.1", "3.11", "v0.1.1")


def test_candidate_version_selection_rejects_lock_mismatch(tmp_path: Path) -> None:
    _candidate_metadata(tmp_path, "0.1.1", lock_version="0.1.0")
    with pytest.raises(RuntimeError, match="uv.lock project version"):
        select_candidate_identity(tmp_path)


def test_candidate_version_selection_rejects_missing_dated_entry(tmp_path: Path) -> None:
    _candidate_metadata(tmp_path, "0.1.1", dated_entry=False)
    with pytest.raises(RuntimeError, match="no dated changelog entry"):
        select_candidate_identity(tmp_path)


@pytest.mark.parametrize("version", ["0.1.1rc1", "01.1.0"])
def test_candidate_version_selection_rejects_controller_incompatible_tag(
    tmp_path: Path, version: str
) -> None:
    _candidate_metadata(tmp_path, version)
    with pytest.raises(RuntimeError, match="stable vX.Y.Z tag"):
        select_candidate_identity(tmp_path)


def test_candidate_version_selection_rejects_incompatible_python_pin(tmp_path: Path) -> None:
    _candidate_metadata(tmp_path, "0.1.1", python_pin="3.10")
    with pytest.raises(RuntimeError, match="does not satisfy requires-python"):
        select_candidate_identity(tmp_path)
