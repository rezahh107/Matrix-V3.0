"""Exercise the real Matrix HEAD through the personal CMD/Git/uv consumer.

Windows CI only. All Git tags and synthetic local data live in a temp directory;
no GitHub tag, published version, or organizational records are involved.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def run(args: list[str], *, cwd: Path, env: dict[str, str] | None = None,
        ok: bool = True, timeout: int = 420) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args, cwd=cwd, env=env, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False, timeout=timeout,
    )
    if (result.returncode == 0) != ok:
        raise AssertionError(
            f"Unexpected exit={result.returncode} from {args[0]} {args[1:3]}; "
            f"stdout={result.stdout[-1800:]!r}; stderr={result.stderr[-1800:]!r}"
        )
    return result


def git(cwd: Path, *args: str) -> str:
    return run(["git", *args], cwd=cwd).stdout.strip()


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if os.name != "nt" or os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("This probe only runs in disposable Windows Actions")
    root = Path(__file__).resolve().parents[2]
    expected = os.environ["MATRIX_EXPECTED_SOURCE_SHA"]
    if re.fullmatch(r"[0-9a-f]{40}", expected) is None:
        raise RuntimeError("Expected exact 40-character commit SHA")
    if git(root, "rev-parse", "HEAD") != expected:
        raise AssertionError("CI checkout is not the intended source commit")

    # The proposed identity is not an officially approved release. A local
    # annotated tag is created *only* in a temp clone, never in the CI checkout.
    from tools.ci.qualify_uv_source import validate_version_identity
    version, python_pin = validate_version_identity(
        (root / "pyproject.toml").read_bytes(), (root / "uv.lock").read_bytes(),
        (root / ".python-version").read_bytes(), (root / "CHANGELOG.md").read_bytes(),
        required_release_version="0.1.0",
    )
    assert (version, python_pin) == ("0.1.0", "3.11")

    with tempfile.TemporaryDirectory(prefix="matrix-real-personal-ci-") as tmp:
        base = Path(tmp)
        remote, seed, client = (base / name for name in ("remote.git", "seed", "client"))
        run(["git", "init", "--bare", "--initial-branch=main", str(remote)], cwd=base)
        git(root, "push", str(remote), "HEAD:refs/heads/main")
        run(["git", "clone", str(remote), str(seed)], cwd=base)
        git(seed, "config", "user.name", "Disposable CI Tag")
        git(seed, "config", "user.email", "ci@example.invalid")
        git(seed, "tag", "-a", "v0.1.0", "-m", "DISPOSABLE CI ONLY - not a release")
        git(seed, "push", "origin", "refs/tags/v0.1.0")
        run(["git", "clone", "--no-tags", str(remote), str(client)], cwd=base)
        assert git(client, "rev-parse", "HEAD") == expected
        assert git(client, "tag", "--list") == ""

        home = base / "synthetic-user-home"
        years = home / ".smart_alloc" / "years"
        years.mkdir(parents=True)
        database = years / "smart_alloc_1405.sqlite"
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
            connection.execute("INSERT INTO marker VALUES ('synthetic-preserve-me')")
        settings = home / ".smart_alloc" / "user_settings.json"
        settings.write_text('{"ci_only":"preserve-me"}\n', encoding="utf-8")
        db_checksum, settings_checksum = checksum(database), checksum(settings)
        env = os.environ.copy()
        env.update({"HOME": str(home), "USERPROFILE": str(home),
                    "QT_QPA_PLATFORM": "offscreen", "MATRIX_CI_SMOKE_CLOSE_MS": "1400"})

        def personal(operation: str, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
            return run(["cmd.exe", "/d", "/c", "call", "Matrix-Personal.cmd",
                        operation, *args], cwd=client, env=env, ok=ok)

        # Invalid selection and dirty checkout must fail before new state.
        personal("activate", "v9.9.9", ok=False)
        assert not (client / ".matrix-personal" / "state.json").exists()
        readme = client / "README.md"
        readme.write_bytes(readme.read_bytes() + b"\nDISPOSABLE_DIRTY_FILE\n")
        personal("activate", "v0.1.0", ok=False)
        assert not (client / ".matrix-personal" / "state.json").exists()
        git(client, "restore", "--", "README.md")

        # A damaged annual DB prevents a valid snapshot and activation.
        broken = years / "broken.sqlite"
        broken.write_bytes(b"not-sqlite")
        personal("activate", "v0.1.0", ok=False)
        assert broken.read_bytes() == b"not-sqlite"
        assert not (client / ".matrix-personal" / "state.json").exists()
        broken.unlink()  # Only synthetic corruption, never real records.

        activated = personal("activate", "v0.1.0")
        assert "ACTIVE v0.1.0" in activated.stdout
        state = json.loads(personal("status").stdout)
        assert state["previous"] is None
        assert state["current"] == {
            "tag": "v0.1.0", "sha": expected, "version": "0.1.0", "python": python_pin
        }
        assert git(client, "rev-parse", "refs/tags/v0.1.0^{commit}") == expected
        assert git(client, "cat-file", "-t", "refs/tags/v0.1.0") == "tag"
        installed = client / ".matrix-personal" / "versions" / f"v0.1.0--{expected[:12]}"
        assert git(installed, "rev-parse", "HEAD") == expected
        assert (installed / ".venv" / "Scripts" / "python.exe").is_file()
        assert checksum(installed / "uv.lock") == checksum(root / "uv.lock")

        backups = client / ".matrix-personal" / "backups"
        valid = []
        for item in backups.iterdir():
            db = item / database.name
            if not (item / "README.txt").exists():
                continue  # A failed activation can leave an incomplete snapshot.
            with sqlite3.connect(db) as connection:
                assert connection.execute("PRAGMA quick_check").fetchone() == ("ok",)
                assert connection.execute("SELECT value FROM marker").fetchone() == (
                    "synthetic-preserve-me",)
            assert checksum(item / settings.name) == settings_checksum
            valid.append(item)
        assert len(valid) == 1, "Expected one complete, valid pre-activation snapshot"
        assert checksum(database) == db_checksum and checksum(settings) == settings_checksum

        # Real app entrypoint via selected locked environment; CI-only Qt close.
        started = personal("start")
        combined = started.stdout + started.stderr
        assert "UnicodeEncodeError" not in combined
        assert "--- Logging error ---" not in combined
        assert json.loads(personal("status").stdout) == state
        assert checksum(database) == db_checksum and checksum(settings) == settings_checksum
        personal("rollback", ok=False)  # No invented previous official version.
        assert json.loads(personal("status").stdout) == state
        print("REAL MATRIX WINDOWS CONSUMER PASS", expected, "v0.1.0 (LOCAL TAG ONLY)")
        print("real_uv_sync=yes; real_cmd_activate_status_start=yes; "
              "synthetic_sqlite_and_json_preserved=yes; actual_previous_version=no")


if __name__ == "__main__":
    sys.exit(main())
