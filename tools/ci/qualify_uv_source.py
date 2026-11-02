"""Create and verify a privacy-bounded, exact-commit uv source candidate.

This is preparation only. It never creates a tag or GitHub Release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tomllib
import zipfile
from pathlib import Path

# Only version-controlled runtime sources/configuration and minimal launch/docs.
# In particular, never archive tracked personal/sample Excel files in the root.
RUNTIME_PATHS = (
    "app",
    "config",
    "resources",
    "policy",
    "educational_master.ssot.yaml",
    "educational_validation_rules.yaml",
    "policy.yaml",
    "policy_sample.yaml",
    ".python-version",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "CHANGELOG.md",
    "run_gui.py",
    "Launch_Matrix3.cmd",
    "tools/ci",
    "tests/infra/test_cli_database_preparation.py",
    "tests/integration/test_build_matrix_school_expansion.py",
    "tests/integration/test_groupcode_runtime_authority.py",
    "tests/test_excel_export_smoke.py",
)
REQUIRED_FILES = {
    "app/main.py",
    "app/ui/main_window.py",
    "app/ui/assets/font_data_vazirmatn.py",
    "app/ui/styles.qss",
    "config/policy.json",
    "resources/translations/ui_texts.json",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "README.md",
    "CHANGELOG.md",
    "tests/test_excel_export_smoke.py",
    "tests/infra/test_cli_database_preparation.py",
    "tests/integration/test_build_matrix_school_expansion.py",
    "tests/integration/test_groupcode_runtime_authority.py",
}
SAFE_QUALIFICATION_TESTS = {"tests/infra/test_cli_database_preparation.py", "tests/integration/test_build_matrix_school_expansion.py", "tests/test_excel_export_smoke.py"}
REJECTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".sqlite", ".db", ".pem", ".key"}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def build_candidate(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_sha = git("rev-parse", "HEAD").decode().strip()
    # Compare archive bytes against exact Git *blob objects*, not git-show text
    # streams (which can differ under Windows console newline translation).
    entries = git("ls-tree", "-r", "-z", "HEAD", "--", *RUNTIME_PATHS)
    expected_blobs: dict[str, str] = {}
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        mode, kind, object_id = metadata.split(b" ", 2)
        if kind != b"blob":
            raise RuntimeError(f"Unsupported Git tree entry: {path_bytes!r}")
        expected_blobs[path_bytes.decode("utf-8")] = object_id.decode("ascii")
    expected_paths = set(expected_blobs)
    missing = REQUIRED_FILES - expected_paths
    if missing:
        raise RuntimeError(f"Required runtime files missing: {sorted(missing)}")
    forbidden = sorted(
        path for path in expected_paths
        if Path(path).suffix.lower() in REJECTED_EXTENSIONS or
        (path.startswith("tests/") and path not in SAFE_QUALIFICATION_TESTS)
        or path.startswith(("ci/golden_datasets/", "evidence/"))
    )
    if forbidden:
        raise RuntimeError(f"Unsafe source candidate entries: {forbidden}")

    archive = output_dir / f"matrix-uv-source-{source_sha[:12]}.zip"
    subprocess.run(
        ["git", "archive", "--format=zip", f"--output={archive}", "HEAD",
         "--", *RUNTIME_PATHS],
        check=True,
    )
    with zipfile.ZipFile(archive) as source:
        if source.testzip():
            raise RuntimeError("ZIP CRC verification failed")
        archived_paths = {entry.filename for entry in source.infolist() if not entry.is_dir()}
        if archived_paths != expected_paths:
            raise RuntimeError(
                f"Archive file list mismatch: missing={sorted(expected_paths - archived_paths)}, "
                f"unexpected={sorted(archived_paths - expected_paths)}"
            )
        # Git's immutable tree is the authority for all content, not filenames alone.
        for name in sorted(expected_paths):
            data = source.read(name)
            header = f"blob {len(data)}\0".encode()
            archive_blob = hashlib.sha1(header + data).hexdigest()
            if archive_blob != expected_blobs[name]:
                raise RuntimeError(
                    f"Archive blob differs from reviewed Git tree: {name} "
                    f"(archive {archive_blob}; tree {expected_blobs[name]})"
                )

    with zipfile.ZipFile(archive) as source:
        pyproject_bytes = source.read("pyproject.toml")
        lock_bytes = source.read("uv.lock")
    config = tomllib.loads(pyproject_bytes.decode("utf-8"))
    version = config["project"]["version"]
    if not isinstance(version, str) or not version:
        raise RuntimeError("Package version missing")
    manifest = {
        "source_sha": source_sha,
        "candidate_package_version_not_official_release": version,
        "archive": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "uv_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "files_checked_against_git_tree": len(expected_paths),
        "publication": "NOT_AUTHORIZED",
    }
    (output_dir / "candidate-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_candidate(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
