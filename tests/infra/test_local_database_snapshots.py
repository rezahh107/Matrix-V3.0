from __future__ import annotations

from pathlib import Path

import pytest

from app.infra.local_database import LocalDatabase

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "db_snapshots"


def test_local_database_initializes_on_snapshots() -> None:
    if not SNAPSHOT_DIR.exists():
        pytest.skip("tests/data/db_snapshots is missing; add .sqlite snapshots to run this test.")

    snapshots = sorted(SNAPSHOT_DIR.glob("*.sqlite"))
    if not snapshots:
        pytest.skip("No .sqlite snapshots found in tests/data/db_snapshots.")

    for snapshot_path in snapshots:
        db = LocalDatabase(snapshot_path)
        db.initialize()
