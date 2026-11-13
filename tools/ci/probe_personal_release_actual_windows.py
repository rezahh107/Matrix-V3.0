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
from contextlib import closing
from pathlib import Path

from tools.ci.qualify_uv_source import validate_version_identity
from tools.personal_release import TAG_PATTERN


def select_candidate_identity(root: Path) -> tuple[str, str, str]:
    """Select the current HEAD's validated, stable personal-release identity."""
    inputs = tuple(
        (root / name).read_bytes()
        for name in ("pyproject.toml", "uv.lock", ".python-version", "CHANGELOG.md")
    )
    version, python_pin = validate_version_identity(*inputs)
    tag = f"v{version}"
    if TAG_PATTERN.fullmatch(tag) is None:
        raise RuntimeError("Candidate version cannot be represented by a stable vX.Y.Z tag")
    # The release consumer requires a dated entry for the selected version.
    validate_version_identity(*inputs, required_release_version=version)
    return version, python_pin, tag


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
    version, python_pin, tag = select_candidate_identity(root)

    with tempfile.TemporaryDirectory(prefix="matrix-real-personal-ci-") as tmp:
        base = Path(tmp)
        remote, seed, client = (base / name for name in ("remote.git", "seed", "client"))
        run(["git", "init", "--bare", "--initial-branch=main", str(remote)], cwd=base)
        git(root, "push", str(remote), "HEAD:refs/heads/main")
        run(["git", "clone", str(remote), str(seed)], cwd=base)
        git(seed, "config", "user.name", "Disposable CI Tag")
        git(seed, "config", "user.email", "ci@example.invalid")
        git(seed, "tag", "-a", tag, "-m", "DISPOSABLE CI ONLY - not a release")
        git(seed, "push", "origin", f"refs/tags/{tag}")
        run(["git", "clone", "--no-tags", str(remote), str(client)], cwd=base)
        assert git(client, "rev-parse", "HEAD") == expected
        assert git(client, "tag", "--list") == ""

        home = base / "synthetic-user-home"
        years = home / ".smart_alloc" / "years"
        years.mkdir(parents=True)
        database = years / "smart_alloc_1405.sqlite"
        with closing(sqlite3.connect(database)) as connection, connection:
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
        personal("activate", "not-an-approved-tag", ok=False)
        # Also reject a well-formed version absent from the disposable remote.
        missing_tag = f"v{int(version.split('.')[0]) + 1}.0.0"
        personal("activate", missing_tag, ok=False)
        assert not (client / ".matrix-personal" / "state.json").exists()
        readme = client / "README.md"
        readme.write_bytes(readme.read_bytes() + b"\nDISPOSABLE_DIRTY_FILE\n")
        personal("activate", tag, ok=False)
        assert not (client / ".matrix-personal" / "state.json").exists()
        git(client, "restore", "--", "README.md")

        # A damaged annual DB prevents a valid snapshot and activation.
        broken = years / "broken.sqlite"
        broken.write_bytes(b"not-sqlite")
        personal("activate", tag, ok=False)
        assert broken.read_bytes() == b"not-sqlite"
        assert not (client / ".matrix-personal" / "state.json").exists()
        broken.unlink()  # Only synthetic corruption, never real records.

        activated = personal("activate", tag)
        assert f"ACTIVE {tag}" in activated.stdout
        state = json.loads(personal("status").stdout)
        assert state["previous"] is None
        assert state["current"] == {
            "tag": tag, "sha": expected, "version": version, "python": python_pin
        }
        assert git(client, "rev-parse", f"refs/tags/{tag}^{{commit}}") == expected
        assert git(client, "cat-file", "-t", f"refs/tags/{tag}") == "tag"
        installed = client / ".matrix-personal" / "versions" / f"{tag}--{expected[:12]}"
        assert git(installed, "rev-parse", "HEAD") == expected
        assert (installed / ".venv" / "Scripts" / "python.exe").is_file()
        assert checksum(installed / "uv.lock") == checksum(root / "uv.lock")

        backups = client / ".matrix-personal" / "backups"
        valid = []
        for item in backups.iterdir():
            db = item / database.name
            if not (item / "README.txt").exists():
                continue  # A failed activation can leave an incomplete snapshot.
            with closing(sqlite3.connect(db)) as connection:
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
        # Launch may legitimately update SQLite schema/metadata or settings.
        # Preserve the original synthetic record, not the file's physical bytes.
        with closing(sqlite3.connect(database)) as connection:
            assert connection.execute("PRAGMA quick_check").fetchone() == ("ok",)
            assert connection.execute("SELECT value FROM marker").fetchone() == (
                "synthetic-preserve-me",)
        assert json.loads(settings.read_text(encoding="utf-8"))["ci_only"] == "preserve-me"
        print("After startup: raw DB unchanged=", checksum(database) == db_checksum,
              "raw JSON unchanged=", checksum(settings) == settings_checksum)
        personal("rollback", ok=False)  # No invented previous official version.
        assert json.loads(personal("status").stdout) == state
        print("REAL MATRIX WINDOWS CONSUMER PASS", expected, tag, "(LOCAL TAG ONLY)")
        print("real_uv_sync=yes; real_cmd_activate_status_start=yes; "
              "synthetic_sqlite_and_json_preserved=yes; actual_previous_version=no")
    qualify_published_two_version_upgrade()




