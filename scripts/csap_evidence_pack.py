from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def _run_git(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _print_hashes(paths: list[Path]) -> None:
    for path in paths:
        if not path.exists():
            print(f"{path}: MISSING")
            continue
        print(f"{path}: {_sha256(path)}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    print(f"git rev-parse HEAD: {_run_git(['git', 'rev-parse', 'HEAD'])}")
    print("git status --porcelain:")
    status = _run_git(["git", "status", "--porcelain"])
    print(status if status else "(clean)")

    paths = [
        Path("app/core/common/unknown_data_channel.py"),
        Path("app/core/common/join_resolver.py"),
        Path("app/core/common/eligibility_channel.py"),
        Path("app/core/common/filters.py"),
        Path("app/core/policy_loader.py"),
        Path("app/infra/cli_legacy.py"),
        Path("app/infra/io_utils.py"),
        Path("app/ui/main_window.py"),
        Path("app/ui/dialogs/unknown_data_dialog.py"),
        Path("policy.yaml"),
        Path("policy_sample.yaml"),
        Path("config/policy.json"),
        Path("config/dashboard_texts.json"),
        Path("config/logging.yaml"),
        Path("config/SmartAlloc_Exporter_Config_v1.json"),
        Path("resources/translations/ui_texts.json"),
        Path("docs/LAW_Smart_Student_Allocation_v3.0.md"),
        Path("docs/Technical_SSoT_Smart_Student_Allocation_v3.0-TECH.md"),
        Path("docs/📚 Refactor Narrative v3.0 — روایت کامل و ماشین‌فهم از مسأله تا راه‌حل.md"),
        Path("tests/core/test_unknown_data_channel.py"),
        Path("tests/core/test_policy_unknown_modes_explicit.py"),
        Path("tests/core/test_center_from_manager.py"),
        Path("tests/core/test_canonical_frames.py"),
        Path("tests/core/test_ranking_rules.py"),
        Path("tests/core/common/test_join_resolver.py"),
        Path("tests/unit/test_trace.py"),
        Path("tests/infra/test_reference_mentors_repository.py"),
        Path("tests/infra/test_preflight_unknowns_report.py"),
        Path("tests/integration/test_matrix_core_end_to_end.py"),
        Path("app/core/matrix/build_matrix_core.py"),
        Path("tests/ui/test_unknowns_decision_gate.py"),
        Path("tools/ci/test_no_silent_coercion.py"),
    ]
    print("sha256:")
    _print_hashes([repo_root / path for path in paths])


if __name__ == "__main__":
    main()
