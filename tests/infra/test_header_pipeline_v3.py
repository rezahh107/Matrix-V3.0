from __future__ import annotations

import pandas as pd

from app.core.common.columns import HEADER_ALIASES_V3
from app.infra.common.header_pipeline_v3 import HeaderPipelineV3


def test_header_pipeline_merges_mentor_id_aliases() -> None:
    pipeline = HeaderPipelineV3(alias_registry=HEADER_ALIASES_V3)
    df = pd.DataFrame(
        {
            "mentor_code": ["A", None],
            "employee_id": [None, "B"],
            "گروه آزمایشی": ["27", "27"],
        }
    )
    result = pipeline.resolve(df, source="mentor")

    assert "mentor_id" in result.resolved_df
    assert result.resolved_df["mentor_id"].tolist() == ["A", "B"]


def test_header_pipeline_respects_existing_canonical_mentor_id() -> None:
    pipeline = HeaderPipelineV3(alias_registry=HEADER_ALIASES_V3)
    df = pd.DataFrame(
        {
            "mentor_id": ["canonical", None],
            "employee_id": [None, "alias"],
            "گروه آزمایشی": ["27", "27"],
        }
    )

    result = pipeline.resolve(df, source="mentor")

    assert "mentor_id" in result.resolved_df
    assert result.resolved_df["mentor_id"].tolist() == ["canonical", "alias"]


def test_header_pipeline_reports_unknown_and_ambiguous_headers() -> None:
    pipeline = HeaderPipelineV3(
        alias_registry={"mentor": {"mentor_id": "mentor_id", "کد رشته": "کدرشته"}},
        required={"mentor": ["mentor_id", "کدرشته"]},
        critical_required={"mentor": ["mentor_id", "کدرشته"]},
    )
    df = pd.DataFrame({"mentor_id": [1], "کد رشته": [1], "کدرشته": [2], "???": [3]})

    result = pipeline.resolve(df, source="mentor")
    messages = {issue.message for issue in result.issues}
    severities = {issue.severity for issue in result.issues}

    assert "AMBIGUOUS_HEADER" in messages
    assert "UNKNOWN_HEADER" in messages
    assert result.can_continue
    assert "P2" in severities


def test_header_pipeline_flags_missing_join_key_as_p0() -> None:
    pipeline = HeaderPipelineV3(
        alias_registry=HEADER_ALIASES_V3,
        required={"mentor": ["mentor_id", "کدرشته"]},
        critical_required={"mentor": ["mentor_id", "کدرشته"]},
    )
    df = pd.DataFrame({"mentor_id": ["A"]})

    result = pipeline.resolve(df, source="mentor")
    missing_messages = [issue for issue in result.issues if issue.message == "MISSING_REQUIRED"]

    assert not result.can_continue
    assert missing_messages[0].severity == "P0"


def test_header_pipeline_handles_inspactor_unknown_and_capacity_ambiguity() -> None:
    pipeline = HeaderPipelineV3(alias_registry=HEADER_ALIASES_V3)
    df = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["1"],
            "تعداد داوطلبان تحت پوشش": [10],
            "capacity_current": [12],
            "ستون اضافه": [0],
        }
    )

    result = pipeline.resolve(df, source="inspactor")
    messages = {issue.message for issue in result.issues}
    severities = {issue.severity for issue in result.issues}

    assert "AMBIGUOUS_HEADER" in messages
    assert "UNKNOWN_HEADER" in messages
    assert "mentor_id" in result.resolved_df.columns
    assert result.can_continue
    assert "P2" in severities or "P1" in severities


def test_header_pipeline_maps_student_required_headers() -> None:
    required = ["کدرشته", "گروه آزمایشی", "جنسیت", "کد مدرسه"]
    pipeline = HeaderPipelineV3(
        alias_registry=HEADER_ALIASES_V3,
        required={"student": required},
        critical_required={"student": required},
    )
    df = pd.DataFrame(
        {
            "کد رشته": [1],
            "گروه آزمایشی": [2],
            "جنسیت": [1],
            "school code": [123],
        }
    )

    result = pipeline.resolve(df, source="student")

    assert not result.missing_required
    assert result.can_continue

