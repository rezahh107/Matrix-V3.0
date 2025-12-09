from __future__ import annotations

import pandas as pd

from app.core.policy_loader import load_policy
from app.core.students.domain_validation import validate_student_domain


def test_invalid_graduation_status_yields_issue() -> None:
    policy = load_policy()
    df = pd.DataFrame(
        {
            policy.stage_column("type"): [1],
            policy.stage_column("graduation_status"): [99],
        }
    )

    result = validate_student_domain(df, policy=policy)

    assert result.issues
    assert not result.can_continue
