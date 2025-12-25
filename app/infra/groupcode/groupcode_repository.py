from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from app.core.common.columns import canonicalize_headers
from app.core.common.domain import VALID_GROUP_CODES
from app.infra.db.reference_tables import ReferenceTableStatus, status_from_meta
from app.infra.errors import DatabasePreparationError
from app.infra.io_utils import read_excel_first_sheet
from app.infra.local_database import LocalDatabase
from app.infra.reference_repository import SQLiteReferenceRepository
from app.infra.sqlite_types import coerce_int_columns

__all__ = ["GroupCodeRepository"]


class GroupCodeRepository:
    """مخزن group_code با import از فایل crosswalk."""

    REQUIRED_COLUMNS: tuple[str, ...] = (
        "group_code",
        "level",
        "grade",
        "track",
    )

    _PERSIAN_HEADER_ALIASES: dict[str, str] = {
        "کد گروه": "group_code",
        "کدرشته": "group_code",
        "مقطع تحصیلی": "level",
        "پایه": "grade",
        "رشته": "track",
        "گروه آزمایشی": "experimental_group",
    }

    _ALLOWED_LEVELS: tuple[str, ...] = (
        "دبستان",
        "متوسطه اول",
        "متوسطه دوم",
        "هنرستان",
        "کنکوری",
    )

    _GRADE_WORD_BY_NUMBER: dict[int, str] = {
        2: "دوم",
        3: "سوم",
        4: "چهارم",
        5: "پنجم",
        6: "ششم",
        7: "هفتم",
        8: "هشتم",
        9: "نهم",
        10: "دهم",
        11: "یازدهم",
        12: "دوازدهم",
    }

    def __init__(self, db: LocalDatabase) -> None:
        self._db = db
        self._repo = SQLiteReferenceRepository(
            db=db,
            table_name="groupcodes",
            int_columns=("group_code", "grade"),
            unique_columns=("group_code",),
        )

    def import_from_excel(
        self, path: Path, *, clear_before: bool = True, version_tag: str | None = None
    ) -> ReferenceTableStatus:
        df = read_excel_first_sheet(path)
        normalized = self._normalize_import_frame(df)
        normalized = coerce_int_columns(normalized, ["group_code", "grade"])
        self._validate_import_frame(normalized)
        if "is_active" not in normalized.columns:
            normalized = normalized.copy()
            normalized["is_active"] = pd.Series([1] * len(normalized), dtype="Int64")
        imported_at = datetime.utcnow()
        normalized["version_tag"] = version_tag or path.stem
        normalized["source_filename"] = path.name
        normalized["imported_at"] = imported_at.isoformat()
        self._repo.upsert_frame(
            normalized,
            source=str(path),
            version_tag=version_tag or path.stem,
            source_filename=path.name,
            imported_at=imported_at,
        )
        return status_from_meta("groupcodes", self._repo.last_refresh_meta())

    def status(self) -> ReferenceTableStatus:
        self._db.initialize()
        meta = self._repo.last_refresh_meta()
        if meta is not None and meta.row_count > 0:
            return status_from_meta("groupcodes", meta)

        count = 0
        try:
            with self._db.connect() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM groupcodes")
                row = cursor.fetchone()
                count = int(row[0]) if row and row[0] is not None else 0
        except Exception:
            count = 0

        if count > 0:
            return ReferenceTableStatus(
                table_name="groupcodes",
                row_count=count,
                version_tag="builtin:ssot",
            )

        return status_from_meta("groupcodes", meta)

    def _normalize_import_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        canonical_fa = canonicalize_headers(df, header_mode="fa")
        rename_map: dict[str, str] = {}
        for column in canonical_fa.columns:
            target = self._PERSIAN_HEADER_ALIASES.get(column)
            if target:
                rename_map[column] = target
        normalized = canonical_fa.rename(columns=rename_map)
        canonical_en = canonicalize_headers(normalized, header_mode="en")
        missing = [col for col in self.REQUIRED_COLUMNS if col not in canonical_en.columns]
        if missing:
            raise DatabasePreparationError(
                path="groupcodes.xlsx",
                reason="ستون‌های الزامی group_code موجود نیست.",
                hint=", ".join(missing),
            )
        columns = [
            "group_code",
            "level",
            "grade",
            "track",
            *(col for col in ("is_active", "experimental_group") if col in canonical_en.columns),
        ]
        return canonical_en[columns].copy()

    def _validate_import_frame(self, df: pd.DataFrame) -> None:
        invalid_codes = [code for code in df["group_code"] if int(code) not in VALID_GROUP_CODES]
        if invalid_codes:
            raise DatabasePreparationError(
                path="groupcodes.xlsx",
                reason="کد گروه نامعتبر است.",
                hint=", ".join(str(code) for code in sorted(set(invalid_codes))),
            )
        invalid_levels = [level for level in df["level"] if level not in self._ALLOWED_LEVELS]
        if invalid_levels:
            raise DatabasePreparationError(
                path="groupcodes.xlsx",
                reason="سطح تحصیلی نامعتبر است.",
                hint=", ".join(sorted(set(map(str, invalid_levels)))),
            )
        if not pd.api.types.is_integer_dtype(df["grade"].dtype):
            raise DatabasePreparationError(
                path="groupcodes.xlsx",
                reason="ستون پایه باید عددی باشد.",
                hint="grade",
            )

    def load_crosswalk_groups_frame(self) -> pd.DataFrame:
        self._db.initialize()
        frame = self._repo.load_frame()
        if frame.empty:
            raise DatabasePreparationError(
                path="sqlite",
                reason="جدول groupcodes خالی است.",
                hint="از تب Database فایل کدگروه را وارد کنید.",
            )

        columns = ["group_code", "level", "grade", "track"]
        missing = [col for col in columns if col not in frame.columns]
        if missing:
            raise DatabasePreparationError(
                path="sqlite",
                reason="ستون‌های groupcodes ناقص است.",
                hint=", ".join(missing),
            )

        prepared = frame[columns].copy()
        prepared["گروه آزمایشی"] = prepared.apply(self._build_group_name, axis=1)
        prepared["کد گروه"] = prepared["group_code"].astype(int)
        prepared["مقطع تحصیلی"] = prepared["level"].astype(str)
        result = prepared[["گروه آزمایشی", "کد گروه", "مقطع تحصیلی"]].copy()
        result["گروه آزمایشی"] = result["گروه آزمایشی"].apply(self._normalize_space)
        result["کدرشته"] = result["کد گروه"]
        sorted_result = result.sort_values("کد گروه").reset_index(drop=True)
        return sorted_result

    @property
    def database(self) -> LocalDatabase:
        """Expose underlying LocalDatabase for coordinated operations."""

        return self._db

    def load_canonical_frame(self) -> pd.DataFrame:
        """Load the canonical groupcodes frame from SQLite for parity checks."""

        frame = self._repo.load_frame()
        ordered_columns = [
            "group_code",
            "level",
            "grade",
            "track",
            "is_active",
        ]
        available_columns = [col for col in ordered_columns if col in frame.columns]
        return frame[available_columns].copy()

    def _build_group_name(self, row: pd.Series) -> str:
        level = str(row.get("level", "")).strip()
        grade = int(row.get("grade", 0)) if pd.notna(row.get("grade")) else 0
        track = str(row.get("track", "")).strip()
        grade_word = self._GRADE_WORD_BY_NUMBER.get(grade, "")

        if level == "دبستان":
            return f"{grade_word} دبستان".strip()
        if level == "متوسطه اول":
            return grade_word
        if level in {"متوسطه دوم", "هنرستان"}:
            return f"{grade_word} {track}".strip()
        if level == "کنکوری":
            if track in {"هنر", "منحصرا زبان"}:
                return track
            return f"{self._GRADE_WORD_BY_NUMBER.get(grade, grade_word)} {track}".strip()
        return track or grade_word

    @staticmethod
    def _normalize_space(value: str) -> str:
        return " ".join(str(value).split())
