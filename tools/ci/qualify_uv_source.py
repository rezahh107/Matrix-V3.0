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
}
REJECTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".sqlite", ".db", ".pem", ".key"}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def build_candidate(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_sha = git("rev-parse", "HEAD").decode().strip()
    expected_paths = {
        line for line in git("ls-tree", "-r", "--name-only", "HEAD", "--", *RUNTIME_PATHS)
        .decode().splitlines() if line
    }
    missing = REQUIRED_FILES - expected_paths
    if missing:
        raise RuntimeError(f"Required runtime files missing: {sorted(missing)}")
    forbidden = sorted(
        path for path in expected_paths
        if Path(path).suffix.lower() in REJECTED_EXTENSIONS or
        path.startswith(("tests/", "ci/golden_datasets/", "evidence/"))
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
            if source.read(name) != git("show", f"HEAD:{name}"):
                raise RuntimeError(f"Git source content differs from archive: {name}")

    config = tomllib.loads(git("show", "HEAD:pyproject.toml").decode())
    version = config["project"]["version"]
    if not isinstance(version, str) or not version:
        raise RuntimeError("Package version missing")
    manifest = {
        "source_sha": source_sha,
        "candidate_package_version_not_official_release": version,
        "archive": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "uv_lock_sha256": hashlib.sha256(git("show", "HEAD:uv.lock")).hexdigest(),
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
