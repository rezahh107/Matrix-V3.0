# file: app/infra/local_database.py
"""پایگاه دادهٔ محلی SQLite برای نگهداشت تاریخچه و مراجع.

این ماژول یک لایهٔ نازک روی :mod:`sqlite3` است تا بدون وابستگی خارجی
لاگ اجرای تخصیص و داده‌های مرجع (مدارس و Crosswalk) را ذخیره کند.
Schema به‌صورت دترمینیستیک ساخته می‌شود و نسخهٔ آن در ``schema_meta``
ثبت و در هر بار مقداردهی اولیه اعتبارسنجی می‌شود.

نمونهٔ استفادهٔ سریع:

>>> db = LocalDatabase(Path("smart_alloc.db"))
>>> db.initialize()
>>> run_id = db.insert_run(sample_run_record)
>>> db.insert_run_metrics([RunMetricRow(run_id, "SCHOOL.students_total", 10.0)])
"""
from __future__ import annotations

import io
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd
from pandas.api.types import is_integer_dtype

from app.infra.errors import (
    DatabaseCorruptError,
    DatabaseOperationError,
    DatabasePreparationError,
    DatabaseSchemaMismatchError,
    ReferenceDataMissingError,
    SchemaVersionMismatchError,
)
from app.infra.sqlite_config import configure_connection
from app.infra.sqlite_types import coerce_int_columns as _sqlite_coerce_int_columns
from app.infra.sqlite_types import coerce_int_like as _sqlite_coerce_int_like

_SCHEMA_VERSION = 9
_POLICY_VERSION = "1.0.3"
_SSOT_VERSION = "1.0.2"
_ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

logger = logging.getLogger(__name__)


class DatabaseHealthStatus(str, Enum):
    """وضعیت کلی پایگاه داده برای نمایش در UI."""

    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DatabaseHealthSummary:
    """خلاصه وضعیت پایگاه‌داده برای نمایش در نوار وضعیت."""

    status: DatabaseHealthStatus
    message: str
    counts: Dict[str, int]
    last_updated: Optional[datetime] = None


@dataclass(frozen=True)
class TableSchemaDiagnostics:
    """تشخیص ساختار یک جدول مهم در پایگاه داده."""

    name: str
    exists: bool
    columns: list[str]
    missing_required_columns: list[str]
    row_count: int | None


@dataclass(frozen=True)
class DatabaseSchemaDiagnostics:
    """گزارش کامل وضعیت Schema برای نمایش و عیب‌یابی."""

    path: str
    module_path: str
    expected_schema_version: int
    actual_schema_version: int | None
    tables: list[TableSchemaDiagnostics]


@dataclass(frozen=True)
class RunRecord:
    """نمایندهٔ ردیف جدول ``runs`` برای یک اجرای تخصیص."""

    run_uuid: str
    started_at: datetime
    finished_at: datetime
    policy_version: str
    ssot_version: str
    entrypoint: str
    cli_args: str | None
    db_path: str | None
    input_files_json: str
    input_hashes_json: str
    total_students: int | None
    total_allocated: int | None
    total_unallocated: int | None
    history_metrics_json: str | None
    qa_summary_json: str | None
    status: str
    message: str | None


@dataclass(frozen=True)
class RunMetricRow:
    """ردیف جدول ``run_metrics`` به‌صورت کلید/مقدار."""

    run_id: int
    metric_key: str
    metric_value: float


@dataclass(frozen=True)
class QaSummaryRow:
    """خلاصهٔ QA برای یک اجرای تخصیص (یک ردیف در ``qa_summary``)."""

    run_id: int
    violation_code: str
    severity: str
    count: int


