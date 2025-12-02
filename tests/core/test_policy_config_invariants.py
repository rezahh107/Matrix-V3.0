import pytest

from app.core.policy_loader import (
    DEFAULT_POLICY_VERSION,
    MentorStatus,
    PolicyConfig,
    load_policy,
)

EXPECTED_JOIN_KEYS = [
    "کدرشته",
    "جنسیت",
    "دانش آموز فارغ",
    "مرکز گلستان صدرا",
    "مالی حکمت بنیاد",
    "کد مدرسه",
]

EXPECTED_TRACE_STAGES = (
    "type",
    "group",
    "gender",
    "graduation_status",
    "center",
    "finance",
    "school",
    "capacity_gate",
)

EXPECTED_RANKING = (
    ("max_remaining_capacity", "remaining_capacity", False),
    ("min_allocations_new", "allocations_new", True),
    ("min_mentor_id", "mentor_sort_key", True),
)


@pytest.fixture(scope="module")
def policy() -> PolicyConfig:
    return load_policy()


def test_policy_versions(policy: PolicyConfig) -> None:
    assert policy.version == DEFAULT_POLICY_VERSION
    assert policy.meta.law_version == "3.0-LAW"
    assert policy.meta.tech_ssot_version == "3.0-TECH"


def test_join_keys_and_trace(policy: PolicyConfig) -> None:
    assert policy.join_keys == EXPECTED_JOIN_KEYS
    assert policy.trace_stage_names == EXPECTED_TRACE_STAGES
    trace_columns = tuple(stage.column for stage in policy.trace_stages)
    assert trace_columns == (
        "کدرشته",
        "کدرشته",
        "جنسیت",
        "دانش آموز فارغ",
        "مرکز گلستان صدرا",
        "مالی حکمت بنیاد",
        "کد مدرسه",
        "remaining_capacity",
    )


def test_ranking_rules(policy: PolicyConfig) -> None:
    assert len(policy.ranking_rules) == len(EXPECTED_RANKING)
    for rule, expected in zip(policy.ranking_rules, EXPECTED_RANKING, strict=True):
        name, column, ascending = expected
        assert rule.name == name
        assert rule.column == column
        assert rule.ascending is ascending
        assert "ratio" not in rule.column
        assert "occupancy" not in rule.column


def test_alias_and_governance(policy: PolicyConfig) -> None:
    assert policy.alias_rule.normal == "postal_code"
    assert policy.alias_rule.school == "mentor_id"
    governance = policy.mentor_pool_governance
    assert governance.default_status is MentorStatus.ACTIVE
    assert set(governance.allowed_statuses) == {MentorStatus.ACTIVE, MentorStatus.FROZEN}
    assert governance.mentor_status_map == {}
