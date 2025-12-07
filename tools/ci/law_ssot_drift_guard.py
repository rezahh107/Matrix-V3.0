from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

DOC_PATHS: set[str] = {
    "docs/LAW_Smart_Student_Allocation_v3.0.md",
    "docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md",
    "docs/Repository Specification (SSoT).md",
}

CODE_PREFIXES: tuple[str, ...] = (
    "app/",
    "tests/",
    "tools/",
    "scripts/",
    "ci/",
)


def _normalize_paths(changed_files: Iterable[str]) -> list[str]:
    return [Path(path).as_posix() for path in changed_files]


def classify_changes(changed_files: Iterable[str]) -> tuple[list[str], list[str]]:
    normalized = _normalize_paths(changed_files)
    doc_changes = [path for path in normalized if path in DOC_PATHS]
    code_changes = [
        path for path in normalized if any(path.startswith(prefix) for prefix in CODE_PREFIXES)
    ]
    return doc_changes, code_changes


def check_doc_drift(changed_files: Iterable[str]) -> tuple[bool, list[str]]:
    doc_changes, code_changes = classify_changes(changed_files)
    if doc_changes and not code_changes:
        return False, doc_changes
    return True, doc_changes


def _git_diff_names(base: str, head: str) -> list[str]:
    diff_cmd = ["git", "diff", "--name-only", f"{base}..{head}"]
    result = subprocess.run(diff_cmd, check=True, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line.strip()]


def main(argv: Sequence[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("Usage: python tools/ci/law_ssot_drift_guard.py <base> <head>\n")
        return 2

    base, head = argv[1], argv[2]
    try:
        changed_files = _git_diff_names(base, head)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - git failure
        sys.stderr.write(f"Failed to read git diff for {base}..{head}: {exc.stderr or exc}")
        return 2

    ok, doc_changes = check_doc_drift(changed_files)
    if not ok:
        sys.stderr.write(
            "Detected LAW/SSoT documentation changes without corresponding app/" "tests updates.\n"
        )
        sys.stderr.write("Changed documentation files:\n")
        for path in doc_changes:
            sys.stderr.write(f"  - {path}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
