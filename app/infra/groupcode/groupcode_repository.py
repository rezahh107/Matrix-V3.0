from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from app.core.common.columns import canonicalize_headers
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
        canonical = canonicalize_headers(df, header_mode="en")
        missing = [col for col in self.REQUIRED_COLUMNS if col not in canonical.columns]
        if missing:
            raise DatabasePreparationError(
                path=str(path),
                reason="ستون‌های الزامی group_code موجود نیست.",
                hint=", ".join(missing),
            )
        normalized = coerce_int_columns(canonical, ["group_code", "grade"])
        if "is_active" not in normalized.columns:
            normalized = normalized.copy()
            normalized["is_active"] = pd.Series([1] * len(normalized), dtype="Int64")
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
