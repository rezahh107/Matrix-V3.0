"""Run isolated, paired, and complete Windows Qt pytest processes.

Only the diagnostic workflow invokes this script; production CI is untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

LOADER = "tests/ui/test_qt_loader_harness.py::test_harness_handles_repeated_immediate_success"
OVERLAY = "tests/ui/test_uiux_method_locks.py::test_ui_busy_overlay_tracks_splitter_geometry"


def _identity() -> dict[str, Any]:
    def version(name: str) -> str:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return "unavailable"

    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    return {
        "source_commit": sha,
        "python": sys.version,
        "executable": sys.executable,
        "windows": platform.platform(),
        "pyside6": version("PySide6"),
        "shiboken6": version("shiboken6"),
        "pytest": version("pytest"),
        "pytest_timeout": version("pytest-timeout"),
        "uv_lock_sha256": hashlib.sha256(Path("uv.lock").read_bytes()).hexdigest(),
    }


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"kind": "truncated_jsonl_line"})
    return out


def _run_case(name: str, targets: list[str], root: Path) -> dict[str, Any]:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    events = folder / "qt-lifecycle.jsonl"
    log = folder / "pytest.log"
    env = os.environ.copy()
    env["MATRIX_QT_PROBE_JSONL"] = str(events.resolve())
    env["PYTHONUNBUFFERED"] = "1"
    command = [
        sys.executable, "-X", "faulthandler", "-m", "pytest", *targets,
        "-p", "tools.ci.qt_windows_lifecycle_probe",
        "-vv", "--durations=0", "-ra", "--maxfail=1",
    ]
    start = time.monotonic()
    print("CASE_START", name, json.dumps(targets), flush=True)
    with log.open("w", encoding="utf-8", errors="replace") as handle:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", env=env)
        assert proc.stdout is not None
        for line in proc.stdout:
            handle.write(line)
            handle.flush()
            print(line, end="", flush=True)
        returncode = proc.wait()
    duration = round(time.monotonic() - start, 3)
    records = _read_events(events)
    terminal = [x for x in records if x.get("kind") == "pytest_sessionfinish"]
    starts = [x for x in records if x.get("kind") == "test_start"]
    ends = [x for x in records if x.get("kind") == "test_end"]
    outcomes = [x for x in records if x.get("kind") == "test_report" and x.get("phase") == "call"]
    text = log.read_text(encoding="utf-8", errors="replace")
    summaries = re.findall(r"(?m)^=+\s+([^\n]*?\d+ passed[^\n]*?)\s+=+$", text)
    summary = {
        "case": name,
        "targets": targets,
        "elapsed_seconds": duration,
        "process_exit_code": returncode,
        "pytest_logical_exitstatus": terminal[-1]["logical_exitstatus"] if terminal else None,
        "python_atexit_observed": any(x.get("kind") == "python_atexit" for x in records),
        "pytest_unconfigure_observed": any(x.get("kind") == "pytest_unconfigure" for x in records),
        "last_test_started": starts[-1].get("test") if starts else None,
        "last_test_completed": ends[-1].get("test") if ends else None,
        "test_completed_count": len(ends),
        "test_call_results": {
            status: sum(x.get("outcome") == status for x in outcomes)
            for status in ("passed", "failed", "skipped")
        },
        "terminal_summary": summaries[-1] if summaries else None,
        "first_qt_snapshot": starts[0] if starts else None,
        "last_qt_snapshot": ends[-1] if ends else None,
    }
    (folder / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("CASE_END", json.dumps({k: v for k, v in summary.items()
                                  if k not in ("first_qt_snapshot", "last_qt_snapshot")}),
          flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("isolate", "pairs", "suite"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    identity = _identity()
    (args.output_dir / "environment.json").write_text(
        json.dumps(identity, indent=2), encoding="utf-8"
    )
    print("ENVIRONMENT", json.dumps(identity), flush=True)
    if args.mode == "isolate":
        cases = [
            (f"loader-isolated-{i}", [LOADER]) for i in range(1, 4)
        ] + [
            (f"overlay-isolated-{i}", [OVERLAY]) for i in range(1, 4)
        ]
    elif args.mode == "pairs":
        cases = [
            ("pair-loader-overlay", [LOADER, OVERLAY]),
            ("pair-overlay-loader", [OVERLAY, LOADER]),
        ]
    else:
        cases = [("full-suite", ["tests/ui"])]
    results = [_run_case(name, targets, args.output_dir) for name, targets in cases]
    (args.output_dir / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    good = all(x["process_exit_code"] == 0 and x["pytest_logical_exitstatus"] == 0
               for x in results)
    print("DIAGNOSTIC_RESULT", "ALL_ZERO_EXIT" if good else "NONZERO_OR_NOT_PROVEN",
          flush=True)
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
