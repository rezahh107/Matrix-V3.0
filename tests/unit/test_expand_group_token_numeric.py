"""تست‌های پذیرش برای پشتیبانی از کد عددی در expand_group_token."""

from __future__ import annotations

import pandas as pd
import pytest

from app.core.build_matrix import (
    COL_GROUP,
    COL_GROUP_INCLUDED,
    COL_MANAGER_NAME,
    COL_MENTOR_ID,
    COL_MENTOR_NAME,
    BuildConfig,
    _prepare_base_rows,
    expand_group_token,
    prepare_crosswalk_mappings,
)


def _sample_crosswalk() -> (
    tuple[dict[str, int], dict[int, str], dict[str, list[tuple[str, int]]], dict[str, str]]
):
    crosswalk = pd.DataFrame(
        {"گروه آزمایشی": ["یازدهم ریاضی"], "کد گروه": [27], "مقطع تحصیلی": ["متوسطه دوم"]}
    )
    return prepare_crosswalk_mappings(crosswalk, None)


def test_expand_group_token_supports_numeric_code() -> None:
    """ورودی عددی باید مستقیماً به نام/کد معتبر نگاشت شود."""

    name_to_code, code_to_name, buckets, synonyms = _sample_crosswalk()

    result = expand_group_token("27", name_to_code, code_to_name, buckets, synonyms)

    assert result == [("یازدهم ریاضی", 27)]


def test_prepare_base_rows_accepts_numeric_group_code() -> None:
    """کد عددی در ستون گروه آزمایشی نباید به unseen_groups اضافه شود."""

    name_to_code, code_to_name, buckets, synonyms = _sample_crosswalk()
    cfg = BuildConfig()
    insp = pd.DataFrame(
        {
            COL_MENTOR_ID: ["EMP-1"],
            COL_MENTOR_NAME: ["پشتیبان الف"],
            COL_MANAGER_NAME: ["مدیر الف"],
            COL_GROUP: ["27"],
            COL_GROUP_INCLUDED: ["27"],
        }
    )

    base_df, unseen_groups, unmatched_schools = _prepare_base_rows(
        insp,
        cfg=cfg,
        name_to_code=name_to_code,
        code_to_name=code_to_name,
        buckets=buckets,
        synonyms=synonyms,
        school_name_to_code={},
        code_to_name_school={},
        group_cols=["گروه آزمایشی"],
        school_cols=[],
        gender_col=None,
        included_col=COL_GROUP_INCLUDED,
    )

    assert unseen_groups == []
    assert unmatched_schools == []
    assert base_df.iloc[0]["group_pairs"] == [("یازدهم ریاضی", 27)]


def test_prepare_base_rows_ignores_invalid_when_valid_present() -> None:
    """توکن نامعتبر کنار مقدار معتبر نباید coverage را کاهش دهد."""

    name_to_code, code_to_name, buckets, synonyms = _sample_crosswalk()
    cfg = BuildConfig()
    insp = pd.DataFrame(
        {
            COL_MENTOR_ID: ["EMP-1"],
            COL_MENTOR_NAME: ["پشتیبان الف"],
            COL_MANAGER_NAME: ["مدیر الف"],
            COL_GROUP: ["27, نامعتبر"],
            COL_GROUP_INCLUDED: ["27"],
        }
    )

    base_df, unseen_groups, unmatched_schools = _prepare_base_rows(
        insp,
        cfg=cfg,
        name_to_code=name_to_code,
        code_to_name=code_to_name,
        buckets=buckets,
        synonyms=synonyms,
        school_name_to_code={},
        code_to_name_school={},
        group_cols=["گروه آزمایشی"],
        school_cols=[],
        gender_col=None,
        included_col=COL_GROUP_INCLUDED,
    )

    assert unseen_groups == []
    assert unmatched_schools == []
    assert base_df.iloc[0]["group_pairs"] == [("یازدهم ریاضی", 27)]


