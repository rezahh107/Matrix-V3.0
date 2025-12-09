from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.policy_loader import PolicyConfig
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository
from app.infra.students.pipeline_v3 import StudentPipelineResult, StudentPipelineV3

__all__ = [
    "run_student_pipeline_from_excel",
    "run_student_pipeline_from_dataframe",
]


def run_student_pipeline_from_excel(
    path: Path,
    *,
    policy: PolicyConfig,
    reference_mode: str = "db",
    db: LocalDatabase | None = None,
    school_repo: SchoolRepository | None = None,
    groupcode_repo: GroupCodeRepository | None = None,
) -> StudentPipelineResult:
    mode = "db" if reference_mode == "db" else "excel"
    pipeline = StudentPipelineV3(
        policy=policy,
        reference_mode=mode,
        db=db,
        school_repo=school_repo,
        groupcode_repo=groupcode_repo,
    )
    return pipeline.run_from_excel(path)


def run_student_pipeline_from_dataframe(
    df: pd.DataFrame,
    *,
    policy: PolicyConfig,
    reference_mode: str = "db",
    db: LocalDatabase | None = None,
    school_repo: SchoolRepository | None = None,
    groupcode_repo: GroupCodeRepository | None = None,
) -> StudentPipelineResult:
    mode = "db" if reference_mode == "db" else "excel"
    pipeline = StudentPipelineV3(
        policy=policy,
        reference_mode=mode,
        db=db,
        school_repo=school_repo,
        groupcode_repo=groupcode_repo,
    )
    return pipeline.run(df)
