"""مدیریت دیتابیس‌های سالانه برای LocalDatabase."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.infra.local_database import LocalDatabase


@dataclass(frozen=True)
class YearDatabaseInfo:
    """اطلاعات خلاصهٔ پایگاه دادهٔ یک سال تحصیلی."""

    year_id: str
    path: Path
    schema_version: int | None
    size_bytes: int


class YearDatabaseManager:
    """مدیریت مسیر و چرخهٔ حیات پایگاه‌های دادهٔ سالانه."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _year_path(self, year_id: str) -> Path:
        safe = year_id.replace("/", "-").replace(" ", "_")
        return self.base_dir / f"smart_alloc_{safe}.sqlite"

    def list_years(self) -> List[YearDatabaseInfo]:
        """برگرداندن فهرست سال‌های موجود به‌صورت مرتب."""

        infos: List[YearDatabaseInfo] = []
        for path in sorted(self.base_dir.glob("smart_alloc_*.sqlite")):
            year_id = path.stem.replace("smart_alloc_", "")
            db = LocalDatabase(path)
            version = self._read_version(db)
            size = path.stat().st_size if path.exists() else 0
            infos.append(YearDatabaseInfo(year_id=year_id, path=path, schema_version=version, size_bytes=size))
        return infos

    def create_year(self, year_id: str) -> LocalDatabase:
        """ایجاد پایگاه دادهٔ جدید برای سال و مقداردهی Schema."""

        path = self._year_path(year_id)
        db = LocalDatabase(path, academic_year=year_id)
        db.initialize()
        with db._open_connection() as conn:  # type: ignore[attr-defined]
            db._ensure_year_meta(conn)
        return db

    def open_year(self, year_id: str) -> LocalDatabase:
        """باز کردن پایگاه دادهٔ موجود؛ در صورت نبود ایجاد می‌شود."""

        path = self._year_path(year_id)
        if not path.exists():
            return self.create_year(year_id)
        db = LocalDatabase(path, academic_year=year_id)
        db.initialize()
        return db

    @staticmethod
    def _read_version(db: LocalDatabase) -> int | None:
        try:
            with db.connect() as conn:
                cursor = conn.execute("SELECT schema_version FROM schema_meta WHERE id = 1")
                row = cursor.fetchone()
                return int(row[0]) if row else None
        except Exception:
            return None
