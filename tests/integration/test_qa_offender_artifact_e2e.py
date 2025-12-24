from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra import cli


def _build_matrix_payload(policy) -> pd.DataFrame:
    group_col = policy.stage_column("type")
    status_col = policy.stage_column("graduation_status")
    payload: dict[str, list[object]] = {
        "mentor_id": ["S1"],
        "جایگزین": ["S1"],
        "عادی مدرسه": ["مدرسه‌ای"],
        "has_school_constraint": [True],
        "source_sheet": ["SheetA"],
        "source_row_index": [2],
        "کدرشته": [1],
        "جنسیت": [1],
        "دانش آموز فارغ": [1],
        "مرکز گلستان صدرا": [0],
        "مالی حکمت بنیاد": [0],
        "کد مدرسه": [0],
    }
    if group_col not in payload:
        payload[group_col] = [1]
    if status_col not in payload:
        payload[status_col] = [1]
    matrix = pd.DataFrame(payload)
    return matrix


def _run_build_matrix_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, object]:
    policy = load_policy()
    schools_df = pd.DataFrame({"کد مدرسه": pd.Series([0], dtype="Int64")})
    crosswalk_df = pd.DataFrame({"کد مدرسه": pd.Series([0], dtype="Int64")})
    matrix = _build_matrix_payload(policy)
    empty = pd.DataFrame()
    join_key_duplicates = pd.DataFrame(columns=[*policy.join_keys, "mentor_id", "duplicate_group_size"])
    progress_log = pd.DataFrame()

    def fake_build_matrix(
        _insp_df: pd.DataFrame,
        _schools_df: pd.DataFrame,
        _crosswalk_groups_df: pd.DataFrame,
        *,
        crosswalk_synonyms_df: pd.DataFrame,
        cfg,
        progress,
    ):  # type: ignore[no-untyped-def]
        return (
            matrix,
            empty,
            empty,
            empty,
            empty,
            empty,
            join_key_duplicates,
            progress_log,
        )

    args = argparse.Namespace(
        inspactor=str(tmp_path / "insp.xlsx"),
        schools=str(tmp_path / "schools.xlsx"),
        crosswalk=str(tmp_path / "crosswalk.xlsx"),
        output=str(tmp_path / "output.xlsx"),
        min_coverage=None,
        local_db_path=str(tmp_path / "local.db"),
        policy_version=None,
    )

    monkeypatch.setattr(cli.cli_legacy, "_resolve_local_db", lambda _args: object())
    monkeypatch.setattr(
        cli.cli_legacy,
        "_resolve_reference_frames",
        lambda **_kwargs: (schools_df, crosswalk_df, pd.DataFrame(), {}, {}),
    )
    monkeypatch.setattr(
        cli.cli_legacy,
        "_resolve_mentor_pool_frame",
        lambda *_args, **_kwargs: (matrix.copy(), {}, {}),
    )
    monkeypatch.setattr(cli.cli_legacy, "build_matrix", fake_build_matrix)
    monkeypatch.setattr(cli.cli_legacy, "_export_qa_validation_workbook", lambda **_kwargs: None)

    with pytest.raises(ValueError):
        cli._run_build_matrix(args, policy, lambda *_args: None)

    artifact_path = tmp_path / "artifacts" / "qa_offenders.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload.pop("generated_at", None)
    return payload


def test_qa_offender_artifact_created_and_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _run_build_matrix_once(tmp_path, monkeypatch)
    second = _run_build_matrix_once(tmp_path, monkeypatch)

    assert first["schema_version"] == "1.0"
    assert first["rule_id"] == "QA_RULE_MENTOR_TYPE_01"
    assert first["offender_count"] == 1
    offenders = first["offenders"]
    assert offenders[0]["source_sheet"] == "SheetA"
    assert offenders[0]["source_row_index"] == 2
    assert offenders[0]["mentor_id"] == "S1"
    assert offenders[0]["resolved_school_code"] == 0
    assert "data_fingerprint" in first
    assert first == second
