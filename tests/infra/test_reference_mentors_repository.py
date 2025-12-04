from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.core.canonical_frames import POOL_JOIN_KEY_DUPLICATES_ATTR, canonicalize_pool_frame
from app.core.policy_loader import load_policy
from app.infra.errors import JoinKeyValidationError
from app.infra.local_database import LocalDatabase
from app.infra.reference_mentors_repository import (
    _POOL_JOIN_KEY_QA_ATTR,
    import_mentor_pool_from_excel,
    load_mentor_pool_from_cache,
)
from app.infra.references.schools import (
    import_school_crosswalk_from_excel,
    import_school_report_from_excel,
)


def _write_pool_excel(df: pd.DataFrame, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)


def test_mentor_pool_cache_roundtrip(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    raw = pd.DataFrame(
        {
            "پشتیبان": ["الف", "ب"],
            "کد کارمندی پشتیبان": ["M1", "M2"],
            "کدرشته": [27, 27],
            "گروه آزمایشی": ["27", "27"],
            "جنسیت": [1, 0],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3581],
            "remaining_capacity": [2, 3],
        }
    )
    excel_path = tmp_path / "pool.xlsx"
    _write_pool_excel(raw, excel_path)

    normalized = import_mentor_pool_from_excel(excel_path, db=db, policy=policy)
    loaded = load_mentor_pool_from_cache(db=db, policy=policy)

    assert list(loaded.dtypes[policy.join_keys]) == ["Int64"] * len(policy.join_keys)
    assert {"policy_version", "ssot_version", "pool_hash"}.issubset(loaded.columns)
    comparable_columns = [
        col for col in normalized.columns if col in loaded.columns and col not in {"pool_hash"}
    ]
    assert_frame_equal(
        loaded.sort_values(by="کد کارمندی پشتیبان")[comparable_columns].reset_index(drop=True),
        normalized.sort_values(by="کد کارمندی پشتیبان")[comparable_columns].reset_index(drop=True),
        check_dtype=False,
    )


def test_import_pool_derives_join_keys_from_alias_inputs(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    schools_df = pd.DataFrame({"کد مدرسه": [3581], "نام مدرسه": ["دبیرستان نمونه"]})
    schools_path = tmp_path / "schools.xlsx"
    _write_pool_excel(schools_df, schools_path)
    import_school_report_from_excel(schools_path, db=db)

    crosswalk_path = tmp_path / "crosswalk.xlsx"
    with pd.ExcelWriter(crosswalk_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "گروه آزمایشی": [27],
                "کد گروه": [27],
                "مقطع تحصیلی": ["دوازدهم"],
            }
        ).to_excel(writer, sheet_name="پایه تحصیلی (گروه آزمایشی)", index=False)
    import_school_crosswalk_from_excel(crosswalk_path, db=db)

    inspactor_df = pd.DataFrame(
        {
            "نام پشتیبان": ["پشتیبان A"],
            "نام مدیر": ["مرکز"],
            "کد کارمندی پشتیبان": ["M-1"],
            "گروه آزمایشی": ["27"],
            "جنسیت": ["پسر"],
            "نام مدرسه 1": ["دبیرستان نمونه"],
        }
    )
    insp_path = tmp_path / "insp.xlsx"
    _write_pool_excel(inspactor_df, insp_path)

    normalized = import_mentor_pool_from_excel(
        insp_path, db=db, policy=policy, pool_source="inspactor"
    )

    for join_key in policy.join_keys:
        assert join_key in normalized.columns
        assert str(normalized[join_key].dtype) == "Int64"
    assert int(normalized["کدرشته"].iloc[0]) == 27
    assert int(normalized["کد مدرسه"].iloc[0]) == 3581


