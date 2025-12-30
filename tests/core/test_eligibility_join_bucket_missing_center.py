from __future__ import annotations

import pandas as pd

from app.core.allocate_students import _collect_join_key_map
from app.core.common.eligibility_channel import (
    EligibilitySpec,
    apply_eligibility,
    build_join_bucket_index,
)
from app.core.common.join_keys import normalize_join_key_name
from app.core.common.join_resolver import JoinKeyResolver
from app.core.policy_loader import load_policy


def _build_pool(total: int, global_count: int) -> pd.DataFrame:
    policy = load_policy()
    payload: dict[str, list[int]] = {}
    for column in policy.join_keys:
        payload[column] = [1] * total
    payload[policy.stage_column("gender")] = [int(policy.gender_codes.male.value)] * total
    payload[policy.stage_column("graduation_status")] = [0] * total
    payload[policy.stage_column("finance")] = [0] * total
    payload[policy.columns.school_code] = [1] * total
    center_column = policy.stage_column("center")
    payload[center_column] = [0] * global_count + [101] * (total - global_count)
    return pd.DataFrame(payload)


def _build_student(center_value: object) -> dict[str, object]:
    policy = load_policy()
    student: dict[str, object] = {column: 1 for column in policy.join_keys}
    student[policy.stage_column("gender")] = int(policy.gender_codes.male.value)
    student[policy.stage_column("graduation_status")] = 0
    student[policy.stage_column("finance")] = 0
    student[policy.stage_column("center")] = center_value
    student[policy.columns.school_code] = 1
    student["student_id"] = "S-1"
    return student


def _build_spec(
    student: dict[str, object],
    *,
    join_map: dict[str, int],
    join_bucket_index: dict[tuple[int, ...], pd.Index],
) -> EligibilitySpec:
    policy = load_policy()
    resolver = JoinKeyResolver(policy)
    return EligibilitySpec(
        effective_join_keys=resolver.resolve_center(student, student_join_map=join_map),
        finance_keys=resolver.resolve_finance(student, student_join_map=join_map),
        school_code=resolver.resolve_school(student, student_join_map=join_map),
        student=student,
        policy=policy,
        student_join_map=join_map,
        join_bucket_index=join_bucket_index,
    )


def test_missing_center_disables_join_bucket_and_preserves_pool_size() -> None:
    policy = load_policy()
    pool = _build_pool(total=5250, global_count=90)
    join_bucket_index = build_join_bucket_index(pool, policy)
    student = _build_student(center_value=-1)

    join_map, missing_columns = _collect_join_key_map(student, policy)
    normalized_center = normalize_join_key_name(policy.stage_column("center"))
    assert join_map[normalized_center] == -1
    assert policy.stage_column("center") in missing_columns

    spec = _build_spec(
        student,
        join_map=join_map,
        join_bucket_index=join_bucket_index,
    )
    eligible, _priority, trace = apply_eligibility(pool, spec)

    assert trace["initial"]["rows"] == 5250
    assert trace["bucketed"]["rows"] == 5250
    assert trace["eligible"]["rows"] == 5250
    assert spec.effective_join_keys.center_code is None
    assert eligible.shape[0] == 5250


def test_center_zero_collapses_to_global_mentors() -> None:
    policy = load_policy()
    pool = _build_pool(total=5250, global_count=90)
    join_bucket_index = build_join_bucket_index(pool, policy)
    student = _build_student(center_value=0)

    join_map, missing_columns = _collect_join_key_map(student, policy)
    assert missing_columns == ()
    normalized_center = normalize_join_key_name(policy.stage_column("center"))
    assert join_map[normalized_center] == 0

    spec = _build_spec(
        student,
        join_map=join_map,
        join_bucket_index=join_bucket_index,
    )
    eligible, _priority, trace = apply_eligibility(pool, spec)

    assert trace["initial"]["rows"] == 5250
    assert trace["eligible"]["rows"] == 90
    assert eligible.shape[0] == 90
