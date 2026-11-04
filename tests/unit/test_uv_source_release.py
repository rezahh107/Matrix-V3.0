"""Fail-closed source candidate guards using disposable, synthetic Git repositories."""

from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

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
    monkeypatch.chdir(tmp_path)
    manifest = build_candidate(tmp_path / "candidate")
    archive = tmp_path / "candidate" / str(manifest["archive"])
    assert manifest["candidate_package_version_not_official_release"] == "0.1.0"
    assert manifest["python_version"] == "3.11"
    assert manifest["source_sha"] == subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    assert manifest["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert manifest["publication"] == "NOT_AUTHORIZED"
    assert manifest["privacy_status"] == "REVIEW_REQUIRED_BEFORE_PUBLICATION"
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert "app/main.py" in zipped.namelist()
        assert "students.xlsx" not in zipped.namelist()


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
