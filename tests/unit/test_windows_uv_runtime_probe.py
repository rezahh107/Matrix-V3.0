"""Regression tests for real filesystem qualification in the Windows uv probe."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infra.logging import _resolve_logging_paths
from tools.ci import probe_windows_uv_runtime as probe

PREFIX = ".matrix-uv-io-"


def _assert_no_probe_files(*directories: Path) -> None:
    for directory in directories:
        assert not list(directory.glob(f"{PREFIX}*"))


def _set_distinct_storage_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path, Path]:
    """Keep actual cwd logging distinct from the user-home/crash-log directories."""

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    user_dir, crash_logs = tmp_path / "user-home", tmp_path / "user-home" / "logs"
    user_dir.mkdir()
    crash_logs.mkdir()
    monkeypatch.setattr(probe, "get_user_data_dir", lambda: user_dir)
    monkeypatch.setattr(probe, "get_log_directory", lambda: crash_logs)
    operational_logs, error_reports = _resolve_logging_paths()
    assert operational_logs == workspace / "logs"
    assert error_reports == workspace / "logs" / "errors"
    assert operational_logs != crash_logs
    return user_dir, crash_logs, operational_logs, error_reports


def test_existing_directory_is_not_proof_of_writability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduce the old false-positive with a denied create operation."""

    directory = tmp_path / "existing"
    directory.mkdir()
    assert directory.is_dir()  # Old code incorrectly treated this as success.

    def deny_create(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("simulated Windows directory access denial")

    monkeypatch.setattr(probe.tempfile, "NamedTemporaryFile", deny_create)
    with pytest.raises(RuntimeError, match="directory I/O qualification failed"):
        probe._verify_directory_io(directory)
    _assert_no_probe_files(directory)


def test_all_real_destinations_complete_io_without_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_dir, crash_logs, operational_logs, error_reports = _set_distinct_storage_paths(
        tmp_path, monkeypatch
    )
    # Operational directories start absent, as in a fresh checkout.
    assert not operational_logs.exists()

    seen: list[Path] = []
    real_factory = probe.tempfile.NamedTemporaryFile

    def track_create(*args: object, **kwargs: object):
        seen.append(Path(kwargs["dir"]))
        return real_factory(*args, **kwargs)

    monkeypatch.setattr(probe.tempfile, "NamedTemporaryFile", track_create)
    probe._verify_application_directories()
    assert seen == [user_dir, crash_logs, operational_logs, error_reports]
    assert operational_logs.is_dir() and error_reports.is_dir()
    _assert_no_probe_files(user_dir, crash_logs, operational_logs, error_reports)


@pytest.mark.parametrize(
    "denied_location", ["user_home", "crash_logs", "operational_logs", "error_reports"]
)
def test_each_actual_destination_denial_fails_qualification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, denied_location: str
) -> None:
    """A passing home probe must not conceal denied cwd logs (or vice versa)."""

    destinations = _set_distinct_storage_paths(tmp_path, monkeypatch)
    user_dir, crash_logs, operational_logs, error_reports = destinations
    denied_dir = dict(zip(
        ("user_home", "crash_logs", "operational_logs", "error_reports"),
        destinations,
        strict=True,
    ))[denied_location]
    real_factory = probe.tempfile.NamedTemporaryFile
    seen: list[Path] = []

    def refuse_selected(*args: object, **kwargs: object):
        location = Path(kwargs["dir"])
        seen.append(location)
        if location == denied_dir:
            raise PermissionError("simulated filesystem write denial")
        return real_factory(*args, **kwargs)

    monkeypatch.setattr(probe.tempfile, "NamedTemporaryFile", refuse_selected)
    with pytest.raises(RuntimeError, match="directory I/O qualification failed"):
        probe._verify_application_directories()

    assert denied_dir in seen  # A same-root-only probe could never satisfy this.
    assert seen == list(destinations)[: destinations.index(denied_dir) + 1]
    assert user_dir.is_dir() and crash_logs.is_dir()
    assert operational_logs.is_dir() and error_reports.is_dir()
    _assert_no_probe_files(*destinations)


class _FaultyTemporaryFile:
    def __init__(self, actual, failure: str):
        self.actual = actual
        self.failure = failure

    def __enter__(self):
        self.actual.__enter__()
        return self

    def __exit__(self, *args):
        result = self.actual.__exit__(*args)
        if self.failure == "cleanup":
            raise OSError("simulated cleanup error after removing file")
        return result

    def __getattr__(self, name: str):
        return getattr(self.actual, name)

    def write(self, data: bytes) -> int:
        if self.failure == "write":
            raise PermissionError("simulated write failure")
        return self.actual.write(data)

    def read(self, *args):
        if self.failure == "read":
            return b"incorrect-read-back"
        return self.actual.read(*args)


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("write", "directory I/O qualification failed"),
        ("read", "Directory probe read-back mismatch"),
        ("cleanup", "directory I/O qualification failed"),
    ],
)
def test_write_read_and_cleanup_errors_fail_without_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str, message: str
) -> None:
    directory = tmp_path / "app"
    directory.mkdir()
    real_factory = probe.tempfile.NamedTemporaryFile

    def make_faulty(*args: object, **kwargs: object):
        return _FaultyTemporaryFile(real_factory(*args, **kwargs), failure)

    monkeypatch.setattr(probe.tempfile, "NamedTemporaryFile", make_faulty)
    with pytest.raises(RuntimeError, match=message):
        probe._verify_directory_io(directory)
    _assert_no_probe_files(directory)
