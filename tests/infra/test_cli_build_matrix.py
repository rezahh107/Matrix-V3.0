from dataclasses import replace

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.cli import _sanitize_pool_for_allocation


def test_cli_sanitize_pool_keeps_alias_from_virtual_range() -> None:
    policy = replace(load_policy(), virtual_alias_ranges=((7000, 8000),))
    pool_df = pd.DataFrame(
        {
            "mentor_name": ["مجازی"],
            "alias": [7501],
            "remaining_capacity": [1],
            "کدرشته": [21],
            "جنسیت": [1],
            "دانش آموز فارغ": [1],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [0],
        }
    )

    sanitized = _sanitize_pool_for_allocation(pool_df, policy=policy)

    assert len(sanitized) == 1
    assert int(sanitized["remaining_capacity"].iloc[0]) == 1
