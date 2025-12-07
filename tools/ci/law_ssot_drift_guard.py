from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Tuple


LAW_DOC_KEYWORDS: Tuple[str, ...] = (
    "LAW_",
    "SSoT",
    "Refactor Narrative",
    "Repository Specification",
    "Coverage Map",
)

CODE_OR_TEST_PREFIXES: Tuple[str, ...] = (
    "app/",
    "tests/",
)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guard against LAW/SSoT doc changes without code or tests updates.",
    )
    parser.add_argument(
        "base_ref",
        nargs="?",
        default="origin/main",
        help="Base git ref (default: origin/main)",
    )
    parser.add_argument(
        "head_ref",
        nargs="?",
        default="HEAD",
        help="Head git ref (default: HEAD)",
    )
    return parser.parse_args(list(argv))


def get_changed_files(base_ref: str, head_ref: str) -> List[str]:
    diff_output = subprocess.check_output(
        ["git", "diff", "--name-only", base_ref, head_ref],
        text=True,
    )
    return [line.strip() for line in diff_output.splitlines() if line.strip()]


def classify_changes(changed_files: Iterable[str]) -> Tuple[List[str], List[str]]:
    law_docs: List[str] = []
    code_or_tests: List[str] = []

    for path_str in changed_files:
        path = Path(path_str)
        if path.parts and path.parts[0] == "docs" and any(
            keyword in path.name for keyword in LAW_DOC_KEYWORDS
        ):
            law_docs.append(path_str)

        if any(path_str.startswith(prefix) for prefix in CODE_OR_TEST_PREFIXES):
            code_or_tests.append(path_str)

    return law_docs, code_or_tests


def latest_commit_message() -> str:
    return subprocess.check_output(["git", "log", "-1", "--pretty=%B"], text=True)


def should_skip_guard() -> bool:
    message = latest_commit_message()
    return "SKIP_LAW_DRIFT_GUARD" in message


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    if should_skip_guard():
        print("SKIP_LAW_DRIFT_GUARD found in latest commit message; skipping guard.")
        return 0

    changed_files = get_changed_files(args.base_ref, args.head_ref)
    law_docs, code_or_tests = classify_changes(changed_files)

    if not law_docs:
        return 0

    if code_or_tests:
        return 0

    print("Detected LAW/SSoT documentation changes without corresponding app/tests updates.")
    print("Changed documentation files:")
    for path in law_docs:
        print(f"  - {path}")
    print("Please update relevant application code or tests to keep documentation in sync.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
