from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.students.pipeline_v3 import StudentPipelineV3


def test_finance_alias_status_maps_to_canonical_column(tmp_path: Path) -> None:
    policy = load_policy()
    pipeline = StudentPipelineV3(policy=policy, reference_mode="excel")

    df = pd.DataFrame(
        [
            {
                "گروه آزمایشی نهایی": 1,
                "gender": 1,
                "وضعیت تحصیلی": 0,
                "مرکز ثبت نام": 101,
                "وضعیت ثبت نام": 2,
                "مدرسه نهایی": 1001,
            }
        ]
    )
    path = tmp_path / "students_alias.xlsx"
    df.to_excel(path, index=False)

    result = pipeline.run(df)

    canonical = result.canonical_df
    assert "مالی حکمت بنیاد" in canonical.columns
    assert canonical.loc[0, "مالی حکمت بنیاد"] == 2