class LocalDatabase:
    """کلاس مدیریت اتصال و Schema پایگاه دادهٔ محلی.

    این کلاس رفتار را تغییر نمی‌دهد و فقط یک API ساده برای ایجاد
    جداول و درج داده در اختیار Infra قرار می‌دهد.
    """

    def __init__(self, path: Path, *, academic_year: str | None = None) -> None:
        self.path = path
        self.academic_year = academic_year
        self._required_tables: dict[str, list[str]] = {
            "students_cache": [
                "student_id",
                "کد ملی",
                "کدرشته",
                "گروه آزمایشی",
                "جنسیت",
                "دانش آموز فارغ",
                "مرکز گلستان صدرا",
                "مالی حکمت بنیاد",
                "کد مدرسه",
            ],
            "mentor_pool_cache": [
                "mentor_id",
                "کد کارمندی پشتیبان",
                "کدرشته",
                "گروه آزمایشی",
                "جنسیت",
                "دانش آموز فارغ",
                "مرکز گلستان صدرا",
                "مالی حکمت بنیاد",
                "کد مدرسه",
                "remaining_capacity",
                "allocations_new",
                "occupancy_ratio",
            ],
        }

    def _open_connection(self) -> sqlite3.Connection:
        """ایجاد اتصال پیکربندی‌شده با PRAGMA های یکسان."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        return configure_connection(sqlite3.connect(self.path))

    def connect(self) -> sqlite3.Connection:
        """برگشت اتصال SQLite با تنظیمات استاندارد."""

        return self._open_connection()

    def get_schema_version(self) -> int | None:
        """بازگرداندن نسخهٔ Schema بدون نیاز به برون‌ریزی پرس‌وجو."""

        try:
            with self._open_connection() as conn:
                return self._get_schema_version(conn)
        except sqlite3.Error:
            return None

    def get_schema_diagnostics(self) -> DatabaseSchemaDiagnostics:
        """دریافت گزارش کامل Schema بدون تغییر در پایگاه داده.

        این تابع حتی در صورت ناسازگاری، ساختار فعلی را خوانده و ستون‌های
        الزامی جداول کلیدی (students_cache و mentor_pool_cache) را بررسی
        می‌کند تا برای UI/CLI قابل‌نمایش باشد.
        """

        tables: list[TableSchemaDiagnostics] = []
        actual_version: int | None = None
        try:
            with self._open_connection() as conn:
                actual_version = self._get_schema_version(conn)
                for name, required_cols in self._required_tables.items():
                    tables.append(
                        self._collect_table_diagnostics(conn, name, required_cols)
                    )
                # جدول runs نیز برای ردیابی سلامت مهم است
                tables.append(
                    self._collect_table_diagnostics(conn, "runs", [])
                )
        except sqlite3.Error:
            logger.exception("Failed to read schema diagnostics for %s", self.path)

        return DatabaseSchemaDiagnostics(
            path=str(self.path),
            module_path=str(Path(__file__).resolve()),
            expected_schema_version=_SCHEMA_VERSION,
            actual_schema_version=actual_version,
            tables=tables,
        )

    def reset_full_database(self) -> Path | None:
        """بازنشانی کامل پایگاه‌داده با بکاپ‌گیری امن فایل.

        این متد فایل فعلی ``SQLite`` را (در صورت وجود) به یک فایل بکاپ با پسوند
        ``.bak-YYYYMMDD-HHMMSS`` منتقل می‌کند، سپس پایگاه‌دادهٔ اصلی را از ابتدا
        با ``initialize`` می‌سازد. اگر فایل وجود نداشته باشد، تنها ``initialize``
        اجرا می‌شود.

        Returns
        -------
        Path | None
            مسیر فایل بکاپ در صورت جابه‌جایی فایل اصلی، یا ``None`` زمانی که
            فایلی برای بکاپ وجود نداشت.

        مثال
        ------
        >>> db = LocalDatabase(Path("smart_alloc.db"))
        >>> backup = db.reset_full_database()
        >>> assert db.path.exists()
        """

        backup: Path | None = None
        if self.path.exists():
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
            backup = self.path.with_name(f"{self.path.name}.bak-{timestamp}")
            try:
                self.path.replace(backup)
            except OSError as exc:  # pragma: no cover - I/O failure
                raise DatabasePreparationError(
                    path=str(self.path),
                    reason="انتقال فایل برای بکاپ ممکن نشد.",
                    hint="دسترسی دیسک یا قفل فایل را بررسی کنید و دوباره تلاش نمایید.",
                ) from exc
        self.initialize()
        return backup

    def clear_caches(self) -> None:
        """پاک‌سازی جداول کش بدون حذف تاریخچه یا متادیتا.

        این متد فقط محتویات جداول کش (students_cache, mentor_pool_cache,
        managers_reference, forms_entries) را در یک تراکنش حذف می‌کند و سایر
        جداول مانند ``runs``، ``qa_summary`` یا تاریخچه را دست‌نخورده باقی
        می‌گذارد. اگر جدول کش در نسخه‌های قدیمی موجود نباشد، به‌طور ایمن
        صرف‌نظر می‌شود.

        Raises
        ------
        DatabaseOperationError
            اگر حذف تراکنشی جداول با خطا روبه‌رو شود.
        """

        cache_tables = [
            "students_cache",
            "mentor_pool_cache",
            "managers_reference",
            "forms_entries",
        ]
        try:
            with self._open_connection() as conn:
                existing = [table for table in cache_tables if _table_exists(conn, table)]
                if not existing:
                    return
                conn.execute("BEGIN")
                try:
                    for table in existing:
                        conn.execute(f'DELETE FROM "{table}"')
                    conn.commit()
                except sqlite3.Error as exc:
                    conn.rollback()
                    raise DatabaseOperationError(
                        reason="پاک‌سازی کش پایگاه‌داده ناکام ماند.",
                        hint="سلامت فایل یا دسترسی نوشتن را بررسی کنید و دوباره تلاش نمایید.",
                    ) from exc
        except DatabaseOperationError:
            raise
        except sqlite3.Error as exc:  # pragma: no cover - خطای غیرمنتظره اتصال
            raise DatabaseOperationError(
                reason="خطا در اتصال یا اجرای فرمان پاک‌سازی کش.",
                hint="مجوز نوشتن یا قفل بودن فایل را بررسی کنید.",
            ) from exc

    def backup_and_reset(self) -> Path | None:
        """[Deprecated] سازگار با نسخه‌های قدیمی؛ از ``reset_full_database`` استفاده کنید."""

        return self.reset_full_database()

    def initialize(self) -> None:
        """ایجاد Schema و اعتبارسنجی نسخه به‌صورت idempotent."""

        try:
            self._initialize_once()
        except SchemaVersionMismatchError:
            raise
        except sqlite3.OperationalError as exc:  # pragma: no cover - خطاهای عملیاتی قابل‌تشخیص
            if self._is_schema_mismatch_error(exc):
                raise DatabaseSchemaMismatchError(
                    path=str(self.path),
                    reason=f"ساختار پایگاه‌داده با نسخهٔ فعلی برنامه سازگار نیست: {exc}",
                    hint="فایل پایگاه‌داده را حذف کنید تا با Schema جدید بازسازی شود.",
                ) from exc
            if self._is_corruption_error(exc):
                logger.warning(
                    "Local DB appears corrupted at %s; backing up and recreating", self.path
                )
                backup = self._recover_corrupt_database()
                raise DatabaseCorruptError(
                    path=str(self.path),
                    reason="فایل پایگاه‌داده خراب است و بازسازی شد.",
                    hint="جهت ادامه، در صورت نیاز داده‌های مرجع را دوباره بارگذاری کنید و فرمان را مجدداً اجرا نمایید.",
                    backup_path=backup,
                ) from exc
            raise DatabasePreparationError(
                path=str(self.path),
                reason=str(exc),
                hint=(
                    "دسترسی فایل یا سلامت دیسک را بررسی کنید؛ در صورت تکرار، فایل پایگاه‌داده را حذف و دوباره بسازید."
                ),
            ) from exc
        except sqlite3.DatabaseError as exc:  # pragma: no cover - خطای پایگاه دادهٔ خراب
            if self._is_corruption_error(exc):
                logger.warning(
                    "Local DB appears corrupted at %s; backing up and recreating", self.path
                )
                backup = self._recover_corrupt_database()
                raise DatabaseCorruptError(
                    path=str(self.path),
                    reason="فایل پایگاه‌داده خراب است و بازسازی شد.",
                    hint="جهت ادامه، در صورت نیاز داده‌های مرجع را دوباره بارگذاری کنید و فرمان را مجدداً اجرا نمایید.",
                    backup_path=backup,
                ) from exc
            raise DatabasePreparationError(
                path=str(self.path),
                reason=str(exc),
                hint=(
                    "دسترسی فایل یا سلامت دیسک را بررسی کنید؛ در صورت تکرار، فایل پایگاه‌داده را حذف و دوباره بسازید."
                ),
            ) from exc
        except sqlite3.Error as exc:  # pragma: no cover - خطاهای غیرمنتظره
            raise DatabasePreparationError(
                path=str(self.path),
                reason=str(exc),
                hint="مسیر فایل یا مجوز نوشتن را بررسی کنید.",
            ) from exc
        logger.debug("Local DB schema ensured at %s", self.path)

    def _initialize_once(self) -> None:
        """اجرای یک‌بارهٔ مسیر ساخت/مهاجرت Schema بدون بازیابی.

        این تابع یک اتصال جدید باز می‌کند، نسخهٔ Schema را می‌سنجد، در صورت
        نیاز مهاجرت می‌دهد و سپس اعتبارسنجی می‌کند. وظیفهٔ بازیابی پایگاه
        دادهٔ خراب بر عهدهٔ ``initialize`` است.
        """

        with self._open_connection() as conn:
            self._ensure_schema_meta_table(conn)
            existing_version = self._get_schema_version(conn)
            if existing_version is None:
                self._ensure_schema(conn)
                self._ensure_schema_meta_row(conn, version=_SCHEMA_VERSION)
                # NEW: keep year meta support from main
                self._ensure_year_meta(conn)
            elif existing_version < 2:
                raise SchemaVersionMismatchError(
                    expected_version=_SCHEMA_VERSION,
                    actual_version=existing_version,
                    message="نسخهٔ Schema بسیار قدیمی است و پشتیبانی نمی‌شود؛ پایگاه داده را بازسازی کنید.",
                )
            elif existing_version < _SCHEMA_VERSION:
                try:
                    self._migrate_schema(conn, from_version=existing_version)
                except sqlite3.Error as exc:
                    diagnostics = {name: req for name, req in self._required_tables.items()}
                    raise DatabaseSchemaMismatchError(
                        path=str(self.path),
                        reason=f"مهاجرت Schema ناکام ماند (ساختار ناسازگار): {exc}",
                        hint="فایل را حذف یا بازنشانی کنید تا Schema جدید اعمال شود.",
                        diagnostics=diagnostics,
                    ) from exc
            elif existing_version > _SCHEMA_VERSION:
                raise SchemaVersionMismatchError(
                    expected_version=_SCHEMA_VERSION,
                    actual_version=existing_version,
                    message="نسخهٔ Schema پایگاه داده از نسخهٔ برنامه جدیدتر است.",
                )

            # پس از مهاجرت، نسخهٔ جاری خوانده می‌شود اما ترمیم ستون‌ها تنها زمانی
            # مجاز است که پایگاه داده پیش‌تر در نسخهٔ سازگار بوده یا تازه ساخته
            # شده باشد؛ برای نسخه‌های قدیمی‌تر پیام بازسازی باید به کاربر برسد.
            current_version = self._get_schema_version(conn)
            migrated_from_older = existing_version is not None and existing_version < _SCHEMA_VERSION
            allow_repair = (
                (current_version is None or current_version >= _SCHEMA_VERSION)
                and not migrated_from_older
            )
            self._ensure_schema(conn, allow_repair=allow_repair)
            # NEW: ensure year meta also after migrations/schema ensure
            self._ensure_year_meta(conn)
            self._validate_schema_version(conn)
            self._assert_required_schema(conn)
            conn.commit()

    def _repair_required_schema(
        self, conn: sqlite3.Connection, table: str, missing_columns: list[str]
    ) -> bool:
        """رفع خودکار ستون‌های بحرانی برای انطباق با Schema جاری.

        این متد تنها برای ستون‌های شناخته‌شده و بدون نیاز به مهاجرت پیچیده
        اعمال می‌شود تا کاربران مجبور به بازنشانی کامل پایگاه‌داده در حالت‌های
        رایج (مثل نبودن ``student_id``) نشوند. در صورت انجام تغییر، ``True``
        برگردانده می‌شود تا اعتبارسنجی مجدد Schema صورت گیرد.
        """

        repaired = False

        if table == "students_cache" and "student_id" in missing_columns:
            _ensure_column_exists(
                conn,
                table="students_cache",
                column="student_id",
                definition="TEXT",
            )
            repaired = True

        if table == "mentor_pool_cache" and "گروه آزمایشی" in missing_columns:
            _ensure_column_exists(
                conn,
                table="mentor_pool_cache",
                column='"گروه آزمایشی"',
                definition="TEXT",
            )
            repaired = True

        return repaired

    def _recover_corrupt_database(self) -> Path | None:
        """پشتیبان‌گیری از فایل خراب و بازسازی پایگاه داده.

        - اگر فایل فعلی وجود داشته باشد، با پسوند ``.corrupt`` بکاپ می‌شود
          تا اطلاعات قبلی از دست نرود.
        - سپس مسیر فایل پاک و ``_initialize_once`` دوباره اجرا می‌شود تا
          Schema سالم ساخته شود.
        """
        backup: Path | None = None
        if self.path.exists():
            backup = self.path.with_suffix(self.path.suffix + ".corrupt")
            try:
                self.path.replace(backup)
            except OSError as exc:
                logger.exception("Failed to backup corrupt DB at %s", self.path)
                raise DatabaseCorruptError(
                    path=str(self.path),
                    reason="بکاپ‌گیری از پایگاه‌داده خراب ناکام ماند.",
                    hint="مجوز دسترسی یا قفل بودن فایل را بررسی کنید و در صورت لزوم فایل را به‌صورت دستی حذف کنید.",
                ) from exc
        self._initialize_once()
        return backup

    @staticmethod
    def _is_corruption_error(exc: sqlite3.Error) -> bool:
        """تشخیص پیام‌های خطای مرتبط با خراب بودن فایل SQLite."""
        message = str(exc).lower()
        return (
            "file is not a database" in message
            or "malformed" in message
        )

    @staticmethod
    def _is_schema_mismatch_error(exc: sqlite3.Error) -> bool:
        """تشخیص عدم سازگاری Schema بر اساس پیام SQLite."""

        message = str(exc).lower()
        return "no such column" in message or "has no column named" in message


    def insert_run(self, record: RunRecord) -> int:
        """درج ردیف جدید در جدول ``runs`` و بازگرداندن شناسه."""

        try:
            with self._open_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO runs (
                        run_uuid, started_at, finished_at, policy_version, ssot_version,
                        entrypoint, cli_args, db_path, input_files_json, input_hashes_json,
                        total_students, total_allocated, total_unallocated,
                        history_metrics_json, qa_summary_json, status, message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.run_uuid,
                        _to_iso(record.started_at),
                        _to_iso(record.finished_at),
                        record.policy_version,
                        record.ssot_version,
                        record.entrypoint,
                        record.cli_args,
                        record.db_path,
                        record.input_files_json,
                        record.input_hashes_json,
                        record.total_students,
                        record.total_allocated,
                        record.total_unallocated,
                        record.history_metrics_json,
                        record.qa_summary_json,
                        record.status,
                        record.message,
                    ),
                )
                conn.commit()
                return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            raise DatabaseOperationError("ثبت اجرای جدید در SQLite ناکام ماند.") from exc

    def insert_run_metrics(self, rows: Iterable[RunMetricRow]) -> None:
        """درج چندین ردیف KPI تاریخچه برای یک اجرا."""

        payload = [
            (
                row.run_id,
                row.metric_key,
                row.metric_value,
            )
            for row in rows
        ]
        if not payload:
            logger.debug("No metric rows to insert for run_metrics")
            return
        try:
            with self._open_connection() as conn:
                conn.executemany(
                    """
                    INSERT INTO run_metrics (
                        run_id, metric_key, metric_value
                    ) VALUES (?, ?, ?)
                    """,
                    payload,
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise DatabaseOperationError("ثبت KPI تاریخچه با خطا روبه‌رو شد.") from exc

    def insert_qa_summary(self, rows: Iterable[QaSummaryRow]) -> None:
        """ثبت خلاصهٔ QA برای یک اجرا."""

        payload = [
            (row.run_id, row.violation_code, row.severity, row.count) for row in rows
        ]
        if not payload:
            logger.debug("No QA rows to insert for qa_summary")
            return
        try:
            with self._open_connection() as conn:
                conn.executemany(
                    """
                    INSERT INTO qa_summary (run_id, violation_code, severity, count)
                    VALUES (?, ?, ?, ?)
                    """,
                    payload,
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise DatabaseOperationError("ثبت خلاصهٔ QA با خطا روبه‌رو شد.") from exc

    def fetch_runs(self) -> List[sqlite3.Row]:
        """بازیابی همهٔ اجراها (برای تست/دیباگ)."""

        with self._open_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM runs ORDER BY started_at ASC, id ASC"
            )
            return cursor.fetchall()

    def fetch_metrics_for_run(self, run_id: int) -> List[sqlite3.Row]:
        """بازیابی KPI تاریخچه برای یک شناسه اجرا."""

        with self._open_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM run_metrics WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            )
            return cursor.fetchall()

    def fetch_qa_summary(self, run_id: int) -> List[sqlite3.Row]:
        """بازیابی خلاصهٔ QA برای یک اجرا."""

        with self._open_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM qa_summary WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            )
            return cursor.fetchall()

    # ------------------------------------------------------------------
    # Snapshot های QA/Trace
    # ------------------------------------------------------------------
    def insert_trace_snapshot(
        self,
        *,
        run_id: int,
        trace_df: pd.DataFrame,
        summary_df: pd.DataFrame | None = None,
        history_info_df: pd.DataFrame | None = None,
    ) -> None:
        """ذخیرهٔ Snapshot تریس تخصیص برای یک اجرا.

        داده‌ها به‌صورت JSON دترمینیستیک ذخیره می‌شوند تا رفتار قابل‌آزمایش
        باشد و در مرحلهٔ بازیابی بدون تغییر semantics بازسازی شوند.
        """

        if trace_df is None:
            raise ValueError("دیتافریم تریس تهی است؛ ورودی معتبر بدهید.")
        payload = _serialize_dataframe(trace_df)
        summary_json = _serialize_dataframe(summary_df) if summary_df is not None else None
        history_json = (
            _serialize_dataframe(history_info_df) if history_info_df is not None else None
        )
        try:
            with self._open_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO trace_snapshots (
                        run_id, trace_json, summary_json, history_info_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (run_id, payload, summary_json, history_json),
                )
                conn.commit()
        except sqlite3.Error as exc:  # pragma: no cover - مسیر غیرمنتظره
            raise DatabaseOperationError("ثبت Snapshot تریس با خطا روبه‌رو شد.") from exc

    def fetch_trace_snapshot(
        self, run_id: int
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None]:
        """بازیابی Snapshot تریس برای یک اجرای مشخص."""

        with self._open_connection() as conn:
            cursor = conn.execute(
                """
                SELECT trace_json, summary_json, history_info_json
                FROM trace_snapshots WHERE run_id = ?
                """,
                (run_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None, None, None
        trace_df = _safe_deserialize_dataframe(row["trace_json"], label="trace_json")
        summary_df = _safe_deserialize_dataframe(row["summary_json"], label="summary_json")
        history_df = _safe_deserialize_dataframe(
            row["history_info_json"], label="history_info_json"
        )
        return trace_df, summary_df, history_df

    def insert_qa_snapshot(
        self,
        *,
        run_id: int,
        qa_summary_df: pd.DataFrame | None,
        qa_details_df: pd.DataFrame | None,
        qa_extras: Mapping[str, pd.DataFrame] | None = None,
    ) -> None:
        """ثبت Snapshot QA شامل خلاصه، جزئیات و خروجی‌های تکمیلی."""

        summary_json = _serialize_dataframe(qa_summary_df) if qa_summary_df is not None else None
        details_json = _serialize_dataframe(qa_details_df) if qa_details_df is not None else None
        extras_json = _serialize_dataframe_map(qa_extras)
        if summary_json is None and details_json is None and extras_json is None:
            logger.debug("Skipping QA snapshot insert; all payloads are empty")
            return
        try:
            with self._open_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO qa_snapshots (
                        run_id, qa_summary_json, qa_details_json, qa_extras_json
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (run_id, summary_json, details_json, extras_json),
                )
                conn.commit()
        except sqlite3.Error as exc:  # pragma: no cover - مسیر غیرمنتظره
            raise DatabaseOperationError("ثبت Snapshot QA با خطا مواجه شد.") from exc

    def fetch_qa_snapshot(
        self, run_id: int
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None, dict[str, pd.DataFrame]]:
        """بازیابی Snapshot QA برای یک اجرا."""

        with self._open_connection() as conn:
            cursor = conn.execute(
                """
                SELECT qa_summary_json, qa_details_json, qa_extras_json
                FROM qa_snapshots WHERE run_id = ?
                """,
                (run_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None, None, {}
        summary_df = _safe_deserialize_dataframe(
            row["qa_summary_json"], label="qa_summary_json"
        )
        details_df = _safe_deserialize_dataframe(
            row["qa_details_json"], label="qa_details_json"
        )
        extras = _safe_deserialize_dataframe_map(row["qa_extras_json"])
        return summary_df, details_df, extras

    # ------------------------------------------------------------------
    # Snapshot بایگانی خروجی Exporter
    # ------------------------------------------------------------------
    def insert_exporter_snapshot(
        self,
        *,
        exporter_name: str,
        exporter_version: str | None,
        run_uuid: str | None,
        run_id: int | None,
        rows_df: pd.DataFrame,
        metadata_json: str | None,
        row_hash: str,
        columns_json: str,
        rows_json: str | None,
        row_limit: int,
        is_truncated: bool,
    ) -> int:
        """درج Snapshot خروجی Exporter در جدول ``exporter_snapshots``."""

        if rows_df is None:
            raise ValueError("دیتافریم خروجی Exporter تهی است؛ ورودی معتبر بدهید.")
        try:
            with self._open_connection() as conn:
                LocalDatabase._ensure_exporter_archive_schema(conn)
                cursor = conn.execute(
                    """
                    INSERT INTO exporter_snapshots (
                        exporter_name, exporter_version, run_uuid, run_id,
                        created_at, row_count, row_hash, columns_json,
                        rows_json, metadata_json, row_limit, is_truncated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        exporter_name,
                        exporter_version,
                        run_uuid,
                        run_id,
                        _to_iso(datetime.utcnow()),
                        int(rows_df.shape[0]),
                        row_hash,
                        columns_json,
                        rows_json,
                        metadata_json,
                        int(row_limit),
                        1 if is_truncated else 0,
                    ),
                )
                conn.commit()
                return int(cursor.lastrowid)
        except sqlite3.Error as exc:  # pragma: no cover - مسیر غیرمنتظره
            raise DatabaseOperationError("ثبت Snapshot خروجی Exporter ناکام ماند.") from exc

    def list_exporter_snapshots(self) -> list[sqlite3.Row]:
        """لیست Snapshot های موجود به‌ترتیب جدیدترین زمان."""

        with self._open_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM exporter_snapshots
                ORDER BY datetime(created_at) DESC, id DESC
                """
            )
            return cursor.fetchall()

    def fetch_exporter_snapshot(self, snapshot_id: int) -> tuple[sqlite3.Row | None, pd.DataFrame | None]:
        """بازیابی Snapshot خروجی Exporter بر اساس شناسه."""

        with self._open_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM exporter_snapshots WHERE id = ?", (snapshot_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None, None
        rows_df = _deserialize_exporter_rows(row)
        return row, rows_df

    def get_database_health_summary(self) -> DatabaseHealthSummary:
        """تولید خلاصهٔ سلامت پایگاه‌داده برای نمایش در UI."""

        if not self.path.exists():
            return DatabaseHealthSummary(
                status=DatabaseHealthStatus.UNAVAILABLE,
                message="پایگاه‌داده: در دسترس نیست",
                counts={},
            )

        try:
            with self._open_connection() as conn:
                conn.row_factory = sqlite3.Row
                expected_tables: dict[str, str] = {
                    "دانش‌آموز": "students_cache",
                    "پشتیبان": "mentor_pool_cache",
                    "اجرا": "runs",
                }
                missing = [
                    label for label, table in expected_tables.items() if not _table_exists(conn, table)
                ]
                counts: dict[str, int] = {}
                degraded_tables: list[str] = []
                for label, table in expected_tables.items():
                    if not _table_exists(conn, table):
                        counts[label] = 0
                        continue
                    try:
                        cursor = conn.execute(f'SELECT COUNT(*) FROM "{table}"')
                        row = cursor.fetchone()
                        counts[label] = int(row[0]) if row is not None else 0
                    except sqlite3.Error:
                        degraded_tables.append(label)
                        counts[label] = 0
                last_updated = datetime.utcnow()
                if missing or degraded_tables:
                    return DatabaseHealthSummary(
                        status=DatabaseHealthStatus.DEGRADED,
                        message="پایگاه‌داده: نیاز به بررسی",
                        counts=counts,
                        last_updated=last_updated,
                    )

                return DatabaseHealthSummary(
                    status=DatabaseHealthStatus.OK,
                    message="پایگاه‌داده: آماده",
                    counts=counts,
                    last_updated=last_updated,
                )
        except sqlite3.Error:
            logger.exception("Failed to collect database health summary")
            return DatabaseHealthSummary(
                status=DatabaseHealthStatus.UNAVAILABLE,
                message="پایگاه‌داده: خطای اتصال",
                counts={},
            )

    def _collect_table_diagnostics(
        self, conn: sqlite3.Connection, table: str, required_columns: Sequence[str]
    ) -> TableSchemaDiagnostics:
        """جمع‌آوری اطلاعات ستون‌ها و شمارش ردیف برای یک جدول."""

        exists = _table_exists(conn, table)
        columns: list[str] = []
        missing: list[str] = []
        row_count: int | None = None

        if exists:
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = [str(row[1]) for row in cursor.fetchall()]
            missing = [col for col in required_columns if col not in columns]
            try:
                row_count = int(
                    conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                )
            except sqlite3.Error:
                row_count = None
        else:
            missing = list(required_columns)

        return TableSchemaDiagnostics(
            name=table,
            exists=exists,
            columns=columns,
            missing_required_columns=missing,
            row_count=row_count,
        )

    def _assert_required_schema(self, conn: sqlite3.Connection) -> None:
        """اطمینان از حضور جداول و ستون‌های کلیدی و تولید خطای خوانا در صورت فقدان."""

        diagnostics: dict[str, list[str]] = {}
        for name, required in self._required_tables.items():
            table_diag = self._collect_table_diagnostics(conn, name, required)
            if table_diag.missing_required_columns:
                diagnostics[name] = table_diag.missing_required_columns
        if diagnostics:
            missing_text = ", ".join(
                f"{table}: {', '.join(cols)}" for table, cols in diagnostics.items()
            )
            raise DatabaseSchemaMismatchError(
                path=str(self.path),
                reason=f"ستون‌های ضروری پیدا نشد: {missing_text}",
                hint="فایل پایگاه‌داده را حذف یا بازنشانی کنید تا با Schema جدید ساخته شود.",
                diagnostics=diagnostics,
            )

    def _ensure_schema(self, conn: sqlite3.Connection, *, allow_repair: bool = True) -> None:
        """ساخت جدول‌های runs/run_metrics/qa_summary و مراجع به‌صورت idempotent.

        پارامتر ``allow_repair`` مشخص می‌کند آیا در صورت نبود ستون‌های کلیدی،
        تلاش برای اصلاح خودکار (مثلاً افزودن ``student_id``) انجام شود یا خطای
        ناسازگاری صادر گردد. این گزینه در مهاجرت از نسخه‌های قدیمی غیرفعال
        می‌شود تا اپراتور پیام بازسازی را دریافت کند.
        """

        for name, required in self._required_tables.items():
            if _table_exists(conn, name):
                table_diag = self._collect_table_diagnostics(conn, name, required)
                if table_diag.missing_required_columns:
                    if allow_repair and self._repair_required_schema(
                        conn, name, table_diag.missing_required_columns
                    ):
                        table_diag = self._collect_table_diagnostics(conn, name, required)

                if table_diag.missing_required_columns:
                    missing_text = ", ".join(table_diag.missing_required_columns)
                    raise DatabaseSchemaMismatchError(
                        path=str(self.path),
                        reason=(
                            f"ساختار جدول {name} ناقص است؛ ستون‌های مفقود: {missing_text}"
                        ),
                        hint=(
                            "فایل را حذف یا بازسازی کنید تا Schema کامل ایجاد شود."
                        ),
                        diagnostics={name: table_diag.missing_required_columns},
                    )

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_uuid TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                ssot_version TEXT NOT NULL,
                entrypoint TEXT NOT NULL,
                cli_args TEXT,
                db_path TEXT,
                input_files_json TEXT,
                input_hashes_json TEXT,
                total_students INTEGER,
                total_allocated INTEGER,
                total_unallocated INTEGER,
                history_metrics_json TEXT,
                qa_summary_json TEXT,
                status TEXT NOT NULL,
                message TEXT
            );

            CREATE TABLE IF NOT EXISTS run_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                metric_key TEXT NOT NULL,
                metric_value REAL NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS qa_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                violation_code TEXT NOT NULL,
                severity TEXT NOT NULL,
                count INTEGER NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS trace_snapshots (
                run_id INTEGER PRIMARY KEY,
                trace_json TEXT NOT NULL,
                summary_json TEXT,
                history_info_json TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS qa_snapshots (
                run_id INTEGER PRIMARY KEY,
                qa_summary_json TEXT,
                qa_details_json TEXT,
                qa_extras_json TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exporter_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exporter_name TEXT NOT NULL,
                exporter_version TEXT,
                run_uuid TEXT,
                run_id INTEGER,
                created_at TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                row_hash TEXT NOT NULL,
                columns_json TEXT NOT NULL,
                rows_json TEXT,
                metadata_json TEXT,
                row_limit INTEGER NOT NULL DEFAULT -1,
                is_truncated INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS reference_meta (
                table_name TEXT PRIMARY KEY,
                refreshed_at TEXT NOT NULL,
                source TEXT,
                row_count INTEGER
            );

            CREATE TABLE IF NOT EXISTS schools (
                "کد مدرسه" INTEGER,
                "نام مدرسه" TEXT
            );

            CREATE TABLE IF NOT EXISTS school_crosswalk_groups (
                "کد مدرسه" INTEGER,
                "کد جایگزین" TEXT,
                title TEXT
            );

            CREATE TABLE IF NOT EXISTS school_crosswalk_synonyms (
                "کد مدرسه" INTEGER,
                "کد جایگزین" TEXT,
                alias TEXT
            );

            CREATE TABLE IF NOT EXISTS students_cache (
                student_id TEXT,
                "کد ملی" TEXT,
                "کدرشته" INTEGER,
                "گروه آزمایشی" TEXT,
                "جنسیت" INTEGER,
                "دانش آموز فارغ" INTEGER,
                "مرکز گلستان صدرا" INTEGER,
                "مالی حکمت بنیاد" INTEGER,
                "کد مدرسه" INTEGER,
                school_code_raw TEXT,
                school_code_norm INTEGER,
                school_status_resolved INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_students_cache_student_id
            ON students_cache(student_id);

            CREATE INDEX IF NOT EXISTS idx_students_cache_join_keys
            ON students_cache("کدرشته", "جنسیت", "دانش آموز فارغ", "مرکز گلستان صدرا", "مالی حکمت بنیاد", "کد مدرسه");

            CREATE TABLE IF NOT EXISTS mentor_pool_cache (
                mentor_id TEXT,
                "کد کارمندی پشتیبان" TEXT,
                "کدرشته" INTEGER,
                "گروه آزمایشی" TEXT,
                "جنسیت" INTEGER,
                "دانش آموز فارغ" INTEGER,
                "مرکز گلستان صدرا" INTEGER,
                "مالی حکمت بنیاد" INTEGER,
                "کد مدرسه" INTEGER,
                remaining_capacity REAL,
                allocations_new INTEGER,
                occupancy_ratio REAL
            );

            CREATE TABLE IF NOT EXISTS forms_entries (
                entry_id TEXT,
                form_id TEXT,
                received_at TEXT,
                normalized_at TEXT,
                PRIMARY KEY(entry_id)
            );

            CREATE INDEX IF NOT EXISTS idx_forms_entries_form_id
            ON forms_entries(form_id);

            CREATE INDEX IF NOT EXISTS idx_mentor_pool_cache_mentor_id
            ON mentor_pool_cache(mentor_id);

            CREATE INDEX IF NOT EXISTS idx_mentor_pool_cache_join_keys
            ON mentor_pool_cache("کدرشته", "جنسیت", "دانش آموز فارغ", "مرکز گلستان صدرا", "مالی حکمت بنیاد", "کد مدرسه");
            """
        )
        LocalDatabase._ensure_managers_reference_schema(conn)

    @staticmethod
    def _ensure_managers_reference_schema(conn: sqlite3.Connection) -> None:
        """ایجاد جدول و ایندکس‌های مرجع مدیران به‌شکل پایدار."""

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS managers_reference (
                "نام مدیر" TEXT,
                "مرکز گلستان صدرا" INTEGER
            );
            """
        )
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_managers_reference_manager ON managers_reference("نام مدیر")'
        )
        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_managers_reference_center_manager ON managers_reference("مرکز گلستان صدرا", "نام مدیر")'
        )

    @staticmethod
    def _ensure_exporter_archive_schema(conn: sqlite3.Connection) -> None:
        """ایجاد جدول بایگانی خروجی Exporter به‌شکل پایدار."""

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS exporter_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exporter_name TEXT NOT NULL,
                exporter_version TEXT,
                run_uuid TEXT,
                run_id INTEGER,
                created_at TEXT NOT NULL,
                row_count INTEGER NOT NULL,
                row_hash TEXT NOT NULL,
                columns_json TEXT NOT NULL,
                rows_json TEXT,
                metadata_json TEXT,
                row_limit INTEGER NOT NULL DEFAULT -1,
                is_truncated INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE SET NULL
            );
            """
        )
        _ensure_column_exists(
            conn,
            table="exporter_snapshots",
            column="row_limit",
            definition="INTEGER NOT NULL DEFAULT -1",
        )
        _ensure_column_exists(
            conn,
            table="exporter_snapshots",
            column="is_truncated",
            definition="INTEGER NOT NULL DEFAULT 0",
        )

    @staticmethod
    def _ensure_schema_meta_table(conn: sqlite3.Connection) -> None:
        """ایجاد جدول متادیتای نسخه در صورت نبود."""

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                schema_version INTEGER NOT NULL,
                policy_version TEXT NOT NULL,
                ssot_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    @staticmethod
    def _ensure_schema_meta_row(conn: sqlite3.Connection, *, version: int) -> None:
        """تضمین وجود رکورد نسخهٔ Schema با درج اولیه در صورت نبود."""

        conn.execute(
            """
            INSERT OR IGNORE INTO schema_meta (id, schema_version, policy_version, ssot_version, created_at)
            VALUES (1, ?, ?, ?, ?)
            """,
            (version, _POLICY_VERSION, _SSOT_VERSION, _to_iso(datetime.utcnow())),
        )

    @staticmethod
    def _get_schema_version(conn: sqlite3.Connection) -> int | None:
        cursor = conn.execute("SELECT schema_version FROM schema_meta WHERE id = 1")
        row = cursor.fetchone()
        return int(row[0]) if row is not None else None

    def _ensure_year_meta(self, conn: sqlite3.Connection) -> None:
        """ثبت متادیتای سال تحصیلی در صورت تعریف."""

        LocalDatabase._ensure_year_tables(conn)
        if self.academic_year is None:
            return
        conn.execute(
            """
            INSERT OR REPLACE INTO year_meta (id, academic_year, created_at)
            VALUES (1, ?, COALESCE((SELECT created_at FROM year_meta WHERE id = 1), ?))
            """,
            (self.academic_year, _to_iso(datetime.utcnow())),
        )

    def get_academic_year(self) -> str | None:
        """بازیابی شناسهٔ سال ذخیره‌شده در پایگاه داده."""

        with self._open_connection() as conn:
            cursor = conn.execute(
                "SELECT academic_year FROM year_meta WHERE id = 1"
            )
            row = cursor.fetchone()
            return str(row[0]) if row else None

    def record_roster_source(
        self, *, source_type: str, file_name: str | None, academic_year: str | None = None
    ) -> None:
        """ثبت متادیتای منبع اکسل برای سال جاری."""

        self.initialize()
        with self._open_connection() as conn:
            conn.execute(
                """
                INSERT INTO roster_sources (source_type, file_name, imported_at, academic_year)
                VALUES (?, ?, ?, ?)
                """,
                (
                    source_type,
                    file_name,
                    _to_iso(datetime.utcnow()),
                    academic_year or self.academic_year,
                ),
            )
            conn.commit()

    @staticmethod
    def _validate_schema_version(conn: sqlite3.Connection) -> None:
        """اعتبارسنجی تطابق نسخهٔ Schema پایگاه داده."""

        actual = LocalDatabase._get_schema_version(conn)
        if actual is None:
            raise SchemaVersionMismatchError(
                expected_version=_SCHEMA_VERSION,
                actual_version=-1,
                message="رکورد نسخهٔ Schema یافت نشد.",
            )
        if actual != _SCHEMA_VERSION:
            raise SchemaVersionMismatchError(
                expected_version=_SCHEMA_VERSION,
                actual_version=actual,
                message="نسخهٔ Schema پایگاه داده با نسخهٔ برنامه هم‌خوان نیست.",
            )

    def _migrate_schema(self, conn: sqlite3.Connection, *, from_version: int) -> None:
        """مهاجرت نسخهٔ Schema به نسخهٔ جاری."""

        version = from_version
        while version < _SCHEMA_VERSION:
            if version == 2:
                self._migrate_v2_to_v3(conn)
                version = 3
                continue
            if version == 3:
                self._migrate_v3_to_v4(conn)
                version = 4
                continue
            if version == 4:
                self._migrate_v4_to_v5(conn)
                version = 5
                continue
            if version == 5:
                self._migrate_v5_to_v6(conn)
                version = 6
                continue
            if version == 6:
                self._migrate_v6_to_v7(conn)
                version = 7
                continue
            if version == 7:
                self._migrate_v7_to_v8(conn)
                version = 8
                continue
            if version == 8:
                self._migrate_v8_to_v9(conn)
                version = 9
                continue
            if version == 9:
                self._migrate_v9_to_v10(conn)
                version = 10
                continue
            raise SchemaVersionMismatchError(
                expected_version=_SCHEMA_VERSION,
                actual_version=version,
                message="نسخهٔ Schema پشتیبانی نمی‌شود.",
            )

    def _migrate_v2_to_v3(self, conn: sqlite3.Connection) -> None:
        """افزودن جداول Snapshot برای نسخهٔ ۳."""

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trace_snapshots (
                run_id INTEGER PRIMARY KEY,
                trace_json TEXT NOT NULL,
                summary_json TEXT,
                history_info_json TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS qa_snapshots (
                run_id INTEGER PRIMARY KEY,
                qa_summary_json TEXT,
                qa_details_json TEXT,
                qa_extras_json TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            "UPDATE schema_meta SET schema_version = ? WHERE id = 1", (3,)
        )

    def _migrate_v3_to_v4(self, conn: sqlite3.Connection) -> None:
        """افزودن جدول متادیتای کش مراجع برای نسخهٔ ۴."""

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reference_meta (
                table_name TEXT PRIMARY KEY,
                refreshed_at TEXT NOT NULL,
                source TEXT,
                row_count INTEGER
            );
            """
        )
        conn.execute(
            "UPDATE schema_meta SET schema_version = ? WHERE id = 1", (4,)
        )

    def _migrate_v4_to_v5(self, conn: sqlite3.Connection) -> None:
        """افزودن جدول کش ورودی‌های فرم برای نسخهٔ ۵."""

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS forms_entries (
                entry_id TEXT,
                form_id TEXT,
                received_at TEXT,
                normalized_at TEXT,
                PRIMARY KEY(entry_id)
            );

            CREATE INDEX IF NOT EXISTS idx_forms_entries_form_id
            ON forms_entries(form_id);
            """
        )
        conn.execute(
            "UPDATE schema_meta SET schema_version = ? WHERE id = 1", (5,),
        )

    def _migrate_v5_to_v6(self, conn: sqlite3.Connection) -> None:
        """افزودن جدول مرجع مدیران برای نسخهٔ ۶."""

        LocalDatabase._ensure_managers_reference_schema(conn)
        conn.execute(
            "UPDATE schema_meta SET schema_version = ? WHERE id = 1", (6,),
        )

    def _migrate_v6_to_v7(self, conn: sqlite3.Connection) -> None:
        """افزودن جدول بایگانی خروجی Exporter برای نسخهٔ ۷."""

        LocalDatabase._ensure_exporter_archive_schema(conn)
        conn.execute(
            "UPDATE schema_meta SET schema_version = ? WHERE id = 1", (7,),
        )

    def _migrate_v7_to_v8(self, conn: sqlite3.Connection) -> None:
        """افزودن جدول سال و منابع roster برای نسخهٔ ۸."""

        LocalDatabase._ensure_year_tables(conn)
        conn.execute(
            "UPDATE schema_meta SET schema_version = ? WHERE id = 1", (8,),
        )

    def _migrate_v8_to_v9(self, conn: sqlite3.Connection) -> None:
        """افزودن ستون QA extras برای snapshotها در نسخهٔ ۹."""

        if _table_exists(conn, "qa_snapshots"):
            columns = _get_table_columns(conn, "qa_snapshots")
            if "qa_extras_json" not in columns:
                conn.execute(
                    "ALTER TABLE qa_snapshots ADD COLUMN qa_extras_json TEXT"
                )
        conn.execute(
            "UPDATE schema_meta SET schema_version = ? WHERE id = 1", (9,),
        )

    def _migrate_v9_to_v10(self, conn: sqlite3.Connection) -> None:
        """افزودن ستون ``student_id`` به جدول cache دانش‌آموزان در نسخهٔ ۱۰."""

        if _table_exists(conn, "students_cache"):
            columns = _get_table_columns(conn, "students_cache")
            if "student_id" not in columns:
                conn.execute("ALTER TABLE students_cache ADD COLUMN student_id TEXT")

        conn.execute(
            "UPDATE schema_meta SET schema_version = ? WHERE id = 1", (10,),
        )

    @staticmethod
    def _ensure_year_tables(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS year_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                academic_year TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS roster_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                file_name TEXT,
                imported_at TEXT NOT NULL,
                academic_year TEXT
            );
            """
        )

    # ------------------------------------------------------------------
    # جدول‌های مرجع مدارس / Crosswalk
    # ------------------------------------------------------------------
    def upsert_schools(self, df: pd.DataFrame) -> None:
        """افزودن/جایگزینی جدول مدارس از DataFrame.

        این تابع دیتافریم ورودی را بدون index در جدول ``schools`` ذخیره
        می‌کند و در صورت وجود ستون «کد مدرسه»، ایندکس یکتا می‌سازد تا
        جست‌وجوی مبتنی‌بر کلید اتصال سریع و پایدار بماند.
        """

        if df is None:
            raise ValueError("DataFrame مدارس تهی است؛ ورودی معتبر بدهید.")
        self.initialize()
        try:
            with self._open_connection() as conn:
                self._replace_table_atomic(
                    conn,
                    table_name="schools",
                    df=df,
                    index_statements=(
                        ['CREATE UNIQUE INDEX IF NOT EXISTS idx_schools_code ON schools("کد مدرسه")']
                        if "کد مدرسه" in df.columns
                        else []
                    ),
                )
                self.record_reference_meta(
                    table_name="schools",
                    source=None,
                    row_count=int(df.shape[0]),
                    conn=conn,
                )
        except sqlite3.Error as exc:
            raise DatabaseOperationError("ذخیرهٔ مدارس در SQLite ناکام ماند.") from exc

    def upsert_school_crosswalk(
        self, groups_df: pd.DataFrame, *, synonyms_df: pd.DataFrame | None = None
    ) -> None:
        """ذخیرهٔ Crosswalk مدارس (شیت گروه‌ها و Synonyms).

        - ``groups_df`` در جدول ``school_crosswalk_groups`` ذخیره می‌شود.
        - اگر ``synonyms_df`` موجود باشد، در ``school_crosswalk_synonyms``
          ذخیره می‌شود؛ در غیر این صورت جدول Synonyms حذف نمی‌شود تا دادهٔ
          قبلی باقی بماند.
        """

        if groups_df is None:
            raise ValueError("DataFrame گروه مدارس تهی است؛ ورودی معتبر بدهید.")
        self.initialize()
        try:
            with self._open_connection() as conn:
                self._replace_table_atomic(
                    conn,
                    table_name="school_crosswalk_groups",
                    df=groups_df,
                )
                if synonyms_df is not None:
                    self._replace_table_atomic(
                        conn,
                        table_name="school_crosswalk_synonyms",
                        df=synonyms_df,
                    )
        except sqlite3.Error as exc:
            raise DatabaseOperationError("ذخیرهٔ Crosswalk مدارس ناکام ماند.") from exc

    def load_schools(self) -> pd.DataFrame:
        """بارگذاری جدول مدارس از SQLite با حفظ نوع عددی کلید اتصال."""

        try:
            with self._open_connection() as conn:
                if not _table_exists(conn, "schools"):
                    raise ReferenceDataMissingError(
                        table="schools",
                        message="جدول مدارس در پایگاه داده یافت نشد؛ ابتدا import-schools را اجرا کنید.",
                    )
                df = pd.read_sql_query("SELECT * FROM schools", conn)
            return _coerce_int_columns(df, ["کد مدرسه"])
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                raise ReferenceDataMissingError(
                    table="schools",
                    message="جدول مدارس در پایگاه داده یافت نشد؛ ابتدا import-schools را اجرا کنید.",
                ) from exc
            raise DatabaseOperationError("خواندن جدول مدارس با خطا مواجه شد.") from exc
        except sqlite3.Error as exc:
            raise DatabaseOperationError("خواندن جدول مدارس با خطا مواجه شد.") from exc

    def load_school_crosswalk(self) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        """بارگذاری Crosswalk مدارس از SQLite."""

        try:
            with self._open_connection() as conn:
                if not _table_exists(conn, "school_crosswalk_groups"):
                    raise ReferenceDataMissingError(
                        table="school_crosswalk_groups",
                        message="جدول Crosswalk مدارس یافت نشد؛ ابتدا import-crosswalk را اجرا کنید.",
                    )
                groups_df = pd.read_sql_query("SELECT * FROM school_crosswalk_groups", conn)
                synonyms_df = None
                if _table_exists(conn, "school_crosswalk_synonyms"):
                    synonyms_df = pd.read_sql_query(
                        "SELECT * FROM school_crosswalk_synonyms", conn
                    )
            return _coerce_int_columns(groups_df, ["کد مدرسه", "کد جایگزین"]), synonyms_df
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                raise ReferenceDataMissingError(
                    table="school_crosswalk_groups",
                    message="جدول Crosswalk مدارس یافت نشد؛ ابتدا import-crosswalk را اجرا کنید.",
                ) from exc
            raise DatabaseOperationError("خواندن Crosswalk مدارس با خطا مواجه شد.") from exc

    # ------------------------------------------------------------------
    # کش گزارش دانش‌آموز و استخر منتورها
    # ------------------------------------------------------------------
    def upsert_students_cache(
        self, df: pd.DataFrame, *, join_keys: Sequence[str]
    ) -> None:
        """جایگزینی دیتافریم دانش‌آموزان در جدول ``students_cache``.

        دیتافریم ورودی باید پیش‌تر بر اساس Policy نرمال شده باشد؛ این تابع تنها
        ذخیره‌سازی اتمیک و ساخت ایندکس روی شناسه و کلیدهای اتصال را بر عهده دارد.
        """

        if df is None:
            raise ValueError("DataFrame دانش‌آموزان تهی است؛ ورودی معتبر بدهید.")
        self.initialize()
        _validate_join_keys(df, join_keys)
        index_statements = _build_index_statements(
            table_name="students_cache",
            df=df,
            unique_candidates=("student_id",),
            join_keys=join_keys,
        )
        try:
            with self._open_connection() as conn:
                self._replace_table_atomic(
                    conn,
                    table_name="students_cache",
                    df=df,
                    index_statements=index_statements,
                )
        except sqlite3.Error as exc:
            raise DatabaseOperationError(
                "ذخیرهٔ کش دانش‌آموزان در SQLite ناکام ماند."
            ) from exc

    def load_students_cache(self, *, join_keys: Sequence[str]) -> pd.DataFrame:
        """خواندن دیتافریم دانش‌آموزان از کش SQLite با حفظ نوع کلیدها."""

        try:
            with self._open_connection() as conn:
                if not _table_exists(conn, "students_cache"):
                    raise ReferenceDataMissingError(
                        table="students_cache",
                        message="کش دانش‌آموز یافت نشد؛ ابتدا import-students را اجرا کنید.",
                    )
                df = pd.read_sql_query("SELECT * FROM students_cache", conn)
                if df.empty:
                    raise ReferenceDataMissingError(
                        table="students_cache",
                        message="کش دانش‌آموز خالی است؛ ابتدا import-students را اجرا کنید.",
                    )
            return _coerce_int_columns(df, join_keys)
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                raise ReferenceDataMissingError(
                    table="students_cache",
                    message="کش دانش‌آموز یافت نشد؛ ابتدا import-students را اجرا کنید.",
                ) from exc
            raise DatabaseOperationError("خواندن کش دانش‌آموزان با خطا مواجه شد.") from exc
        except sqlite3.Error as exc:
            raise DatabaseOperationError("خواندن کش دانش‌آموزان با خطا مواجه شد.") from exc

    def upsert_mentor_pool_cache(
        self, df: pd.DataFrame, *, join_keys: Sequence[str]
    ) -> None:
        """جایگزینی دیتافریم استخر منتورها در جدول ``mentor_pool_cache``."""

        if df is None:
            raise ValueError("DataFrame استخر منتورها تهی است؛ ورودی معتبر بدهید.")
        self.initialize()
        _validate_join_keys(df, join_keys)
        index_statements = _build_index_statements(
            table_name="mentor_pool_cache",
            df=df,
            unique_candidates=("mentor_id", "کد کارمندی پشتیبان"),
            join_keys=join_keys,
        )
        try:
            with self._open_connection() as conn:
                self._replace_table_atomic(
                    conn,
                    table_name="mentor_pool_cache",
                    df=df,
                    index_statements=index_statements,
                )
        except sqlite3.Error as exc:
            raise DatabaseOperationError(
                "ذخیرهٔ کش استخر منتورها در SQLite ناکام ماند."
            ) from exc

    def load_mentor_pool_cache(self, *, join_keys: Sequence[str]) -> pd.DataFrame:
        """خواندن دیتافریم استخر منتورها از کش SQLite با حفظ نوع کلیدها."""

        try:
            with self._open_connection() as conn:
                if not _table_exists(conn, "mentor_pool_cache"):
                    raise ReferenceDataMissingError(
                        table="mentor_pool_cache",
                        message="کش استخر منتورها یافت نشد؛ ابتدا import-mentors را اجرا کنید.",
                    )
                df = pd.read_sql_query("SELECT * FROM mentor_pool_cache", conn)
                if df.empty:
                    raise ReferenceDataMissingError(
                        table="mentor_pool_cache",
                        message="کش استخر منتورها خالی است؛ ابتدا import-mentors را اجرا کنید.",
                    )
            return _coerce_int_columns(df, join_keys)
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                raise ReferenceDataMissingError(
                    table="mentor_pool_cache",
                    message="کش استخر منتورها یافت نشد؛ ابتدا import-mentors را اجرا کنید.",
                ) from exc
            raise DatabaseOperationError("خواندن کش استخر منتورها با خطا مواجه شد.") from exc
        except sqlite3.Error as exc:
            raise DatabaseOperationError("خواندن کش استخر منتورها با خطا مواجه شد.") from exc

    # ------------------------------------------------------------------
    # ورودی‌های فرم وردپرس / Gravity Forms
    # ------------------------------------------------------------------
    def upsert_forms_entries(
        self,
        df: pd.DataFrame,
        *,
        source: str | None = None,
    ) -> None:
        """ذخیرهٔ دیتافریم نرمال‌شدهٔ ورودی‌های فرم در جدول ``forms_entries``.

        ورودی باید شامل ستون ``entry_id`` باشد. ستون‌های زمان (received_at و
        normalized_at) به‌صورت ISO8601 ذخیره می‌شوند تا بازسازی دترمینیستیک
        آسان شود.
        """

        if df is None:
            raise ValueError("DataFrame ورودی‌های فرم تهی است؛ ورودی معتبر بدهید.")
        if "entry_id" not in df.columns:
            raise ValueError("ستون entry_id برای ذخیرهٔ کش فرم ضروری است.")

        normalized = _normalize_forms_timestamps(df)
        normalized = normalized.dropna(subset=["entry_id"])\
            .drop_duplicates(subset=["entry_id"], keep="last")\
            .sort_values(by=["received_at", "entry_id"], kind="stable")\
            .reset_index(drop=True)

        self.initialize()
        index_statements = _build_index_statements(
            table_name="forms_entries",
            df=normalized,
            unique_candidates=("entry_id",),
            join_keys=(),
        )
        try:
            with self._open_connection() as conn:
                self._replace_table_atomic(
                    conn,
                    table_name="forms_entries",
                    df=normalized,
                    index_statements=index_statements,
                )
                self.record_reference_meta(
                    table_name="forms_entries",
                    source=source,
                    row_count=int(normalized.shape[0]),
                    conn=conn,
                )
        except sqlite3.Error as exc:  # pragma: no cover - مسیر غیرمنتظره
            raise DatabaseOperationError("ثبت کش ورودی‌های فرم با خطا مواجه شد.") from exc

    def load_forms_entries(self) -> pd.DataFrame:
        """بازیابی کش ورودی‌های فرم به‌صورت DataFrame."""

        with self._open_connection() as conn:
            if not _table_exists(conn, "forms_entries"):
                raise ReferenceDataMissingError(
                    table="forms_entries",
                    message="جدول forms_entries در پایگاه داده یافت نشد؛ ابتدا sync-forms را اجرا کنید.",
                )
            df = pd.read_sql_query(
                "SELECT * FROM forms_entries ORDER BY received_at ASC, entry_id ASC", conn
            )
        if df.empty:
            return df
        restored = _restore_timestamp_columns(
            df, columns=("received_at", "normalized_at")
        )
        return restored

    def record_reference_meta(
        self,
        *,
        table_name: str,
        source: str | None,
        row_count: int | None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        """ثبت زمان به‌روزرسانی کش مرجع برای مصرف مخازن اشتراکی."""

        needs_close = False
        target_conn = conn
        if target_conn is None:
            target_conn = self._open_connection()
            needs_close = True
        try:
            target_conn.execute(
                """
                INSERT OR REPLACE INTO reference_meta(table_name, refreshed_at, source, row_count)
                VALUES (?, ?, ?, ?)
                """,
                (table_name, _to_iso(datetime.utcnow()), source, row_count),
            )
            target_conn.commit()
        finally:
            if needs_close:
                target_conn.close()

    def fetch_reference_meta(self, table_name: str) -> tuple[str, str | None, int | None] | None:
        """بازیابی متادیتای کش مرجع (زمان، منبع، شمارش ردیف)."""

        with self._open_connection() as conn:
            cursor = conn.execute(
                "SELECT refreshed_at, source, row_count FROM reference_meta WHERE table_name = ?",
                (table_name,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return row[0], row[1], row[2]

    def list_tables_with_counts(self) -> pd.DataFrame:
        """فهرست جدول‌های SQLite همراه شمارش ردیف."""

        self.initialize()
        with self._open_connection() as conn:
            cursor = conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
            tables = [row[0] for row in cursor.fetchall()]
            rows: list[dict[str, object]] = []
            for table in tables:
                quoted_table = _quote_identifier(table)
                count = conn.execute(f"SELECT COUNT(1) FROM {quoted_table}").fetchone()[0]
                rows.append({"table": table, "row_count": int(count)})
        return pd.DataFrame(rows)

    def preview_table(self, table_name: str, *, limit: int = 100) -> pd.DataFrame:
        """بازگرداندن نمونه‌ای محدود از جدول برای نمایش."""

        self.initialize()
        with self._open_connection() as conn:
            if not _table_exists(conn, table_name):
                raise DatabaseOperationError("جدول در پایگاه‌داده یافت نشد.")
            try:
                quoted_table = _quote_identifier(table_name)
                df = pd.read_sql_query(
                    f"SELECT * FROM {quoted_table} LIMIT ?", conn, params=[int(limit)]
                )
            except Exception as exc:  # pragma: no cover - خطاهای نادر
                raise DatabaseOperationError("خواندن جدول برای پیش‌نمایش ناکام ماند.") from exc
        return _sqlite_coerce_int_like(df)

    @staticmethod
    def _replace_table_atomic(
        conn: sqlite3.Connection,
        *,
        table_name: str,
        df: pd.DataFrame,
        index_statements: Sequence[str] | None = None,
    ) -> None:
        """جایگزینی اتمیک یک جدول با الگوی temp→swap در یک تراکنش."""

        temp_table = f"_{table_name}_new"
        backup_table = f"_{table_name}_backup"
        try:
            conn.execute(f"DROP TABLE IF EXISTS {temp_table}")
            conn.execute(f"DROP TABLE IF EXISTS {backup_table}")
            df.to_sql(temp_table, conn, if_exists="replace", index=False)

            conn.execute("BEGIN IMMEDIATE")
            if _table_exists(conn, table_name):
                conn.execute(f"ALTER TABLE {table_name} RENAME TO {backup_table}")
            conn.execute(f"ALTER TABLE {temp_table} RENAME TO {table_name}")
            for stmt in index_statements or []:
                conn.execute(stmt)
            conn.execute(f"DROP TABLE IF EXISTS {backup_table}")
            conn.commit()
        except sqlite3.Error as exc:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            try:
                conn.execute(f"DROP TABLE IF EXISTS {temp_table}")
                conn.execute(f"DROP TABLE IF EXISTS {backup_table}")
            except sqlite3.Error:
                pass
            raise DatabaseOperationError("جایگزینی جدول به‌صورت اتمیک با خطا مواجه شد.") from exc


def _to_iso(dt: datetime) -> str:
    """تبدیل datetime به رشتهٔ ISO8601 با پسوند Z."""

    return dt.strftime(_ISO_FORMAT)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """بررسی وجود جدول به‌صورت امن و دترمینیستیک."""

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """استخراج نام ستون‌های جدول داده‌شده.

    - اگر جدول وجود نداشته باشد، مجموعهٔ خالی برگردانده می‌شود.
    - مثال: ``_get_table_columns(conn, "students_cache")`` → ``{"student_id", "کدرشته"}``
    """

    if not table_name:
        return set()
    cursor = conn.execute(f"PRAGMA table_info({_quote_identifier(table_name)})")
    return {str(row[1]) for row in cursor.fetchall()}


def _quote_identifier(name: str) -> str:
    """Quote an identifier safely for use in SQLite statements."""

    if not name:
        raise ValueError("Identifier cannot be empty.")
    escaped = name.replace("\"", "\"\"")
    return f'"{escaped}"'


def _coerce_int_columns(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """تبدیل ستون‌های اعلام‌شده به نوع Int64 بدون تغییر سایر ستون‌ها."""

    return _sqlite_coerce_int_columns(df, list(columns))


def _normalize_timestamp_columns(
    df: pd.DataFrame, *, columns: Iterable[str]
) -> pd.DataFrame:
    """تبدیل ستون‌های زمانی به datetime و ذخیره به‌صورت ISO8601."""

    normalized = df.copy()
    for col in columns:
        if col in normalized.columns:
            series = pd.to_datetime(normalized[col], errors="coerce", utc=True)
            normalized[col] = series.dt.strftime(_ISO_FORMAT)
    return normalized


def _restore_timestamp_columns(
    df: pd.DataFrame, *, columns: Iterable[str]
) -> pd.DataFrame:
    """بازگردانی ستون‌های زمانی به نوع datetime با timezone آگاه."""

    restored = df.copy()
    for col in columns:
        if col in restored.columns:
            restored[col] = pd.to_datetime(restored[col], errors="coerce", utc=True)
    return restored


def _normalize_forms_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """نرمال‌سازی ستون‌های زمانی forms_entries به یک گذر ثابت.

    دریافت دیتافریم شامل ``received_at`` و ``normalized_at`` (در صورت عدم وجود
    normalized_at در ورودی، مقدار UTC فعلی اضافه می‌شود)، تبدیل همهٔ مقادیر به
    datetime آگاه از timezone، و سپس سریال‌سازی ISO8601 با پسوند ``Z``.
    """

    normalized = df.copy()
    if "normalized_at" not in normalized.columns:
        normalized["normalized_at"] = datetime.utcnow()
    for col in ("received_at", "normalized_at"):
        if col in normalized.columns:
            normalized[col] = (
                pd.to_datetime(normalized[col], errors="coerce", utc=True)
                .dt.strftime(_ISO_FORMAT)
            )
    return normalized


def _serialize_dataframe(df: pd.DataFrame | None) -> str | None:
    """سریال‌سازی دترمینیستیک دیتافریم به JSON orient=split."""

    if df is None:
        return None
    normalized = df.copy()
    return normalized.to_json(
        orient="split", force_ascii=False, date_format="iso", double_precision=15
    )


def _serialize_dataframe_map(
    frames: Mapping[str, pd.DataFrame] | None,
) -> str | None:
    """سریال‌سازی نگاشت دیتافریم‌ها به JSON برای ذخیره در SQLite."""

    if not frames:
        return None
    payload: dict[str, str] = {}
    for key, df in frames.items():
        if not isinstance(df, pd.DataFrame):
            continue
        serialized = _serialize_dataframe(df)
        if serialized is None:
            continue
        payload[str(key)] = serialized
    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False)


def _safe_deserialize_dataframe(payload: str | bytes | None, *, label: str) -> pd.DataFrame | None:
    """بازسازی امن دیتافریم از JSON ذخیره‌شده به‌صورت split."""

    if payload in (None, b"", ""):
        return None
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return pd.read_json(io.StringIO(payload), orient="split")
    except Exception:
        logger.exception("Failed to deserialize DataFrame payload for %s", label)
        return None


def _safe_deserialize_dataframe_map(
    payload: str | bytes | None,
) -> dict[str, pd.DataFrame]:
    """بازسازی نگاشت دیتافریم‌ها از JSON ذخیره‌شده."""

    if payload in (None, b"", ""):
        return {}
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        raw = json.loads(payload)
        result: dict[str, pd.DataFrame] = {}
        for key, df_payload in raw.items():
            frame = _safe_deserialize_dataframe(df_payload, label=f"qa_extras.{key}")
            if isinstance(frame, pd.DataFrame):
                result[str(key)] = frame
        return result
    except Exception:
        logger.exception("Failed to deserialize QA extras payload")
        return {}


def _deserialize_exporter_rows(row: sqlite3.Row) -> pd.DataFrame | None:
    """بازسازی Snapshot خروجی Exporter بر اساس payload ذخیره‌شده."""

    payload = row["rows_json"]
    if payload in (None, b"", ""):
        return None
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        parsed = json.loads(payload)
        columns = parsed.get("columns") or json.loads(row["columns_json"])
        rows = parsed.get("rows") or []
        return pd.DataFrame(rows, columns=columns)
    except Exception:
        logger.exception("Failed to deserialize exporter snapshot rows")
        return None


def _coerce_int_like(value: object) -> int | None:
    """تبدیل مقدار به int در صورت امکان؛ در غیر این صورت None."""

    return _sqlite_coerce_int_like(value)


def _normalize_index_name(name: str) -> str:
    safe = name.replace(" ", "_")
    return "".join(ch for ch in safe if ch.isalnum() or ch == "_")


def _ensure_column_exists(
    conn: sqlite3.Connection, *, table: str, column: str, definition: str
) -> None:
    """افزودن ستون جدید به‌صورت idempotent در صورت نبود."""

    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing_columns = {row[1] for row in cursor.fetchall()}
    if column in existing_columns:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _build_index_statements(
    *,
    table_name: str,
    df: pd.DataFrame,
    unique_candidates: Sequence[str] = (),
    join_keys: Sequence[str] = (),
) -> list[str]:
    """تولید ایندکس‌های پایدار برای کلیدهای طبیعی و ۶ کلید اتصال Policy.

    این تابع در تمام کش‌های مرجع استفاده می‌شود تا یکتا بودن شناسه‌های
    طبیعی (student_id, mentor_id, کد مدرسه) و ایندکس‌گذاری join_keys بر اساس
    Policy/SSoT در یک مکان متمرکز باشد.
    """

    statements: list[str] = []
    seen: set[str] = set()
    for column in unique_candidates:
        if column in df.columns:
            idx = _normalize_index_name(f"idx_{table_name}_{column}_uniq")
            if idx not in seen:
                statements.append(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS {idx} ON {table_name}("{column}")'
                )
                seen.add(idx)
    for column in join_keys:
        if column in df.columns:
            idx = _normalize_index_name(f"idx_{table_name}_{column}")
            if idx not in seen:
                statements.append(
                    f'CREATE INDEX IF NOT EXISTS {idx} ON {table_name}("{column}")'
                )
                seen.add(idx)
    if table_name == "managers_reference":
        manager_col = "نام مدیر"
        center_col = "مرکز گلستان صدرا"
        if manager_col in df.columns:
            idx_manager = _normalize_index_name("idx_managers_reference_manager")
            if idx_manager not in seen:
                statements.append(
                    f'CREATE INDEX IF NOT EXISTS {idx_manager} ON {table_name}("{manager_col}")'
                )
                seen.add(idx_manager)
        if manager_col in df.columns and center_col in df.columns:
            idx_composite = _normalize_index_name(
                "idx_managers_reference_center_manager"
            )
            if idx_composite not in seen:
                statements.append(
                    f'CREATE UNIQUE INDEX IF NOT EXISTS {idx_composite} ON {table_name}("{center_col}", "{manager_col}")'
                )
                seen.add(idx_composite)
    return statements


def _validate_join_keys(df: pd.DataFrame, join_keys: Sequence[str]) -> None:
    """تضمین می‌کند کلیدهای اتصال پیش از ذخیره از نوع عددی باشند."""

    missing = [col for col in join_keys if col not in df.columns]
    if missing:
        raise ValueError(f"ستون‌های کلید اتصال وجود ندارند: {missing}")
    for col in join_keys:
        series = df[col]
        if not is_integer_dtype(series):
            try:
                df[col] = series.astype("Int64")
            except Exception as exc:  # pragma: no cover - مسیر خطا
                raise ValueError(f"ستون {col} باید عددی باشد.") from exc
