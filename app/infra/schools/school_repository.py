from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from app.infra.db.reference_tables import ReferenceTableStatus, status_from_meta
from app.infra.errors import DatabasePreparationError
from app.infra.io_utils import read_excel_first_sheet
from app.infra.local_database import LocalDatabase
from app.infra.reference_repository import SQLiteReferenceRepository
from app.infra.schools.header_resolver import SchoolHeaderResolver
from app.infra.sqlite_types import coerce_int_columns

__all__ = ["SchoolRepository"]


class SchoolRepository:
    """مخزن مدارس مبتنی‌بر LocalDatabase با جریان import از Excel."""

    REQUIRED_COLUMNS: tuple[str, ...] = (
        "کد مدرسه",
        "نام مدرسه",
        "مرکز گلستان صدرا",
        "جنسیت",
    )

    def __init__(self, db: LocalDatabase) -> None:
        self._db = db
        self._repo = SQLiteReferenceRepository(
            db=db,
            table_name="schools",
            int_columns=("کد مدرسه", "مرکز گلستان صدرا", "جنسیت"),
            unique_columns=("کد مدرسه",),
        )
        self._header_resolver = SchoolHeaderResolver(
            required_fields=list(self.REQUIRED_COLUMNS), header_mode="fa"
        )

    def import_from_excel(
        self, path: Path, *, clear_before: bool = True, version_tag: str | None = None
    ) -> ReferenceTableStatus:
        df = read_excel_first_sheet(path)
        resolution = self._header_resolver.resolve(df)
        if not resolution.can_continue:
            raise DatabasePreparationError(
                path=str(path),
                reason="ستون‌های الزامی مدارس در فایل موجود نیست.",
                hint=", ".join(resolution.missing_fields),
            )
        normalized = coerce_int_columns(
            resolution.resolved_df, ["کد مدرسه", "مرکز گلستان صدرا", "جنسیت"]
        )
        if "فعال" not in normalized.columns:
            normalized = normalized.copy()
            normalized["فعال"] = pd.Series([1] * len(normalized), dtype="Int64")
        imported_at = datetime.utcnow()
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
        return status_from_meta("schools", self._repo.last_refresh_meta())

    def status(self) -> ReferenceTableStatus:
        return status_from_meta("schools", self._repo.last_refresh_meta())

    @property
    def database(self) -> LocalDatabase:
        """Expose underlying LocalDatabase for coordinated operations."""

        return self._db

    def load_canonical_frame(self) -> pd.DataFrame:
        """Load the canonical schools frame from SQLite for parity checks.

        This helper is read-only and returns the stored schools DataFrame with
        standard columns and integer coercions, without mutating any state.
        """

        frame = self._repo.load_frame()
        ordered_columns = [
            "کد مدرسه",
            "نام مدرسه",
            "مرکز گلستان صدرا",
            "جنسیت",
            "فعال",
        ]
        available_columns = [col for col in ordered_columns if col in frame.columns]
        return frame[available_columns].copy()