def test_prepare_base_rows_reports_unseen_when_no_valid_group() -> None:
    """وقتی هیچ گروه معتبری نیست، باید unseen_groups ثبت شود."""

    name_to_code, code_to_name, buckets, synonyms = _sample_crosswalk()
    cfg = BuildConfig()
    insp = pd.DataFrame(
        {
            COL_MENTOR_ID: ["EMP-2"],
            COL_MENTOR_NAME: ["پشتیبان ب"],
            COL_MANAGER_NAME: ["مدیر ب"],
            COL_GROUP: ["نامعتبر"],
            COL_GROUP_INCLUDED: [""],
        }
    )

    base_df, unseen_groups, unmatched_schools = _prepare_base_rows(
        insp,
        cfg=cfg,
        name_to_code=name_to_code,
        code_to_name=code_to_name,
        buckets=buckets,
        synonyms=synonyms,
        school_name_to_code={},
        code_to_name_school={},
        group_cols=["گروه آزمایشی"],
        school_cols=[],
        gender_col=None,
        included_col=COL_GROUP_INCLUDED,
    )

    assert base_df.empty
    assert unmatched_schools == []
    assert unseen_groups == [
        {"group_token": "legacy:نامعتبر", "supporter": "پشتیبان ب", "manager": "مدیر ب"}
    ]


def test_prepare_base_rows_prefers_included_group_column() -> None:
    """ستون «شامل گروه‌های آزمایشی» باید بر ستون legacy اولویت داشته باشد."""

    name_to_code, code_to_name, buckets, synonyms = _sample_crosswalk()
    cfg = BuildConfig()
    included_col = "شامل گروه های آزمایشی"
    insp = pd.DataFrame(
        {
            COL_MENTOR_ID: ["EMP-3"],
            COL_MENTOR_NAME: ["پشتیبان ج"],
            COL_MANAGER_NAME: ["مدیر ج"],
            COL_GROUP: ["نامعتبر"],
            included_col: ["27"],
        }
    )

    base_df, unseen_groups, unmatched_schools = _prepare_base_rows(
        insp,
        cfg=cfg,
        name_to_code=name_to_code,
        code_to_name=code_to_name,
        buckets=buckets,
        synonyms=synonyms,
        school_name_to_code={},
        code_to_name_school={},
        group_cols=[COL_GROUP],
        school_cols=[],
        gender_col=None,
        included_col=included_col,
    )

    assert unseen_groups == []
    assert unmatched_schools == []
    assert base_df.iloc[0]["group_pairs"] == [("یازدهم ریاضی", 27)]


def test_prepare_base_rows_accepts_only_included_group_column() -> None:
    """اگر فقط ستون جدید وجود داشته باشد باید همان استفاده شود."""

    name_to_code, code_to_name, buckets, synonyms = _sample_crosswalk()
    cfg = BuildConfig()
    included_col = "شامل گروه های آزمایشی"
    insp = pd.DataFrame(
        {
            COL_MENTOR_ID: ["EMP-4"],
            COL_MENTOR_NAME: ["پشتیبان د"],
            COL_MANAGER_NAME: ["مدیر د"],
            included_col: ["27"],
        }
    )

    base_df, unseen_groups, unmatched_schools = _prepare_base_rows(
        insp,
        cfg=cfg,
        name_to_code=name_to_code,
        code_to_name=code_to_name,
        buckets=buckets,
        synonyms=synonyms,
        school_name_to_code={},
        code_to_name_school={},
        group_cols=[],
        school_cols=[],
        gender_col=None,
        included_col=included_col,
    )

    assert unseen_groups == []
    assert unmatched_schools == []
    assert base_df.iloc[0]["group_pairs"] == [("یازدهم ریاضی", 27)]


def test_prepare_base_rows_raises_without_included_column() -> None:
    name_to_code, code_to_name, buckets, synonyms = _sample_crosswalk()
    cfg = BuildConfig()
    insp = pd.DataFrame(
        {
            COL_MENTOR_ID: ["EMP-legacy"],
            COL_MENTOR_NAME: ["پشتیبان legacy"],
            COL_MANAGER_NAME: ["مدیر legacy"],
            COL_GROUP: ["27"],
        }
    )

    with pytest.raises(KeyError):
        _prepare_base_rows(
            insp,
            cfg=cfg,
            name_to_code=name_to_code,
            code_to_name=code_to_name,
            buckets=buckets,
            synonyms=synonyms,
            school_name_to_code={},
            code_to_name_school={},
            group_cols=[COL_GROUP],
            school_cols=[],
            gender_col=None,
            included_col=COL_GROUP_INCLUDED,
        )
