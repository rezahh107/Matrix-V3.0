from __future__ import annotations

import pandas as pd

from app.core.canonical_frames import _build_join_key_duplicate_report
from app.core.policy_loader import load_policy

MENTOR_COLUMN = "کد کارمندی پشتیبان"


def _row(join_keys: list[str], values: list[int], mentor: str) -> dict[str, object]:
    data = dict(zip(join_keys, values, strict=True))
    data[MENTOR_COLUMN] = mentor
    return data


def test_duplicate_report_empty_when_no_duplicates() -> None:
    policy = load_policy()
    join_keys = policy.join_keys
    frame = pd.DataFrame(
        [
            _row(join_keys, [101, 1, 0, 1, 0, 501], "EMP-1"),
            _row(join_keys, [102, 1, 0, 1, 0, 502], "EMP-2"),
            _row(join_keys, [103, 1, 0, 1, 0, 503], "EMP-3"),
        ]
    )

    report = _build_join_key_duplicate_report(frame, join_keys, MENTOR_COLUMN)

    assert report.empty
    assert report.columns.tolist() == join_keys + [MENTOR_COLUMN, "duplicate_group_size"]
    assert str(report["duplicate_group_size"].dtype) == "Int64"


def test_duplicate_report_flags_cross_mentor_collisions() -> None:
    policy = load_policy()
    join_keys = policy.join_keys
    shared_keys = [201, 1, 0, 1, 0, 601]
    unique_keys = [202, 1, 0, 1, 0, 602]
    frame = pd.DataFrame(
        [
            _row(join_keys, shared_keys, "EMP-1"),
            _row(join_keys, shared_keys, "EMP-2"),
            _row(join_keys, unique_keys, "EMP-3"),
        ]
    )

    report = _build_join_key_duplicate_report(frame, join_keys, MENTOR_COLUMN)

    assert len(report) == 2
    assert report[MENTOR_COLUMN].tolist() == ["EMP-1", "EMP-2"]
    assert report["duplicate_group_size"].dropna().unique().tolist() == [2]
    assert all(tuple(row[join_key] for join_key in join_keys) == tuple(shared_keys) for _, row in report.iterrows())


def test_duplicate_report_handles_multiple_duplicate_groups() -> None:
    policy = load_policy()
    join_keys = policy.join_keys
    group_one = [301, 1, 0, 1, 0, 701]
    group_two = [302, 1, 0, 1, 0, 801]
    unique = [303, 1, 0, 1, 0, 901]
    frame = pd.DataFrame(
        [
            _row(join_keys, group_two, "EMP-3"),
            _row(join_keys, group_one, "EMP-1"),
            _row(join_keys, group_one, "EMP-2"),
            _row(join_keys, group_two, "EMP-4"),
            _row(join_keys, unique, "EMP-5"),
        ]
    )

    report = _build_join_key_duplicate_report(frame, join_keys, MENTOR_COLUMN)

    assert len(report) == 4
    group_sizes = report.groupby(join_keys, sort=False)["duplicate_group_size"].first()
    assert group_sizes.to_dict() == {tuple(group_one): 2, tuple(group_two): 2}
    assert report[MENTOR_COLUMN].tolist() == ["EMP-1", "EMP-2", "EMP-3", "EMP-4"]
    assert str(report["duplicate_group_size"].dtype) == "Int64"
