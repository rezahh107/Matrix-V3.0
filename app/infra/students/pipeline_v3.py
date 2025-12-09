from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from app.core.canonical_frames import canonicalize_students_frame
from app.core.common.columns import canonicalize_headers
from app.core.common.join_keys import validate_and_canonicalize_join_keys
from app.core.common.types import (
    HeaderMode,
    StudentDomainValidationResult,
    StudentValidationBundle,
)
from app.core.policy_loader import PolicyConfig
from app.core.students.domain_validation import validate_student_domain
from app.infra.errors import DatabasePreparationError
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.io_utils import read_excel_first_sheet
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository

__all__ = ["StudentPipelineResult", "StudentPipelineV3"]


@dataclass(frozen=True)
class StudentPipelineResult:
    """Aggregate result for student import pipeline."""

    validation: StudentValidationBundle

    @property
    def canonical_df(self) -> pd.DataFrame:
        return self.validation.canonical_df

    @property
    def domain_result(self) -> StudentDomainValidationResult:
        return self.validation.domain

    @property
    def can_continue(self) -> bool:
        if self.validation.join_keys.issues:
            return False
        return self.validation.domain.can_continue


class StudentPipelineV3:
    """Student import pipeline with optional DB-backed reference mode."""

    def __init__(
        self,
        *,
        policy: PolicyConfig,
        header_mode: HeaderMode = "fa",
        reference_mode: Literal["excel", "db"] = "db",
        db: LocalDatabase | None = None,
        school_repo: SchoolRepository | None = None,
        groupcode_repo: GroupCodeRepository | None = None,
    ) -> None:
        self._policy = policy
        self._header_mode = header_mode
        self._reference_mode = reference_mode
        self._school_repo = school_repo
        self._groupcode_repo = groupcode_repo
        self._db = db or (school_repo.database if school_repo is not None else None)

    def run_from_excel(self, path: Path) -> StudentPipelineResult:
        raw_df = read_excel_first_sheet(path)
        return self.run(raw_df)

    def run(self, df: pd.DataFrame) -> StudentPipelineResult:
        crosswalk = self._enforce_db_reference_mode()
        canonical_headers = canonicalize_headers(df, header_mode=self._header_mode)
        join_key_result = validate_and_canonicalize_join_keys(
            canonical_headers, policy=self._policy, entity_type="student"
        )
        students = canonicalize_students_frame(
            join_key_result.canonical_df,
            policy=self._policy,
            group_code_crosswalk=crosswalk,
        )
        domain_result = validate_student_domain(students, policy=self._policy)
        bundle = StudentValidationBundle(join_keys=join_key_result, domain=domain_result)
        return StudentPipelineResult(validation=bundle)

    def _enforce_db_reference_mode(self) -> dict[str | int, int] | None:
        if self._reference_mode != "db":
            return None
        if self._school_repo is None or self._groupcode_repo is None:
            raise DatabasePreparationError(
                path="local_db",
                reason="مراجع مدارس/کدگروه برای حالت DB تنظیم نشده است.",
                hint="ابتدا داده‌های مدارس و کدگروه را بارگذاری کنید.",
            )
        if self._school_repo.database is not self._groupcode_repo.database:
            raise DatabasePreparationError(
                path="local_db",
                reason="مراجع مدارس و کدگروه از پایگاه‌های متفاوت هستند.",
                hint="هر دو مخزن باید به یک پایگاه داده متصل باشند.",
            )
        try:
            school_status = self._school_repo.status()
            groupcode_status = self._groupcode_repo.status()
        except Exception as exc:  # pragma: no cover - defensive conversion
            raise DatabasePreparationError(
                path="local_db",
                reason="خواندن وضعیت داده مرجع ممکن نیست.",
                hint=str(exc),
            ) from exc
        if school_status.row_count <= 0 or groupcode_status.row_count <= 0:
            raise DatabasePreparationError(
                path="local_db",
                reason="جدول مدارس یا کدگروه خالی است.",
                hint="داده‌های مرجع را از فایل‌های Excel وارد کنید.",
            )
        crosswalk_frame = self._groupcode_repo.load_canonical_frame()
        if "group_code" not in crosswalk_frame.columns:
            return {}
        mapping: dict[str | int, int] = {}
        for group_code in crosswalk_frame["group_code"].dropna().astype(int):
            mapping[int(group_code)] = int(group_code)
        return mapping
