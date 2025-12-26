from pathlib import Path

import pandas as pd
import pytest

from app.infra.errors import DatabasePreparationError
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase


def test_header_guard_blocks_missing_groupcode_columns(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    repo = GroupCodeRepository(db)
    df = pd.DataFrame(
        [
            {
                "group_code": 101,
                "level": "متوسطه دوم",
                "track": "ریاضی",
            }
        ]
    )
    path = tmp_path / "groupcodes.xlsx"
    df.to_excel(path, index=False)

    with pytest.raises(DatabasePreparationError) as excinfo:
        repo.import_from_excel(path)

    assert "grade" in (excinfo.value.hint or "")
