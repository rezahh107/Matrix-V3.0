import copy
import json
from collections.abc import Mapping
from typing import Any, cast

import pandas as pd
import pytest

from app.core.allocation.mentor_pool import (
    apply_mentor_pool_governance,
    compute_effective_status,
    filter_active_mentors,
)
from app.core.policy_loader import MentorStatus, PolicyConfig, parse_policy_dict


def _policy_with_governance(
    base_payload: Mapping[str, object], governance: Mapping[str, object]
) -> PolicyConfig:
    payload = cast(dict[str, object], copy.deepcopy(base_payload))
    payload["mentor_pool_governance"] = dict(governance)
    return parse_policy_dict(payload)


def _base_policy_payload() -> dict[str, object]:
    with open("config/policy.json", encoding="utf-8") as handle:
        data: Any = json.load(handle)
    if not isinstance(data, dict):
        raise TypeError("Policy payload must be a mapping")
    return cast(dict[str, object], data)


def test_filter_retains_all_when_policy_active() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": [11, 12],
            "نام": ["الف", "ب"],
            "has_school_constraint": [False, True],
        }
    )
    baseline = mentors.copy(deep=True)

    filtered = filter_active_mentors(mentors, policy.mentor_pool_governance)

    assert len(filtered) == 2
    assert filtered["has_school_constraint"].tolist() == [False, True]
    pd.testing.assert_frame_equal(mentors, baseline)


def test_policy_disables_specific_mentor() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive"],
            "mentors": [
                {"mentor_id": 20, "status": "inactive"},
            ],
        },
    )
    mentors = pd.DataFrame({"mentor_id": [10, 20], "نام": ["الف", "ب"]})

    statuses = compute_effective_status(mentors, policy.mentor_pool_governance)
    assert statuses.tolist() == [MentorStatus.ACTIVE, MentorStatus.INACTIVE]

    filtered = filter_active_mentors(mentors, policy.mentor_pool_governance)
    assert filtered["mentor_id"].tolist() == [10]


def test_override_enables_disabled_and_attaches_status() -> None:
    governance_payload = {
        "default_status": "active",
        "allowed_statuses": ["active", "inactive"],
        "mentors": [
            {"mentor_id": 21, "status": "inactive"},
        ],
    }
    policy = _policy_with_governance(_base_policy_payload(), governance_payload)
    mentors = pd.DataFrame({"mentor_id": [21, 22], "نام": ["ج", "د"]})

    filtered = filter_active_mentors(
        mentors,
        policy.mentor_pool_governance,
        overrides={21: True},
        attach_status=True,
    )

    assert filtered["mentor_id"].tolist() == [21, 22]
    assert filtered["mentor_status"].tolist() == ["active", "active"]


def test_override_disables_active_idempotent() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame({"mentor_id": [31, 32, 33]})

    first = filter_active_mentors(mentors, policy.mentor_pool_governance, overrides={32: False})
    second = filter_active_mentors(mentors, policy.mentor_pool_governance, overrides={32: False})

    assert first.equals(second)
    assert first["mentor_id"].tolist() == [31, 33]


def test_default_inactive_requires_override() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "inactive",
            "allowed_statuses": ["active", "inactive"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame({"mentor_id": [40, 41]})

    filtered = filter_active_mentors(mentors, policy.mentor_pool_governance)
    assert filtered.empty

    overridden = filter_active_mentors(mentors, policy.mentor_pool_governance, overrides={41: True})
    assert overridden["mentor_id"].tolist() == [41]


def test_frozen_mentor_is_excluded_from_pool() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive", "frozen"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": [50, 51],
            "mentor_status": ["active", "frozen"],
            "remaining_capacity": [2, 3],
        }
    )

    filtered = filter_active_mentors(mentors, policy.mentor_pool_governance, attach_status=True)

    assert filtered["mentor_id"].tolist() == [50]
    assert filtered["mentor_status"].tolist() == ["active"]


def test_capacity_gate_removes_non_positive_capacity() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": [60, 61, 62],
            "remaining_capacity": [1, 0, -5],
        }
    )

    filtered = filter_active_mentors(mentors, policy.mentor_pool_governance)

    assert filtered["mentor_id"].tolist() == [60]


def test_duplicate_mentor_id_headers_are_resolved() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive", "frozen"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": [70, 71],
            "کد کارمندی پشتیبان": [70, 71],
            "mentor_status": ["active", "frozen"],
            "remaining_capacity": [1, 2],
        }
    )

    statuses = compute_effective_status(mentors, policy.mentor_pool_governance)
    assert statuses.tolist() == [MentorStatus.ACTIVE, MentorStatus.FROZEN]

    filtered = filter_active_mentors(mentors, policy.mentor_pool_governance)

    assert filtered["mentor_id"].tolist() == [70]


def test_frozen_status_not_allowed_raises_validation_error() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": [81, 82],
            "mentor_status": ["active", "frozen"],
            "remaining_capacity": [1, 1],
        }
    )

    with pytest.raises(ValueError):
        filter_active_mentors(mentors, policy.mentor_pool_governance)


def test_all_frozen_mentors_result_in_empty_pool() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive", "frozen"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": [91, 92],
            "mentor_status": ["frozen", "frozen"],
            "remaining_capacity": [2, 3],
        }
    )

    governed = apply_mentor_pool_governance(mentors, policy.mentor_pool_governance)

    assert governed.empty
    assert governed.attrs["mentor_pool_governance"] == {
        "total": 2,
        "removed": 2,
        "overrides_count": 0,
    }


def test_unknown_future_status_is_rejected() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive", "frozen"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame(
        {
            "mentor_id": [101],
            "mentor_status": ["paused"],
        }
    )

    with pytest.raises(ValueError):
        compute_effective_status(mentors, policy.mentor_pool_governance)


def test_apply_mentor_pool_governance_delegates_to_effective_status() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive"],
            "mentors": [
                {"mentor_id": 2, "status": "inactive"},
            ],
        },
    )
    mentors = pd.DataFrame({"mentor_id": [1, 2, 3]})

    filtered = apply_mentor_pool_governance(
        mentors,
        policy.mentor_pool_governance,
        overrides={2: True, 3: False},
    )

    assert filtered["mentor_id"].tolist() == [1, 2]
    assert filtered.attrs["mentor_pool_governance"] == {
        "total": 3,
        "removed": 1,
        "overrides_count": 2,
    }


def test_apply_mentor_pool_without_identifier_is_noop_with_attrs() -> None:
    policy = _policy_with_governance(
        _base_policy_payload(),
        {
            "default_status": "active",
            "allowed_statuses": ["active", "inactive"],
            "mentors": [],
        },
    )
    mentors = pd.DataFrame({"name": ["a", "b"]})

    filtered = apply_mentor_pool_governance(mentors, policy.mentor_pool_governance)

    pd.testing.assert_frame_equal(filtered, mentors)
    assert filtered.attrs["mentor_pool_governance"] == {
        "total": 2,
        "removed": 0,
        "overrides_count": 0,
    }