def qualify_published_two_version_upgrade() -> None:
    """Actual published v0.1.0 -> candidate Git+uv/Qt upgrade on disposable Windows."""
    import shutil
    from datetime import UTC, datetime

    from tools.personal_release import TAG_PATTERN

    root = Path(__file__).resolve().parents[2]
    expected = os.environ["MATRIX_EXPECTED_SOURCE_SHA"]
    version, pin, candidate_tag = select_candidate_identity(root)
    assert candidate_tag == "v0.2.0" and TAG_PATTERN.fullmatch(candidate_tag)
    assert git(root, "rev-parse", "HEAD") == expected
    assert os.name == "nt" and os.environ.get("GITHUB_ACTIONS") == "true"

    old_tag = "v0.1.0"
    old_commit = "36817ca03bc798fafc091a7bfa7afde22bc7ad76"
    old_tag_object = "57169369d3255ddb508c88d3be6854f93db39d79"
    assert old_commit != expected, "Two-version test cannot use the same commit twice"

    # Only fetch immutable published source. GitHub Actions checkout is disposable.
    if git(root, "rev-parse", "--verify", "refs/tags/v0.1.0") != old_tag_object:
        raise AssertionError("Published annotated v0.1.0 tag identity changed")
    assert git(root, "cat-file", "-t", "refs/tags/v0.1.0") == "tag"
    assert git(root, "rev-parse", "refs/tags/v0.1.0^{commit}") == old_commit

    evidence: dict[str, object] = {
        "scenario": "published-v0.1.0-to-candidate-v0.2.0",
        "source": {"old_tag_object": old_tag_object, "old_commit": old_commit,
                   "candidate_commit": expected,
                   "candidate_tree": git(root, "rev-parse", "HEAD^{tree}"),
                   "candidate_version": version, "python_pin": pin},
        "environment": "github-hosted-windows-disposable",
        "cases": {},
        "conclusion": "FAIL",
    }
    report_dir = Path(os.environ["MATRIX_UPGRADE_EVIDENCE_DIR"])
    report_dir.mkdir(parents=True, exist_ok=True)

    def passed(case: str, note: str) -> None:
        cases = evidence["cases"]
        assert isinstance(cases, dict)
        cases[case] = {"status": "PASS", "oracle": note}

    def semantic(path: Path) -> dict[str, object]:
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            refs = db.execute("PRAGMA foreign_key_check").fetchall()
            schema = db.execute(
                "SELECT schema_version FROM schema_meta WHERE id=1"
            ).fetchone()[0]
            runs = db.execute(
                "SELECT run_uuid, status FROM runs WHERE run_uuid='d4-upgrade-synthetic'"
            ).fetchall()
            metrics = db.execute(
                "SELECT rm.metric_key, rm.metric_value FROM run_metrics rm "
                "JOIN runs r ON r.id=rm.run_id "
                "WHERE r.run_uuid='d4-upgrade-synthetic'"
            ).fetchall()
        return {"integrity": integrity, "foreign_keys": refs, "schema": schema,
                "runs": runs, "metrics": metrics}

    try:
        with tempfile.TemporaryDirectory(prefix="matrix-d4-two-version-") as tmp:
            base = Path(tmp)
            remote, seed, client = (base / n for n in ("remote.git", "seed", "client"))
            git(base, "init", "--bare", "--initial-branch=main", str(remote))
            git(root, "push", str(remote), "HEAD:refs/heads/main",
                "refs/tags/v0.1.0:refs/tags/v0.1.0")
            git(base, "clone", str(remote), str(seed))
            git(seed, "config", "user.name", "CI Disposable Release")
            git(seed, "config", "user.email", "ci@example.invalid")
            git(seed, "tag", "-a", candidate_tag, "-m", "LOCAL TEST ONLY")
            git(seed, "push", "origin", f"refs/tags/{candidate_tag}")
            git(base, "clone", "--no-tags", str(remote), str(client))
            assert git(client, "tag", "--list") == ""
            assert git(client, "rev-parse", "HEAD") == expected

            home = base / "synthetic-home"
            for folder in (home, base / "appdata", base / "localappdata", base / "temp"):
                folder.mkdir()
            years = home / ".smart_alloc" / "years"
            years.mkdir(parents=True)
            db_path = years / "smart_alloc_1405.sqlite"
            json_file = home / ".smart_alloc" / "user_settings.json"
            ini_file = base / "synthetic-preferences.ini"
            external = base / "external-profile-synthetic.xlsx"
            external.write_bytes(b"synthetic-external-file-only-no-real-person-data")
            external_sha = checksum(external)
            env = os.environ.copy()
            env.update({
                "HOME": str(home), "USERPROFILE": str(home),
                "APPDATA": str(base / "appdata"),
                "LOCALAPPDATA": str(base / "localappdata"),
                "TEMP": str(base / "temp"), "TMP": str(base / "temp"),
                "QT_QPA_PLATFORM": "offscreen",
                "MATRIX_CI_SMOKE_CLOSE_MS": "1400",
                "MATRIX_TEST_INI": str(ini_file),
                "MATRIX_TEST_DB": str(db_path),
            })

            def personal(operation: str, *args: str, ok: bool = True,
                         settings: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
                e = env | (settings or {})
                response = run(["cmd.exe", "/d", "/c", "call", "Matrix-Personal.cmd",
                                operation, *args], cwd=client, env=e, ok=ok)
                if not ok:
                    assert "PERSONAL RELEASE FAILED" in response.stderr
                return response

            def state() -> dict:
                return json.loads(personal("status").stdout)

            def python_in(worktree: Path, script: str, *, ok: bool = True) -> None:
                run(["uv", "run", "--no-sync", "--locked", "python", "-c", script],
                    cwd=worktree, env=env, ok=ok)

            def worktree(tag: str, sha: str) -> Path:
                loc = client / ".matrix-personal" / "versions" / f"{tag}--{sha[:12]}"
                assert git(loc, "rev-parse", "HEAD") == sha
                return loc

            old_activation = personal("activate", old_tag)
            assert f"ACTIVE {old_tag} {old_commit}" in old_activation.stdout
            previous_state = state()
            assert previous_state["current"]["sha"] == old_commit
            assert previous_state["current"]["tag"] == old_tag
            assert previous_state["previous"] is None
            old_dir = worktree(old_tag, old_commit)
            personal("start")
            passed("BASELINE", "real old tag/commit, status, worktree and app.main start")

            # Create real v0.1.0 LocalDatabase schema and FK-linked records.
            seed_script = """
import os
from datetime import UTC, datetime
from pathlib import Path
from app.infra.local_database import LocalDatabase, RunRecord, RunMetricRow
from PySide6.QtCore import QSettings
db = LocalDatabase(Path(os.environ['MATRIX_TEST_DB']))
db.initialize()
now = datetime.now(UTC)
rec = RunRecord('d4-upgrade-synthetic', now, now, 'synthetic', 'synthetic',
    'allocate', None, None, '{}', '{}', 1, 1, 0, None, None, 'success', None)
id_ = db.insert_run(rec)
db.insert_run_metrics([RunMetricRow(id_, 'D4.synthetic', 1.0)])
db.close_all_connections()
native = QSettings('YourOrganization', 'MentorAllocation')
native.setValue('ci/d4-two-version', 'preserved')
native.sync()
assert native.status() == QSettings.Status.NoError
ini = QSettings(os.environ['MATRIX_TEST_INI'], QSettings.Format.IniFormat)
ini.setValue('ci/d4-two-version', 'preserved')
ini.sync()
assert ini.status() == QSettings.Status.NoError
"""
            python_in(old_dir, seed_script)
            json_file.write_text('{"d4_user_setting":"preserved"}\n', encoding="utf-8")
            baseline = semantic(db_path)
            assert baseline["integrity"] == "ok" and baseline["foreign_keys"] == []
            assert baseline["schema"] == 13
            assert baseline["runs"] == [("d4-upgrade-synthetic", "success")]
            assert baseline["metrics"] == [("D4.synthetic", 1.0)]
            passed("PERSISTED_BASELINE", "v0.1.0 real schema, run + FK metric, JSON, native and INI settings")

            # N1: a dirty controller checkout cannot update or clean private state.
            readme = client / "README.md"
            original_readme = readme.read_bytes()
            readme.write_bytes(original_readme + b"\nCI-DIRTY")
            personal("activate", candidate_tag, ok=False)
            assert state() == previous_state and readme.read_bytes().endswith(b"CI-DIRTY")
            assert semantic(db_path) == baseline
            readme.write_bytes(original_readme)
            assert git(client, "status", "--porcelain=v1") == ""
            passed("N1", "dirty checkout refused; active tag/data and tracked mutation preserved")

            # N2 + N3: invalid, missing, lightweight and wrongly-versioned annotated tags.
            personal("activate", "bad-version", ok=False)
            personal("activate", "v9.9.9", ok=False)
            git(seed, "tag", "v0.9.0")
            git(seed, "push", "origin", "refs/tags/v0.9.0")
            personal("activate", "v0.9.0", ok=False)
            passed("N2", "missing, malformed and lightweight tags refused")
            git(seed, "tag", "-a", "v0.2.1", "-m", "DISPOSABLE MISMATCH")
            git(seed, "push", "origin", "refs/tags/v0.2.1")
            personal("activate", "v0.2.1", ok=False)
            assert state() == previous_state
            passed("N3", "annotated tag/version mismatch rejected before activation")

            # N4: genuine uv sync rejection under an empty offline dependency cache.
            offline = personal("activate", candidate_tag, ok=False, settings={
                "UV_CACHE_DIR": str(base / "empty-offline-uv-cache"), "UV_OFFLINE": "1",
            })
            assert "uv sync" in offline.stderr, (
                "offline failure was not attributable to the uv sync step"
            )
            assert state() == previous_state
            passed("N4", "actual uv sync failed offline; previous active release preserved")

            # N5/N6: an invalid SQLite file causes the real online-backup prerequisite to fail.
            bad = years / "broken.sqlite"
            bad.write_bytes(b"controlled-invalid-sqlite")
            backup_failure = personal("activate", candidate_tag, ok=False)
            assert "PERSONAL RELEASE FAILED" in backup_failure.stderr
            assert bad.read_bytes() == b"controlled-invalid-sqlite"
            assert state() == previous_state and semantic(db_path) == baseline
            bad.unlink()  # Synthetic test file only, never real user data.
            passed("N5", "backup prerequisite failed without changing active version")
            passed("N6", "invalid SQLite rejected without deleting the source database")

            personal("activate", candidate_tag)
            upgraded = state()
            assert upgraded["current"] == {
                "tag": candidate_tag, "sha": expected, "version": version, "python": pin,
            }
            assert upgraded["previous"] == previous_state["current"]
            new_dir = worktree(candidate_tag, expected)
            assert checksum(new_dir / "uv.lock") == checksum(root / "uv.lock")
            assert old_dir.is_dir() and git(old_dir, "rev-parse", "HEAD") == old_commit
            assert git(client, "cat-file", "-t", f"refs/tags/{candidate_tag}") == "tag"
            assert git(client, "rev-parse", f"refs/tags/{candidate_tag}^{{commit}}") == expected
            personal("start")
            personal("start")  # Real second start: persisted state must survive restart.
            assert semantic(db_path) == baseline
            assert json.loads(json_file.read_text(encoding="utf-8")) == {
                "d4_user_setting": "preserved",
            }
            python_in(new_dir, """
import os
from PySide6.QtCore import QSettings
native = QSettings('YourOrganization', 'MentorAllocation')
native.sync()
assert native.value('ci/d4-two-version') == 'preserved'
ini = QSettings(os.environ['MATRIX_TEST_INI'], QSettings.Format.IniFormat)
ini.sync()
assert ini.value('ci/d4-two-version') == 'preserved'
""")
            assert external_sha == checksum(external)
            passed("UPGRADE", "real Git+uv activation, distinct candidate worktree and two app.main launches")
            passed("PERSISTENCE", "SQLite integrity/FK/rows, JSON, INI, native Windows QSettings, external hash")
            passed("WORKTREES", "old source worktree retained with exact released commit")

            # A fresh copy of the real pre-activation backup can be recovered, separately.
            backups = sorted((client / ".matrix-personal" / "backups").iterdir())
            valid_backups = [b for b in backups if (b / db_path.name).is_file()]
            assert valid_backups
            restore_copy = base / "restored-copy.sqlite"
            with closing(sqlite3.connect(valid_backups[-1] / db_path.name)) as source:
                with closing(sqlite3.connect(restore_copy)) as dest:
                    source.backup(dest)
            assert semantic(restore_copy) == baseline
            passed("RECOVERY", "SQLite preactivation backup restored into separate synthetic copy")

            # N7: the semantic oracle actually catches relationship/data changes.
            modified_copy = base / "modified-copy.sqlite"
            shutil.copy2(db_path, modified_copy)
            with closing(sqlite3.connect(modified_copy)) as db:
                db.execute("UPDATE runs SET status='corrupted' WHERE run_uuid='d4-upgrade-synthetic'")
                db.commit()
            assert semantic(modified_copy) != baseline
            assert semantic(db_path) == baseline
            passed("N7", "intentional record mutation detected; candidate DB unchanged")

            # N8: code rollback does not repair deliberately incompatible schema state.
            incompatible = base / "incompatible-copy.sqlite"
            shutil.copy2(db_path, incompatible)
            with closing(sqlite3.connect(incompatible)) as db:
                db.execute("UPDATE schema_meta SET schema_version=999 WHERE id=1")
                db.commit()
            assert semantic(incompatible)["schema"] == 999
            incompatible_env = env | {"MATRIX_TEST_DB": str(incompatible)}
            refusal = run(["uv", "run", "--no-sync", "--locked", "python", "-c",
                "import os; from pathlib import Path; "
                "from app.infra.local_database import LocalDatabase; "
                "LocalDatabase(Path(os.environ['MATRIX_TEST_DB'])).initialize()"],
                cwd=old_dir, env=incompatible_env, ok=False)
            assert refusal.returncode != 0 and semantic(incompatible)["schema"] == 999
            personal("rollback")
            rolled = state()
            assert rolled["current"] == previous_state["current"]
            assert rolled["previous"] is None
            assert semantic(db_path) == baseline
            passed("N8", "old code selection succeeds; incompatible copied schema is still incompatible")
            passed("ROLLBACK", "old code reselected; data restoration not implied or performed")

            evidence["conclusion"] = "PASS"
            print("PUBLISHED TWO-VERSION WINDOWS UPGRADE PASS", old_commit, expected)
    except Exception as exc:
        evidence["failure"] = {"type": type(exc).__name__, "detail": str(exc)[-600:]}
        raise
    finally:
        (report_dir / "two-version-upgrade.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

if __name__ == "__main__":
    sys.exit(main())
