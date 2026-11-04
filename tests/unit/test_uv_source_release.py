"""Fail-closed source candidate guards using disposable, synthetic Git repositories."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tools.ci import qualify_uv_source as candidate_builder
from tools.ci.qualify_uv_source import (
    REQUIRED_FILES,
    RUNTIME_PATHS,
    build_candidate,
    validate_version_identity,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.DEVNULL)


def _synthetic_repo(root: Path) -> None:
    _git(root, "init")
    # Avoid host-level core.autocrlf rewriting the disposable fixture on Windows.
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "config", "user.email", "candidate-test@example.invalid")
    _git(root, "config", "user.name", "Synthetic CI")
    required = set(REQUIRED_FILES)
    required.update(
        path for path in RUNTIME_PATHS
        if Path(path).suffix or path in {".python-version", "Launch_Matrix3.cmd"}
    )
    required.update({"policy/policy_schema.json", "tools/ci/probe_windows_uv_runtime.py"})
    for path in sorted(required):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic test fixture\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "smart-student-allocation"\n'
        'version = "0.1.0"\nrequires-python = ">=3.11"\n', encoding="utf-8"
    )
    (root / "uv.lock").write_text(
        'version = 1\nrequires-python = ">=3.11"\n'
        '[[package]]\nname = "smart-student-allocation"\n'
        'version = "0.1.0"\nsource = { editable = "." }\n', encoding="utf-8"
    )
    (root / ".python-version").write_text("3.11\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n## [Unreleased]\n"
        "## Historical entry: 1.0.0 (unverified)\n", encoding="utf-8"
    )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "Synthetic fixture")


def test_archive_provenance_version_and_privacy_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_repo(tmp_path)
    # Even when intentionally tracked, root inputs and Golden fixtures are not
    # runtime sources and must not leak into the downloadable candidate.
    (tmp_path / "students.xlsx").write_bytes(b"synthetic spreadsheet placeholder")
    golden = tmp_path / "tests/golden/personal.csv"
    golden.parent.mkdir(parents=True, exist_ok=True)
    golden.write_text("synthetic,data\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "Private-looking data outside allowlist")
    monkeypatch.chdir(tmp_path)
    manifest = build_candidate(tmp_path / "candidate")
    archive = tmp_path / "candidate" / str(manifest["archive"])
    assert manifest["candidate_package_version_not_official_release"] == "0.1.0"
    assert manifest["python_version"] == "3.11"
    assert manifest["source_sha"] == subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    assert manifest["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert sorted(p.name for p in (tmp_path / "candidate").iterdir()) == sorted(
        [archive.name, "candidate-manifest.json"]
    )
    on_disk = json.loads((tmp_path / "candidate" / "candidate-manifest.json").read_text(
        encoding="utf-8"
    ))
    assert on_disk == manifest
    expected = {}
    tracked = subprocess.check_output(
        ["git", "ls-tree", "-r", "-z", "HEAD", "--", *RUNTIME_PATHS], cwd=tmp_path
    )
    for entry in tracked.split(b"\0"):
        if not entry:
            continue
        meta, filename = entry.split(b"\t", 1)
        expected[filename.decode("utf-8")] = meta.split()[-1].decode("ascii")
    with zipfile.ZipFile(archive) as zipped:
        assert {entry.filename for entry in zipped.infolist() if not entry.is_dir()} == set(expected)
        assert set(manifest["archive_files"]) == set(expected)
        for name, blob_sha in expected.items():
            content = zipped.read(name)
            assert hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest() == blob_sha

    assert manifest["publication"] == "NOT_AUTHORIZED"
    assert manifest["privacy_status"] == "REVIEW_REQUIRED_BEFORE_PUBLICATION"
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert "app/main.py" in zipped.namelist()
        assert "students.xlsx" not in zipped.namelist()
        assert "tests/golden/personal.csv" not in zipped.namelist()


def test_lock_package_version_drift_blocks_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_repo(tmp_path)
    (tmp_path / "uv.lock").write_text(
        'version = 1\nrequires-python = ">=3.11"\n'
        '[[package]]\nname = "smart-student-allocation"\n'
        'version = "9.9.9"\n', encoding="utf-8"
    )
    _git(tmp_path, "add", "uv.lock")
    _git(tmp_path, "commit", "-m", "Wrong lock")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="uv.lock project version"):
        build_candidate(tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()
    assert not list(tmp_path.glob(".candidate.staging-*"))



@pytest.mark.parametrize("unsafe_name", ["app/students.xlsx", "app/.env", "app/id_rsa"])
def test_tracked_sensitive_file_names_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsafe_name: str
) -> None:
    _synthetic_repo(tmp_path)
    target = tmp_path / unsafe_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("synthetic only\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "Unintended tracked input")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="Unsafe source candidate"):
        build_candidate(tmp_path / "candidate")


def test_historical_version_cannot_pass_official_release_gate() -> None:
    project = (
        b'[project]\nname = "smart-student-allocation"\n'
        b'version = "0.1.0"\nrequires-python = ">=3.11"\n'
    )
    lock = (
        b'version = 1\nrequires-python = ">=3.11"\n'
        b'[[package]]\nname = "smart-student-allocation"\nversion = "0.1.0"\n'
    )
    history = b"## [Unreleased]\n## Historical entry: 1.0.0\n"
    with pytest.raises(RuntimeError, match="differs from package"):
        validate_version_identity(project, lock, b"3.11\n", history,
                                  required_release_version="1.0.0")
    with pytest.raises(RuntimeError, match="no dated changelog"):
        validate_version_identity(project, lock, b"3.11\n", history,
                                  required_release_version="0.1.0")
    approved_section = history + b"## [0.1.0] - 2026-11-04\n"
    assert validate_version_identity(
        project, lock, b"3.11\n", approved_section,
        required_release_version="0.1.0"
    ) == ("0.1.0", "3.11")


def test_secret_inside_allowed_python_file_blocks_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_repo(tmp_path)
    # Synthetic, deliberately PAT-shaped bytes; no real credential.
    (tmp_path / "app/main.py").write_bytes(b"key = 'ghp_" + b"A" * 36 + b"'\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "Unsafe secret fixture")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="Potential credential in archive source"):
        build_candidate(tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()
    assert not list(tmp_path.glob(".candidate.staging-*"))



def test_failed_post_archive_version_gate_leaves_no_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="no dated changelog entry"):
        build_candidate(tmp_path / "candidate", required_release_version="0.1.0")
    assert not (tmp_path / "candidate").exists()
    assert not list(tmp_path.glob(".candidate.staging-*"))


@pytest.mark.parametrize(
    ("python_pin", "should_pass"),
    [
        ("3.10", False),
        ("3.10.12", False),
        ("3.11", True),
        ("3.11.0", True),
        ("3.12", True),
        ("3.12.4", True),
    ],
)
def test_python_pin_satisfies_minimum_requirement(
    python_pin: str, should_pass: bool
) -> None:
    project, lock, history = _version_fixture()
    if should_pass:
        assert validate_version_identity(
            project, lock, python_pin.encode(), history
        ) == ("0.1.0", python_pin)
    else:
        with pytest.raises(RuntimeError, match="does not satisfy"):
            validate_version_identity(project, lock, python_pin.encode(), history)


@pytest.mark.parametrize(
    "requires_python",
    [">3.11", "~=3.11", ">=3.11,<4", ">=3.11.0", ">= 3.11", ">=3.*", ">=03.11", ">=3.11;os_name"],
)
def test_unsupported_or_ambiguous_requirement_rejected(requires_python: str) -> None:
    project, lock, history = _version_fixture(requires_python)
    with pytest.raises(RuntimeError, match="Unsupported requires-python"):
        validate_version_identity(project, lock, b"3.12", history)


def _version_fixture(
    minimum: str = ">=3.11",
) -> tuple[bytes, bytes, bytes]:
    project = (
        '[project]\nname = "smart-student-allocation"\n'
        'version = "0.1.0"\nrequires-python = "' + minimum + '"\n'
    )
    lock = (
        'version = 1\nrequires-python = "' + minimum + '"\n'
        '[[package]]\nname = "smart-student-allocation"\n'
        'version = "0.1.0"\n'
    )
    return project.encode(), lock.encode(), b"## [Unreleased]\n"


def test_python_pin_failure_after_archive_removes_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_repo(tmp_path)
    (tmp_path / ".python-version").write_text("3.10\n", encoding="utf-8")
    _git(tmp_path, "add", ".python-version")
    _git(tmp_path, "commit", "-m", "Unsupported Python pin")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="does not satisfy"):
        build_candidate(tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()
    assert not list(tmp_path.glob(".candidate.staging-*"))


def test_manifest_write_interruption_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    real_write = Path.write_text

    def interrupt_manifest(self: Path, data: str, *args: object, **kwargs: object) -> int:
        if self.name == "candidate-manifest.json":
            raise OSError("synthetic manifest interruption")
        return real_write(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", interrupt_manifest)
    with pytest.raises(OSError, match="synthetic manifest interruption"):
        build_candidate(tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()
    assert not list(tmp_path.glob(".candidate.staging-*"))


def test_stage_promotion_interruption_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    def reject_promotion(source: Path, destination: Path) -> None:
        raise OSError("synthetic rename interruption")

    monkeypatch.setattr(candidate_builder, "_promote_staging", reject_promotion)
    with pytest.raises(OSError, match="synthetic rename interruption"):
        build_candidate(tmp_path / "candidate")
    assert not (tmp_path / "candidate").exists()
    assert not list(tmp_path.glob(".candidate.staging-*"))


def test_destination_occupied_during_atomic_promotion_is_not_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _synthetic_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "candidate"
    real_promote = candidate_builder._promote_staging

    def occupy_destination(source: Path, target: Path) -> None:
        target.mkdir()  # Another process creates the target after the last check.
        real_promote(source, target)

    monkeypatch.setattr(candidate_builder, "_promote_staging", occupy_destination)
    with pytest.raises(FileExistsError):
        build_candidate(destination)
    assert destination.is_dir()
    assert list(destination.iterdir()) == []
    assert not list(tmp_path.glob(".candidate.staging-*"))


@pytest.mark.skipif(sys.platform != "linux", reason="requires native Linux renameat2")
@pytest.mark.parametrize("occupant_kind", ["file", "symlink"])
def test_linux_noreplace_preserves_racing_file_or_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, occupant_kind: str
) -> None:
    """Exercise the real Linux syscall after the initial destination check."""
    _synthetic_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "candidate"
    original_promote = candidate_builder._promote_staging
    sentinel = b"synthetic competing owner"

    def occupy_then_promote(staging: Path, target: Path) -> None:
        if occupant_kind == "file":
            target.write_bytes(sentinel)
        else:
            target.symlink_to("missing-synthetic-target")
        original_promote(staging, target)

    monkeypatch.setattr(candidate_builder, "_promote_staging", occupy_then_promote)
    with pytest.raises(FileExistsError):
        build_candidate(destination)
    if occupant_kind == "file":
        assert destination.is_file()
        assert destination.read_bytes() == sentinel
    else:
        assert destination.is_symlink()
        assert destination.readlink() == Path("missing-synthetic-target")
    assert not list(tmp_path.glob(".candidate.staging-*"))


@pytest.mark.parametrize("occupied", [False, True])
def test_destination_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, occupied: bool
) -> None:
    _synthetic_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "candidate"
    destination.mkdir()
    if occupied:
        (destination / "keep.txt").write_text("DO NOT OVERWRITE", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_candidate(destination)
    assert destination.is_dir()
    assert sorted(p.name for p in destination.iterdir()) == (
        ["keep.txt"] if occupied else []
    )
    assert not list(tmp_path.glob(".candidate.staging-*"))
