from __future__ import annotations

import pandas as pd
import pytest

from app.core.canonical_frames import canonicalize_students_frame
from app.core.policy_loader import MentorPoolGovernanceConfig, MentorStatus, load_policy
from app.infra.canonical_frames import canonicalize_mentor_pool_frame


def _governance_config(*, allowed: tuple[MentorStatus, ...]) -> MentorPoolGovernanceConfig:
    return MentorPoolGovernanceConfig(
        default_status=MentorStatus.ACTIVE,
        mentor_status_map={},
        allowed_statuses=allowed,
    )


def test_canonicalize_students_frame_resets_index_and_preserves_lineage() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        {
            "student_id": ["s-1", "s-2", "s-3"],
            "کدرشته": [21, 21, 21],
            "جنسیت": [1, 2, 1],
            "دانش آموز فارغ": [0, 0, 0],
            "مرکز گلستان صدرا": [0, 0, 0],
            "مالی حکمت بنیاد": [0, 0, 0],
            "کد مدرسه": [0, 0, 0],
        },
        index=pd.Index([10, 20, 30], name="row_id"),
    )

    canonical = canonicalize_students_frame(students, policy=policy)

    assert isinstance(canonical.index, pd.RangeIndex)
    assert canonical["__source_index__"].tolist() == [10, 20, 30]


def test_canonicalize_mentor_pool_frame_preserves_string_index_order() -> None:
    governance = _governance_config(allowed=(MentorStatus.ACTIVE,))
    mentors_df = pd.DataFrame(
        {"mentor_status": ["active", "active", "active"]},
        index=pd.Index(["uuid-20", "uuid-10", "uuid-30"], name="mentor_key"),
    )

    canonical = canonicalize_mentor_pool_frame(mentors_df, governance=governance)

    assert list(canonical.index) == ["uuid-20", "uuid-10", "uuid-30"]


def test_canonicalize_mentor_pool_frame_rejects_duplicate_index() -> None:
    governance = _governance_config(allowed=(MentorStatus.ACTIVE,))
    mentors_df = pd.DataFrame(
        {"mentor_status": ["active", "active"]},
        index=pd.Index(["dup", "dup"]),
    )

    with pytest.raises(ValueError, match="input index must be unique"):
        canonicalize_mentor_pool_frame(mentors_df, governance=governance)
