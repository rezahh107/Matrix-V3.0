from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra.cli_legacy import _resolve_mentor_pool_frame
from app.infra.pool_loader import load_pool


def _write_workbook(path: Path, *, sheet_name: str = "matrix") -> Path:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "mentor_id": [1],
                "کدرشته": [1],
                "جنسیت": [1],
                "دانش آموز فارغ": [0],
                "مرکز گلستان صدرا": [1],
                "مالی حکمت بنیاد": [0],
                "کد مدرسه": [1],
                "remaining_capacity": [1],
                "allocations_new": [0],
            }
        ).to_excel(writer, sheet_name=sheet_name, index=False)
    return path


def _args(
    pool: Path,
    pool_type: str = "matrix",
    pool_sheet: str | None = None,
    *,
    pool_arg: str = "pool",
) -> argparse.Namespace:
    payload = {
        pool_arg: str(pool),
        "pool_type": pool_type,
        "pool_sheet": pool_sheet,
        "_ui_overrides": {},
        "_user_settings": None,
    }
    if pool_arg != "pool":
        payload.setdefault("pool", None)
    return argparse.Namespace(**payload)


def test_resolve_pool_selects_matrix_sheet_case_insensitive(tmp_path: Path) -> None:
    path = _write_workbook(tmp_path / "pool.xlsx", sheet_name="Matrix")
    policy = load_policy(Path("config/policy.json"))

    df, _, _ = _resolve_mentor_pool_frame(
        _args(path),
        policy,
        db=None,
        pool_arg="pool",
        pool_source="matrix",
        matrix_only=True,
    )

    detection = df.attrs.get("pool_detection")
    assert detection is not None
    assert detection.selected_sheet.lower() == "matrix"
    assert df.shape[0] == 1


def test_resolve_pool_requires_matrix_sheet(tmp_path: Path) -> None:
    path = _write_workbook(tmp_path / "pool.xlsx", sheet_name="other")
    policy = load_policy(Path("config/policy.json"))

    with pytest.raises(SystemExit) as excinfo:
        _resolve_mentor_pool_frame(
            _args(path),
            policy,
            db=None,
            pool_arg="pool",
            pool_source="matrix",
            matrix_only=True,
        )

    message = str(excinfo.value)
    assert "Allocation program requires" in message
    assert str(path) in message
    assert "matrix" in message
    assert "other" in message


def test_allocation_rejects_inspactor_pool_type(tmp_path: Path) -> None:
    path = _write_workbook(tmp_path / "pool.xlsx", sheet_name="matrix")
    policy = load_policy(Path("config/policy.json"))

    with pytest.raises(SystemExit) as excinfo:
        _resolve_mentor_pool_frame(
            _args(path, pool_type="inspactor"),
            policy,
            db=None,
            pool_arg="pool",
            pool_source="matrix",
            matrix_only=True,
        )

    assert "pool-type" in str(excinfo.value)


def test_inspactor_loader_still_available_for_pool_builder(tmp_path: Path) -> None:
    path = _write_workbook(tmp_path / "pool.xlsx", sheet_name="inspactor")
    policy = load_policy(Path("config/policy.json"))

    df, _, _ = _resolve_mentor_pool_frame(
        _args(path, pool_type="inspactor", pool_arg="inspactor"),
        policy,
        db=None,
        pool_arg="inspactor",
        pool_source="inspactor",
        matrix_only=False,
    )

    assert not df.empty


def test_pool_loader_closes_handles_allowing_rename(tmp_path: Path) -> None:
    path = _write_workbook(tmp_path / "pool.xlsx")

    df = load_pool(path)
    assert not df.empty

    renamed = path.with_name("pool_renamed.xlsx")
    path.rename(renamed)
    assert renamed.exists()
