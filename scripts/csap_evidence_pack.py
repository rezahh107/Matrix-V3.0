from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_paths(paths: Iterable[str]) -> list[Path]:
    resolved: list[Path] = []
    for entry in paths:
        path = Path(entry)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {entry}")
        resolved.append(path)
    return resolved


def main() -> None:
    timestamp = datetime.now(UTC).isoformat()
    head = _run(["git", "rev-parse", "HEAD"])
    print(f"timestamp_utc: {timestamp}")
    print(f"git_head: {head}")

    files = _iter_paths(
        [
            "app/core/common/eligibility_channel.py",
            "app/core/common/join_resolver.py",
            "app/core/allocate_students.py",
        ]
        + list(_run(["git", "diff", "--name-only", "HEAD~1"]).splitlines())
    )

    seen: set[Path] = set()
    print("file_hashes:")
    for path in files:
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            digest = _sha256_for_file(path)
            print(f"  - {path.as_posix()}: {digest}")


if __name__ == "__main__":
    main()
