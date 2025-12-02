import pandas as pd
import pytest

from app.core.common.ranking import apply_ranking_policy
from app.core.policy_loader import PolicyConfig, load_policy


def test_apply_ranking_policy_orders_by_capacity_then_allocations_then_id() -> None:
    policy: PolicyConfig = load_policy()
    state = {
        1: {"remaining": 1, "alloc_new": 0},
        2: {"remaining": 3, "alloc_new": 2},
        3: {"remaining": 3, "alloc_new": 1},
    }
    pool = pd.DataFrame({"mentor_id": [1, 2, 3]})

    ranked = apply_ranking_policy(pool, state=state, policy=policy)

    assert ranked["mentor_id_en"].tolist() == [3, 2, 1]
    assert ranked["remaining_capacity"].tolist() == [3, 3, 1]
    assert ranked["allocations_new"].tolist() == [1, 2, 0]


def test_apply_ranking_policy_rejects_ratio_metrics() -> None:
    policy: PolicyConfig = load_policy()
    bad_rules = [
        policy.ranking_rules[0],
        policy.ranking_rules[1],
        policy.ranking_rules[2].__class__(
            name="min_mentor_id", column="occupancy_ratio", ascending=True
        ),
    ]
    mutated_policy = PolicyConfig(
        version=policy.version,
        normal_statuses=policy.normal_statuses,
        school_statuses=policy.school_statuses,
        join_keys=policy.join_keys,
        required_student_fields=policy.required_student_fields,
        ranking_rules=bad_rules,
        trace_stages=policy.trace_stages,
        gender_codes=policy.gender_codes,
        postal_valid_range=policy.postal_valid_range,
        finance_variants=policy.finance_variants,
        center_map=policy.center_map,
        school_code_empty_as_zero=policy.school_code_empty_as_zero,
        prefer_major_code=policy.prefer_major_code,
        coverage_threshold=policy.coverage_threshold,
        dedup_removed_ratio_threshold=policy.dedup_removed_ratio_threshold,
        school_lookup_mismatch_threshold=policy.school_lookup_mismatch_threshold,
        join_key_duplicate_threshold=policy.join_key_duplicate_threshold,
        alias_rule=policy.alias_rule,
        columns=policy.columns,
        column_aliases=policy.column_aliases,
        excel=policy.excel,
        virtual_alias_ranges=policy.virtual_alias_ranges,
        virtual_name_patterns=policy.virtual_name_patterns,
        emission=policy.emission,
        fairness_strategy=policy.fairness_strategy,
        center_management=policy.center_management,
        mentor_pool_governance=policy.mentor_pool_governance,
        coverage_options=policy.coverage_options,
        mentor_school_binding=policy.mentor_school_binding,
        allocation_channels=policy.allocation_channels,
        meta=policy.meta,
    )

    with pytest.raises(ValueError):
        apply_ranking_policy(pd.DataFrame({"mentor_id": [1]}), policy=mutated_policy)
