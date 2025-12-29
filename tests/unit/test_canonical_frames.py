from __future__ import annotations

import pandas as pd
import pytest

from app.core.policy_loader import MentorPoolGovernanceConfig, MentorStatus
from app.infra.canonical_frames import canonicalize_mentor_pool_frame


def _governance_config(*, allowed: tuple[MentorStatus, ...]) -> MentorPoolGovernanceConfig:
    return MentorPoolGovernanceConfig(
        default_status=MentorStatus.ACTIVE,
        mentor_status_map={},
        allowed_statuses=allowed,
    )


def test_canonicalize_mentor_pool_frame_handles_non_range_index() -> None:
    governance = _governance_config(allowed=(MentorStatus.ACTIVE,))
    mentors_df = pd.DataFrame(
        {"mentor_status": ["active", "active"]},
        index=pd.Index([10, 20], name="mentor_id"),
    )

    canonical = canonicalize_mentor_pool_frame(mentors_df, governance=governance)

    assert canonical.loc[10, "mentor_status"] == "active"
    assert canonical.loc[20, "mentor_status"] == "active"


@pytest.mark.parametrize(
    ("status", "error_match"),
    [
        ("unknown", "Unknown mentor_status value"),
        ("inactive", "mentor_status value is not allowed"),
    ],
)
def test_canonicalize_mentor_pool_frame_rejects_invalid_status(
    status: str, error_match: str
) -> None:
    """Verify that invalid mentor statuses are rejected with the correct error."""
    governance = _governance_config(allowed=(MentorStatus.ACTIVE,))
    mentors_df = pd.DataFrame({"mentor_status": [status]})

    with pytest.raises(ValueError, match=error_match):
        canonicalize_mentor_pool_frame(mentors_df, governance=governance)
