"""ماژول Rule Engine برای اعمال سیاست رتبه‌بندی روی ماتریس."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pandas as pd

from app.core.common.ranking import apply_ranking_policy, build_mentor_state
from app.core.policy_loader import PolicyConfig, load_policy

__all__ = ["rank_rule_engine_candidates"]


def rank_rule_engine_candidates(
    candidate_pool: pd.DataFrame, *, policy: PolicyConfig | None = None
) -> pd.DataFrame:
    """مرتب‌سازی کاندیدهای Rule Engine بر اساس policy مرکزی.

    مثال::

        >>> import pandas as pd
        >>> sample = pd.DataFrame({"کد کارمندی پشتیبان": ["EMP-1"], "remaining_capacity": [2]})
        >>> ranked = rank_rule_engine_candidates(sample)
        >>> ranked.empty
        False
    """

    if policy is None:
        policy = load_policy()
    state = build_mentor_state(candidate_pool, policy=policy)
    mapped_state = cast(Mapping[object, Mapping[str, int | float | str | None]], state)
    return apply_ranking_policy(candidate_pool, state=mapped_state, policy=policy)
