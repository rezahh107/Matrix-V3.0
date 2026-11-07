"""Owner-selected Git tag installations; no tag creation or publishing.

Each approved tag gets an isolated worktree and uv environment. State is switched
only after source/lock verification, synchronization and an import probe. No old
worktree, personal file or database is deleted by this command.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from tools.ci.qualify_uv_source import validate_version_identity

TAG_PATTERN = re.compile(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
RECORD_PATTERN = re.compile(r"v\d+\.\d+\.\d+--[a-f0-9]{12}\Z")


class ReleaseError(RuntimeError):
    """Fail closed, preserving the previously selected worktree."""


def command(args: list[str], *, cwd: Path, capture: bool = True) -> str:
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=capture,
                                check=True)
        return result.stdout.strip() if capture else ""
    except (OSError, subprocess.CalledProcessError) as exc:
        # Avoid echoing command output, which could contain private file paths/data.
        raise ReleaseError(f"Command failed: {args[0]} {args[1] if len(args)>1 else ''}") from exc


def git(repo: Path, *args: str) -> str:
    return command(["git", *args], cwd=repo)


def check_clean(repo: Path) -> None:
    if git(repo, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ReleaseError(f"Local edits/untracked files in {repo}; move or back them up first")


def validate_checkout(repo: Path) -> None:
    if Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo.resolve():
        raise ReleaseError("--repo must name the top-level Git checkout")
    if git(repo, "remote", "get-url", "origin").strip() == "":
        raise ReleaseError("Git origin is missing")


def validate_tag(repo: Path, tag: str, *, fetch: bool) -> dict[str, str]:
    match = TAG_PATTERN.fullmatch(tag)
    if not match:
        raise ReleaseError("Select an explicit approved tag shaped vMAJOR.MINOR.PATCH")
    if fetch:
        # Only fetch this exact version, never auto-follow latest or rewrite tags.
        git(repo, "fetch", "--no-tags", "origin", f"refs/tags/{tag}:refs/tags/{tag}")
    if git(repo, "cat-file", "-t", f"refs/tags/{tag}") != "tag":
        raise ReleaseError("Only annotated, immutable release tags are supported")
    sha = git(repo, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    def blob(path: str) -> bytes:
        # Git files are authoritative, not potentially edited working-tree files.
        try:
            return subprocess.check_output(["git", "show", f"{sha}:{path}"], cwd=repo)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ReleaseError(f"Tagged release missing required file: {path}") from exc
    version, python_pin = validate_version_identity(
        blob("pyproject.toml"), blob("uv.lock"), blob(".python-version"),
        blob("CHANGELOG.md"), required_release_version=match.group(0)[1:],
    )
    if version != tag[1:]:
        raise ReleaseError("Tag name and application version disagree")
    return {"tag": tag, "sha": sha, "python": python_pin, "version": version}


def paths(repo: Path) -> tuple[Path, Path]:
    control = repo / ".matrix-personal"
    if control.is_symlink():
        raise ReleaseError("Refusing symlinked personal release state directory")
    if any((control / name).is_symlink() for name in ("versions", "backups")):
        raise ReleaseError("Refusing symlinked personal release versions/backups")
    return control, control / "state.json"


@contextmanager
def operation_guard(repo: Path):
    """Exclude overlapping activate, rollback and start operations.

    A crashed process may leave the lock directory behind. Deliberately do not
    remove it automatically: an operator must confirm no process remains.
    """
    validate_checkout(repo)
    control, _ = paths(repo)
    control.mkdir(parents=True, exist_ok=True)
    marker = control / ".operation-lock"
    try:
        marker.mkdir()
    except FileExistsError as exc:
        raise ReleaseError(
            "Another Matrix operation is running, or a stale operation lock exists. "
            "Close Matrix, verify no helper is running, then inspect "
            ".matrix-personal/.operation-lock before removing it manually."
        ) from exc
    try:
        yield
    finally:
        marker.rmdir()


def validate_release_record(record: object) -> None:
    """Validate persisted release identity without accessing Git or user files."""
    if not isinstance(record, dict) or set(record) != {"tag", "sha", "version", "python"}:
        raise ReleaseError("Invalid installed release record")
    tag, sha, version, python = (record[key] for key in ("tag", "sha", "version", "python"))
    if not isinstance(tag, str) or TAG_PATTERN.fullmatch(tag) is None:
        raise ReleaseError("Invalid installed tag")
    if not isinstance(sha, str) or re.fullmatch(r"[a-f0-9]{40}", sha) is None:
        raise ReleaseError("Invalid installed SHA")
    if not isinstance(version, str) or version != tag[1:]:
        raise ReleaseError("Invalid installed version")
    if not isinstance(python, str) or re.fullmatch(
        r"(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?", python
    ) is None:
        raise ReleaseError("Invalid installed Python pin")


def _unique_state_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate release state key")
        result[key] = value
    return result


def read_state(state_file: Path) -> dict:
    if state_file.is_symlink():
        raise ReleaseError("Refusing symlinked personal release state")
    if not state_file.exists():
        return {"current": None, "previous": None}
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"),
                           object_pairs_hook=_unique_state_object)
    except (ValueError, OSError) as exc:
        raise ReleaseError("Release state is invalid; no change made") from exc
    if not isinstance(state, dict) or set(state) != {"current", "previous"}:
        raise ReleaseError("Release state has unexpected keys")
    for key in ("current", "previous"):
        if state[key] is not None:
            validate_release_record(state[key])
    if state["current"] is None and state["previous"] is not None:
        raise ReleaseError("Previous release requires a current release")
    if state["previous"] is not None and (
        state["current"]["tag"] == state["previous"]["tag"]
        or state["current"]["sha"] == state["previous"]["sha"]
    ):
        raise ReleaseError("Current and previous must identify distinct releases")
    return state


def record_dir(repo: Path, record: dict) -> Path:
    validate_release_record(record)
    tag, sha = record["tag"], record["sha"]
    name = f"{tag}--{sha[:12]}"
    if not RECORD_PATTERN.fullmatch(name):
        raise ReleaseError("Unsafe installed worktree name")
    target = repo / ".matrix-personal" / "versions" / name
    if target.is_symlink() or not target.is_dir():
        raise ReleaseError("Installed worktree missing or symlinked")
    if git(target, "rev-parse", "HEAD") != sha:
        raise ReleaseError("Installed worktree HEAD changed")
    return target


def verify_record(repo: Path, record: dict, *, clean: bool = True) -> Path:
    target = record_dir(repo, record)
    if clean:
        check_clean(target)
    checked = validate_tag(repo, record["tag"], fetch=False)
    if checked != record:
        raise ReleaseError("Installed tag identity changed")
    return target


def atomic_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(filename, path)
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


def backup_local_data(repo: Path, old_tag: str, new_tag: str) -> Path:
    """Non-destructive pre-activation snapshot of known DB/settings paths."""
    root = Path.home() / ".smart_alloc"
    name = f"{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}_{old_tag}_to_{new_tag}"
    dest = repo / ".matrix-personal" / "backups" / name
    dest.mkdir(parents=True, exist_ok=False)
    years = root / "years"
    if years.exists():
        if years.is_symlink() or not years.is_dir():
            raise ReleaseError("Unexpected yearly-database directory; snapshot incomplete")
        for source in sorted(years.iterdir()):
            if source.suffix.lower() not in {".sqlite", ".db"}:
                continue
            if source.is_symlink() or not source.is_file():
                raise ReleaseError("Unexpected database entry; snapshot incomplete")
            with (
                closing(sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)) as src,
                closing(sqlite3.connect(dest / source.name)) as snapshot,
            ):
                src.backup(snapshot)
    settings = root / "user_settings.json"
    if settings.exists():
        if settings.is_symlink() or not settings.is_file():
            raise ReleaseError("Unexpected settings file; snapshot incomplete")
        shutil.copy2(settings, dest / "user_settings.json")
    # Qt QSettings remains OS-managed; never alter Registry in an app update.
    # A database-schema downgrade after a new app run is NOT guaranteed safe.
    (dest / "README.txt").write_text(
        "Pre-activation copy of ~/.smart_alloc/years SQLite and user_settings.json.\n"
        "QSettings/other externally selected files are NOT included. No automatic data restore.\n",
        encoding="utf-8",
    )
    return dest


def activate(repo: Path, tag: str) -> None:
    # Do not even create the ignored operation directory for a dirty checkout.
    check_clean(repo)
    with operation_guard(repo):
        _activate_locked(repo, tag)


def _activate_locked(repo: Path, tag: str) -> None:
    validate_checkout(repo)
    check_clean(repo)
    control, state_file = paths(repo)
    state = read_state(state_file)
    current_dir = verify_record(repo, state["current"]) if state["current"] else None
    candidate = validate_tag(repo, tag, fetch=True)
    if state["current"] == candidate:
        print("Already active:", tag, candidate["sha"])
        return
    version_dir = control / "versions" / f"{tag}--{candidate['sha'][:12]}"
    if version_dir.is_symlink():
        raise ReleaseError("Candidate worktree is a symlink")
    if version_dir.exists():
        if version_dir != verify_record(repo, candidate):
            raise ReleaseError("Candidate directory mismatch")
    else:
        version_dir.parent.mkdir(parents=True, exist_ok=True)
        git(repo, "worktree", "add", "--detach", "--", str(version_dir), candidate["sha"])
    check_clean(version_dir)
    command(["uv", "python", "install", candidate["python"]], cwd=version_dir, capture=False)
    command(["uv", "sync", "--locked"], cwd=version_dir, capture=False)
    # Import the actual executable module inside the new locked environment.
    command(["uv", "run", "--no-sync", "--locked", "python", "-c",
             "import app.main"], cwd=version_dir, capture=False)
    # A backup failure leaves current state/previous version untouched.
    snapshot = backup_local_data(repo,
                                 state["current"]["tag"] if state["current"] else "initial",
                                 tag)
    atomic_state(state_file, {"current": candidate, "previous": state["current"]})
    print("ACTIVE", tag, candidate["sha"], "backup:", snapshot)
    print("Previous application worktree retained:", current_dir or "none")


def rollback(repo: Path) -> None:
    with operation_guard(repo):
        _rollback_locked(repo)


def _rollback_locked(repo: Path) -> None:
    validate_checkout(repo)
    check_clean(repo)
    _, state_file = paths(repo)
    state = read_state(state_file)
    if not state["previous"] or not state["current"]:
        raise ReleaseError("No previous installed version to restore")
    verify_record(repo, state["current"])
    previous = verify_record(repo, state["previous"])
    if not (previous / ".venv").is_dir():
        raise ReleaseError("Previous locked environment missing; rollback not activated")
    command(["uv", "run", "--no-sync", "--locked", "python", "-c",
             "import app.main"], cwd=previous, capture=False)
    atomic_state(state_file, {"current": state["previous"], "previous": None})
    print("ROLLED BACK", state["previous"]["tag"], state["previous"]["sha"])
    print("Database restoration is NOT automatic; inspect pre-activation backup if needed")


def status(repo: Path) -> None:
    validate_checkout(repo)
    _, state_file = paths(repo)
    state = read_state(state_file)
    if state["current"]:
        verify_record(repo, state["current"], clean=False)
    print(json.dumps(state, indent=2))


def start(repo: Path) -> None:
    with operation_guard(repo):
        _start_locked(repo)


def _start_locked(repo: Path) -> None:
    validate_checkout(repo)
    _, state_file = paths(repo)
    current = read_state(state_file)["current"]
    if not current:
        raise ReleaseError("No approved version selected; use activate vMAJOR.MINOR.PATCH")
    target = verify_record(repo, current)
    if not (target / ".venv").is_dir():
        raise ReleaseError("Selected version has no locked environment")
    # Running an app is distinct from release activation; it may modify user data.
    result = subprocess.run(["uv", "run", "--no-sync", "--locked", "python", "-m", "app.main"],
                            cwd=target, check=False)
    if result.returncode:
        raise ReleaseError(f"Application returned nonzero exit status {result.returncode}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("operation", choices=("activate", "rollback", "status", "start"))
    parser.add_argument("version", nargs="?")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.operation == "activate":
            if args.version is None:
                raise ReleaseError("An explicit approved version is required")
            activate(repo, args.version)
        else:
            if args.version is not None:
                raise ReleaseError("Unexpected version argument")
            {"rollback": rollback, "status": status, "start": start}[args.operation](repo)
    except (ReleaseError, RuntimeError, OSError, sqlite3.Error) as exc:
        print(f"PERSONAL RELEASE FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