def test_import_pool_reports_unmapped_group(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    schools_df = pd.DataFrame({"کد مدرسه": [3581], "نام مدرسه": ["نمونه"]})
    schools_path = tmp_path / "schools.xlsx"
    _write_pool_excel(schools_df, schools_path)
    import_school_report_from_excel(schools_path, db=db)

    crosswalk_path = tmp_path / "crosswalk.xlsx"
    with pd.ExcelWriter(crosswalk_path, engine="openpyxl") as writer:
        pd.DataFrame({"گروه آزمایشی": [27], "کد گروه": [27], "مقطع تحصیلی": ["دوازدهم"]}).to_excel(
            writer, sheet_name="پایه تحصیلی (گروه آزمایشی)", index=False
        )
    import_school_crosswalk_from_excel(crosswalk_path, db=db)

    inspactor_df = pd.DataFrame(
        {
            "نام پشتیبان": ["پشتیبان A"],
            "نام مدیر": ["مرکز"],
            "کد کارمندی پشتیبان": ["M-1"],
            "گروه آزمایشی": ["نامعلوم"],
            "جنسیت": ["پسر"],
            "نام مدرسه 1": ["نمونه"],
        }
    )
    insp_path = tmp_path / "insp.xlsx"
    _write_pool_excel(inspactor_df, insp_path)

    with pytest.raises(JoinKeyValidationError):
        import_mentor_pool_from_excel(insp_path, db=db, policy=policy)


def test_import_pool_reports_unmapped_school(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    schools_df = pd.DataFrame({"کد مدرسه": [3581], "نام مدرسه": ["نمونه"]})
    schools_path = tmp_path / "schools.xlsx"
    _write_pool_excel(schools_df, schools_path)
    import_school_report_from_excel(schools_path, db=db)

    crosswalk_path = tmp_path / "crosswalk.xlsx"
    with pd.ExcelWriter(crosswalk_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {"گروه آزمایشی": ["27"], "کد گروه": [27], "مقطع تحصیلی": ["دوازدهم"]}
        ).to_excel(writer, sheet_name="پایه تحصیلی (گروه آزمایشی)", index=False)
    import_school_crosswalk_from_excel(crosswalk_path, db=db)

    inspactor_df = pd.DataFrame(
        {
            "نام پشتیبان": ["پشتیبان A"],
            "نام مدیر": ["مرکز"],
            "کد کارمندی پشتیبان": ["M-1"],
            "گروه آزمایشی": ["27"],
            "جنسیت": ["پسر"],
            "نام مدرسه 1": ["مدرسه ناشناخته"],
        }
    )
    insp_path = tmp_path / "insp_school.xlsx"
    _write_pool_excel(inspactor_df, insp_path)

    normalized = import_mentor_pool_from_excel(insp_path, db=db, policy=policy)

    issues = normalized.attrs.get(_POOL_JOIN_KEY_QA_ATTR, [])
    reasons = {item["reason"] for item in issues}
    assert "SCHOOL_NOT_FOUND" in reasons
    assert int(normalized["کد مدرسه"].iloc[0]) == 0


def test_import_pool_deduplicates_exact_rows(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    schools_df = pd.DataFrame({"کد مدرسه": [3581], "نام مدرسه": ["نمونه"]})
    schools_path = tmp_path / "schools.xlsx"
    _write_pool_excel(schools_df, schools_path)
    import_school_report_from_excel(schools_path, db=db)

    crosswalk_path = tmp_path / "crosswalk.xlsx"
    with pd.ExcelWriter(crosswalk_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {"گروه آزمایشی": ["27"], "کد گروه": [27], "مقطع تحصیلی": ["دوازدهم"]}
        ).to_excel(writer, sheet_name="پایه تحصیلی (گروه آزمایشی)", index=False)
    import_school_crosswalk_from_excel(crosswalk_path, db=db)

    inspactor_df = pd.DataFrame(
        {
            "نام پشتیبان": ["پشتیبان A", "پشتیبان A"],
            "نام مدیر": ["مرکز", "مرکز"],
            "کد کارمندی پشتیبان": ["", ""],
            "گروه آزمایشی": ["27", "27"],
            "جنسیت": ["پسر", "پسر"],
            "نام مدرسه 1": ["نمونه", "نمونه"],
        }
    )
    insp_path = tmp_path / "insp.xlsx"
    _write_pool_excel(inspactor_df, insp_path)

    normalized = import_mentor_pool_from_excel(insp_path, db=db, policy=policy)

    assert len(normalized) == 1
    assert normalized["کد کارمندی پشتیبان"].iloc[0] == ""


def test_import_pool_respects_existing_join_keys(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    raw = pd.DataFrame(
        {
            "پشتیبان": ["الف"],
            "کد کارمندی پشتیبان": ["M1"],
            "کدرشته": [27],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [2],
            "مالی حکمت بنیاد": [1],
            "کد مدرسه": [3581],
        }
    )
    excel_path = tmp_path / "pool.xlsx"
    _write_pool_excel(raw, excel_path)

    normalized = import_mentor_pool_from_excel(excel_path, db=db, policy=policy)
    issues = normalized.attrs.get(_POOL_JOIN_KEY_QA_ATTR, [])
    assert issues == []
    assert int(normalized["کدرشته"].iloc[0]) == 27
    assert int(normalized["کد مدرسه"].iloc[0]) == 3581


def test_pool_missing_columns_error_mentions_canonical_keys() -> None:
    policy = load_policy()

    # فراخوانی مستقیم canonicalize_pool_frame برای بررسی متن خطا
    raw = pd.DataFrame({"کد کارمندی پشتیبان": ["M1"], "پشتیبان": ["الف"]})

    with pytest.raises(KeyError) as exc_info:
        canonicalize_pool_frame(raw, policy=policy, sanitize_pool=False)

    assert "canonical join-key" in str(exc_info.value)
    assert "join_keys_and_pool_explainer" in str(exc_info.value)


def test_import_pool_reports_unknown_center_and_finance(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    schools_df = pd.DataFrame({"کد مدرسه": [3581], "نام مدرسه": ["نمونه"]})
    schools_path = tmp_path / "schools.xlsx"
    _write_pool_excel(schools_df, schools_path)
    import_school_report_from_excel(schools_path, db=db)

    crosswalk_path = tmp_path / "crosswalk.xlsx"
    with pd.ExcelWriter(crosswalk_path, engine="openpyxl") as writer:
        pd.DataFrame(
            {"گروه آزمایشی": ["27"], "کد گروه": [27], "مقطع تحصیلی": ["دوازدهم"]}
        ).to_excel(writer, sheet_name="پایه تحصیلی (گروه آزمایشی)", index=False)
    import_school_crosswalk_from_excel(crosswalk_path, db=db)

    inspactor_df = pd.DataFrame(
        {
            "نام پشتیبان": ["پشتیبان A"],
            "نام مدیر": ["مدیر ناشناخته"],
            "کد کارمندی پشتیبان": ["M-1"],
            "گروه آزمایشی": ["27"],
            "جنسیت": ["پسر"],
            "مالی حکمت بنیاد": [999],
            "نام مدرسه 1": ["نمونه"],
        }
    )
    insp_path = tmp_path / "insp_center_finance.xlsx"
    _write_pool_excel(inspactor_df, insp_path)

    normalized = import_mentor_pool_from_excel(insp_path, db=db, policy=policy)

    issues = normalized.attrs.get(_POOL_JOIN_KEY_QA_ATTR, [])
    reasons = {item["reason"] for item in issues}
    assert "CENTER_FALLBACK_WILDCARD" in reasons
    assert "FINANCE_UNKNOWN" in reasons
    assert int(normalized["مالی حکمت بنیاد"].iloc[0]) == policy.finance_variants[0]


def test_import_pool_reports_duplicate_composite_keys(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    duplicated_pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m1"],
            "کد کارمندی پشتیبان": ["E1", "E1"],
            "کدرشته": [27, 27],
            "گروه آزمایشی": ["27", "27"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3581],
        }
    )
    excel_path = tmp_path / "dup_pool.xlsx"
    _write_pool_excel(duplicated_pool, excel_path)

    normalized = import_mentor_pool_from_excel(excel_path, db=db, policy=policy)

    duplicates = normalized.attrs.get(POOL_JOIN_KEY_DUPLICATES_ATTR)
    assert duplicates is not None
    assert isinstance(duplicates, pd.DataFrame)
    assert len(duplicates) == 2
    mentor_column = "mentor_id" if "mentor_id" in duplicates.columns else "کد کارمندی پشتیبان"
    assert set(duplicates[mentor_column]) == {"m1"}


def test_import_pool_allows_same_mentor_multiple_join_keys(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")

    expanded_pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m1"],
            "کد کارمندی پشتیبان": ["E1", "E1"],
            "کدرشته": [27, 33],
            "گروه آزمایشی": ["27", "33"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 2],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3582],
        }
    )
    excel_path = tmp_path / "expanded_pool.xlsx"
    _write_pool_excel(expanded_pool, excel_path)

    normalized = import_mentor_pool_from_excel(excel_path, db=db, policy=policy)
    assert len(normalized) == 2
