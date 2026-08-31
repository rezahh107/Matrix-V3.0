"""Shared fixtures for integration tests.

This module centralizes expensive canonical allocation runs so downstream tests
can reuse the generated artifacts without re-running the CLI multiple times.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def canonical_allocation_outputs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Run the allocation CLI on canonical inputs and return output paths.

    The fixture executes the real CLI with the repository-root ``students.xlsx``
    and ``0918.xlsx`` (sheet ``matrix``) to mirror production usage. The
    resulting allocation workbook and QA validation workbook paths are returned
    for reuse across multiple tests.
    """

    tmp_dir = tmp_path_factory.mktemp("canonical_allocation")
    output_path = tmp_dir / "output.xlsx"
    validation_path = tmp_dir / "output_validation.xlsx"

    db = LocalDatabase(tmp_dir / "canonical-references.sqlite")
    db.initialize()
    schools_path = tmp_dir / "canonical-schools.xlsx"
    pd.DataFrame(
        {
            "کد مدرسه": [1],
            "نام مدرسه": ["Synthetic Canonical School"],
            "مرکز گلستان صدرا": [0],
            "جنسیت": [1],
            "فعال": [1],
        }
    ).to_excel(schools_path, index=False)
    school_repo = SchoolRepository(db)
    school_repo.import_from_excel(schools_path)
    assert school_repo.status().row_count > 0
    assert GroupCodeRepository(db).status().row_count > 0

    cmd = [
        sys.executable,
        "-m",
        "app.infra.cli_legacy",
        "allocate",
        "--students",
        str(ROOT / "students.xlsx"),
        "--pool",
        str(ROOT / "0918.xlsx"),
        "--pool-type",
        "matrix",
        "--pool-sheet",
        "matrix",
        "--policy",
        "config/policy.json",
        "--academic-year",
        "1404",
        "--counter-duplicate-strategy",
        "assign-new",
        "--local-db",
        str(db.path),
        "--output",
        str(output_path),
    ]

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=ROOT,
    )
    if result.returncode != 0:
        raise AssertionError(
            "Canonical allocation run failed",
            result.returncode,
            result.stdout,
            result.stderr,
        )

    validation_path = output_path.with_name(f"{output_path.stem}_validation.xlsx")
    if not validation_path.exists():
        raise AssertionError(f"Expected validation workbook missing: {validation_path}")

    return output_path, validation_path
