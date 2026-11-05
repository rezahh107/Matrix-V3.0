"""Synthetic annotated-tag upgrade/rollback; only disposable local Git repositories."""
from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from tools import personal_release as release


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
    assert len(list((checkout / ".matrix-personal" / "backups").iterdir())) == 2


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


def test_invalid_unqualified_version_and_missing_rollback(checkout: Path, fake_uv) -> None:
    for tag in ("main", "v1.1.1", "v9.0.0", "../../v1.0.0"):
        with pytest.raises(release.ReleaseError):
            release.activate(checkout, tag)
    assert not (checkout / ".matrix-personal" / "state.json").exists()
    with pytest.raises(release.ReleaseError, match="No previous"):
        release.rollback(checkout)


def test_dirty_initial_checkout_blocks_git_write(checkout: Path, fake_uv) -> None:
    (checkout / "config" / "policy.json").write_text('{"changed":true}')
    with pytest.raises(release.ReleaseError, match="Local edits"):
        release.activate(checkout, "v1.0.0")
    assert not (checkout / ".matrix-personal").exists()
