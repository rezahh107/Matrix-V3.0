import pandas as pd

from app.core.qa import invariants


def test_history_channel_rule_passes_with_canonical_keys() -> None:
    history_info = pd.DataFrame(
        {
            "national_code": ["0012345678", "12345678"],
            "allocation_channel": ["school", "SADRA"],
        }
    )

    result = invariants.check_HISTORY_CHANNEL_01(history_info=history_info)

    assert result.passed
    assert not result.violations


def test_history_channel_rule_flags_duplicates_after_canonicalization() -> None:
    history_info = pd.DataFrame(
        {
            "national_code": ["123-456-7890", "01234567890"],
            "allocation_channel": ["SCHOOL", "school"],
        }
    )

    result = invariants.check_HISTORY_CHANNEL_01(history_info=history_info)

    assert not result.passed
    assert any(v.rule_id == "QA_RULE_HISTORY_CHANNEL_01" for v in result.violations)
    duplicate_detail = result.violations[0].details or {}
    assert duplicate_detail.get("duplicate_rows") == 2


def test_history_channel_rule_flags_missing_national_code() -> None:
    history_info = pd.DataFrame(
        {"national_code": [None, "  "], "allocation_channel": ["SCHOOL", "SADRA"]}
    )

    result = invariants.check_HISTORY_CHANNEL_01(history_info=history_info)

    assert not result.passed
    assert any(v.rule_id == "QA_RULE_HISTORY_CHANNEL_01" for v in result.violations)
    missing_detail = result.violations[0].details or {}
    assert missing_detail.get("invalid_rows") == 2
