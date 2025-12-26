from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.students.pipeline_v3 import StudentPipelineV3


def test_student_alias_headers_resolved(tmp_path: Path) -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "گروه آزمایشی نهایی": "1",
                "gender": "1",
                "وضعیت تحصیلی": "0",
                "مرکز ثبت نام": "101",
                "وضعیت ثبت نام": "0",
                "مدرسه نهایی": "1001",
            }
        ]
    )
    path = tmp_path / "students_alias.xlsx"
    df.to_excel(path, index=False)

    pipeline = StudentPipelineV3(policy=policy, reference_mode="excel")
    result = pipeline.run(df)

    assert not result.validation.join_keys.issues
    assert set(policy.join_keys).issubset(set(result.canonical_df.columns))
