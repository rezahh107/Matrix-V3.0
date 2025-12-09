from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from app.core.canonical_frames import canonicalize_headers, canonicalize_pool_frame
from app.core.common.join_keys import validate_and_canonicalize_join_keys
from app.core.policy_adapter import policy
from app.infra.mentors.field_registry import FieldRegistry
from app.infra.mentors.header_resolver import HeaderResolver
from app.infra.mentors.pipeline_v3 import MentorPipelineV3, canonicalize_join_keys_for_cache
from app.infra.reference_mentors_repository import (
    _POOL_JOIN_KEY_QA_ATTR,
    _POOL_QA_PAYLOAD_ATTR,
    import_mentor_pool_from_dataframe,
)


def _make_simple_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            "ظرفیت": [2, 1],
            "کدرشته": [1, 1],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [10, 11],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [101, 102],
        }
    )


def _legacy_pool(df: pd.DataFrame) -> pd.DataFrame:
    normalized = canonicalize_headers(df, header_mode="fa")
    validation = validate_and_canonicalize_join_keys(
        normalized, policy=policy.config, entity_type="mentor"
    )
    canonical = canonicalize_pool_frame(
        validation.canonical_df,
        policy=policy.config,
        sanitize_pool=False,
        pool_source="inspactor",
    )
    canonical.attrs[_POOL_JOIN_KEY_QA_ATTR] = []
    return canonical


def test_happy_path_parity_with_legacy_helpers() -> None:
    payload = _make_simple_df()
    pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")

    result = pipeline.run(payload)

    baseline = _legacy_pool(payload)
    join_cols = ["mentor_id", *policy.config.join_keys, "ظرفیت"]
    assert result.can_continue
    pd.testing.assert_frame_equal(
        result.build_result.pool.loc[:, join_cols].reset_index(drop=True),
        baseline.loc[:, join_cols].reset_index(drop=True),
        check_dtype=False,
    )


def test_golden_parity_snapshot_pool() -> None:
    golden_path = Path("ci/golden_datasets/mentors/golden_inspactor.csv")
    if not golden_path.exists():
        raise AssertionError(
            "Missing sanitized golden mentor dataset at ci/golden_datasets/mentors/golden_inspactor.csv"
        )

    payload = pd.read_csv(golden_path)
    pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")

    result = pipeline.run(payload)
    baseline = _legacy_pool(payload)

    join_cols = ["mentor_id", *policy.config.join_keys, "remaining_capacity", "ظرفیت"]
    pd.testing.assert_frame_equal(
        result.build_result.pool.loc[:, join_cols].reset_index(drop=True),
        baseline.loc[:, join_cols].reset_index(drop=True),
        check_dtype=False,
    )


def test_edge_multi_profile_and_wildcards_exposes_qa() -> None:
    payload = _make_simple_df()
    payload.loc[1, "کد مدرسه"] = 0
    extra = payload.iloc[[1]].copy()
    extra["کد مدرسه"] = 999
    payload = pd.concat([payload, extra], ignore_index=True)

    pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")
    result = pipeline.run(payload)

    assert not result.can_continue
    reasons = {issue["reason"] for issue in result.join_key_result.issues}
    assert "MULTIPLE_JOIN_PROFILES_PER_MENTOR" in reasons
    assert result.join_key_result.usable_profiles.shape[0] == 1
    assert any(
        issue["reason"] == "MULTIPLE_JOIN_PROFILES_PER_MENTOR"
        for issue in result.build_result.qa_issues
    )


def test_header_alias_resolved_and_forwarded() -> None:
    payload = _make_simple_df().rename(columns={"mentor_id": "کد کارمندی پشتیبان"})

    pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")
    result = pipeline.run(payload)

    assert result.header_result.can_continue
    assert "mentor_id" in result.build_result.pool.columns


def test_ensure_mentor_id_coalesces_aliases() -> None:
    registry = FieldRegistry(policy.config)
    resolver = HeaderResolver(registry)
    df = pd.DataFrame({"mentor_code": ["m-1"], "employee_id": [None], "ظرفیت": [1]})

    ensured = resolver._ensure_mentor_id(df)

    assert "mentor_id" in ensured.columns
    assert ensured.loc[0, "mentor_id"] == "m-1"
    assert "mentor_code" not in ensured.columns


def test_ensure_mentor_id_prefers_existing_canonical() -> None:
    registry = FieldRegistry(policy.config)
    resolver = HeaderResolver(registry)
    df = pd.DataFrame(
        {
            "mentor_id": ["canonical-id"],
            "employee_id": ["alias-id"],
            "ظرفیت": [1],
        }
    )

    ensured = resolver._ensure_mentor_id(df)

    assert "mentor_id" in ensured.columns
    assert ensured.loc[0, "mentor_id"] == "canonical-id"
    assert "employee_id" not in ensured.columns


def test_pipeline_handles_canonical_mentor_id_with_alias_column() -> None:
    payload = _make_simple_df()
    payload["mentor_code"] = ["alias-m1", "alias-m2"]

    pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")
    result = pipeline.run(payload)

    assert result.can_continue
    assert list(result.build_result.pool["mentor_id"]) == ["m1", "m2"]
    assert "mentor_code" not in result.build_result.pool.columns


def test_reference_repository_delegates_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeDB:
        def __init__(self) -> None:
            self.cached: pd.DataFrame | None = None
            self.join_keys: list[str] | None = None

        def upsert_mentor_pool_cache(self, df: pd.DataFrame, *, join_keys: list[str]) -> None:
            self.cached = df.copy()
            self.join_keys = list(join_keys)

    calls: list[pd.DataFrame] = []

    original_run = MentorPipelineV3.run

    def _recording_run(self: MentorPipelineV3, df: pd.DataFrame):  # type: ignore[override]
        calls.append(df.copy())
        return original_run(self, df)

    monkeypatch.setattr(MentorPipelineV3, "run", _recording_run)

    payload = _make_simple_df()
    fake_db = _FakeDB()
    result = import_mentor_pool_from_dataframe(payload, db=fake_db, policy=policy.config)

    assert calls, "MentorPipelineV3.run must be invoked"
    assert fake_db.cached is not None
    assert set(result["mentor_id"]) == {"m1", "m2"}


def test_db_derivation_and_cache_canonicalization(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def _fake_derive(
        df: pd.DataFrame, *, db: object, policy: object
    ) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        calls.append({"db": db, "columns": list(df.columns)})
        derived = df.copy()
        derived[policy.join_keys[0]] = [1]
        derived[policy.join_keys[1]] = [1]
        derived[policy.join_keys[2]] = [0]
        derived[policy.join_keys[3]] = [0]
        derived[policy.join_keys[4]] = [0]
        derived[policy.join_keys[5]] = [101]
        qa = [{"reason": "CENTER_FALLBACK_WILDCARD", "row_index": 0}]
        derived.attrs[_POOL_JOIN_KEY_QA_ATTR] = qa
        return derived, qa

    monkeypatch.setattr("app.infra.mentors.pipeline_v3._derive_pool_join_keys", _fake_derive)
    payload = pd.DataFrame({"mentor_id": ["m-1"], "ظرفیت": [1]})
    pipeline = MentorPipelineV3(policy=policy.config, db=object(), reference_mode="excel")

    result = pipeline.run(payload)

    assert calls and calls[0]["db"] is not None
    assert not result.can_continue
    assert result.build_result.qa_issues[0]["reason"] == "CENTER_FALLBACK_WILDCARD"
    cache_ready = result.build_result.pool
    for col in policy.config.join_keys:
        assert pd.api.types.is_integer_dtype(cache_ready[col])


def test_qa_payload_schema_forwarded_via_attrs() -> None:
    payload = _make_simple_df()
    payload.loc[1, "کد مدرسه"] = 0
    payload = pd.concat([payload, payload.iloc[[1]].assign(**{"کد مدرسه": 999})], ignore_index=True)

    pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")
    result = pipeline.run(payload)

    qa_payload = result.build_result.pool.attrs[_POOL_QA_PAYLOAD_ATTR]
    assert set(qa_payload.keys()) == {
        "issues",
        "duplicates",
        "multi_profile_mentors",
        "usable_profiles",
        "all_profiles",
    }
    assert any(
        issue["reason"] == "MULTIPLE_JOIN_PROFILES_PER_MENTOR" for issue in qa_payload["issues"]
    )


def test_qa_attr_is_forwarded_into_result() -> None:
    payload = _make_simple_df()
    payload.attrs[_POOL_JOIN_KEY_QA_ATTR] = [
        {"reason": "CENTER_FALLBACK_WILDCARD", "row_index": 0, "column": "مرکز گلستان صدرا"}
    ]

    pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")
    result = pipeline.run(payload)

    assert not result.can_continue
    assert any(
        issue["reason"] == "CENTER_FALLBACK_WILDCARD" for issue in result.build_result.qa_issues
    )


def test_cache_join_key_canonicalization_outputs_ints() -> None:
    payload = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.config.join_keys[0]: ["1"],
            policy.config.join_keys[1]: ["1"],
            policy.config.join_keys[2]: ["0"],
            policy.config.join_keys[3]: ["0"],
            policy.config.join_keys[4]: ["0"],
            policy.config.join_keys[5]: ["101"],
        }
    )

    canonical = canonicalize_join_keys_for_cache(payload, policy=policy.config)

    for col in policy.config.join_keys:
        assert pd.api.types.is_integer_dtype(canonical[col])


def test_failure_missing_join_keys_in_headers_or_values() -> None:
    payload = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            "ظرفیت": [1],
            "جنسیت": [1],
        }
    )
    pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")

    result = pipeline.run(payload)

    assert not result.header_result.can_continue
    assert not result.can_continue
    assert any(issue["reason"] == "MISSING_JOIN_KEY" for issue in result.value_result.issues)


def test_missing_mentor_id_is_reported_not_crashing() -> None:
    payload = pd.DataFrame(
        {
            "ظرفیت": [1],
            "کدرشته": [1],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [10],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [101],
        }
    )

    pipeline = MentorPipelineV3(policy=policy.config, reference_mode="excel")
    result = pipeline.run(payload)

    assert not result.can_continue
    assert any(
        issue.get("reason") == "MISSING_MENTOR_ID" for issue in result.join_key_result.issues
    )
    assert "mentor_id" in result.join_key_result.canonical_df.columns
