from pathlib import Path

import pandas as pd
import pytest

from app.infra import cli


def test_allocate_parser_defaults_to_matrix(tmp_path: Path) -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["allocate", "--output", str(tmp_path / "out.xlsx")])

    assert args.pool_type == "matrix"
    assert args.pool_sheet is None


def test_import_mentors_parser_accepts_matrix(tmp_path: Path) -> None:
    parser = cli._build_parser()
    args = parser.parse_args(
        [
            "import-mentors",
            "--inspactor",
            str(tmp_path / "pool.xlsx"),
            "--pool-type",
            "matrix",
            "--local-db",
            str(tmp_path / "cache.sqlite"),
        ]
    )

    assert args.pool_type == "matrix"


def test_import_mentors_parser_defaults_to_inspactor(tmp_path: Path) -> None:
    parser = cli._build_parser()
    args = parser.parse_args(
        [
            "import-mentors",
            "--inspactor",
            str(tmp_path / "pool.xlsx"),
            "--local-db",
            str(tmp_path / "cache.sqlite"),
        ]
    )

    assert args.pool_type == "inspactor"
    assert args.pool_sheet is None


def test_import_mentors_cli_accepts_inspactor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pool_file = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(pool_file, engine="openpyxl") as writer:
        pd.DataFrame({"mentor_id": [1]}).to_excel(writer, sheet_name="inspactor", index=False)

    called: dict[str, object] = {}

    monkeypatch.setattr(cli, "_resolve_local_db", lambda args: object())
    monkeypatch.setattr(cli.cli_legacy, "_resolve_local_db", lambda args: object())
    monkeypatch.setattr(
        cli,
        "import_mentor_pool_from_excel",
        lambda path, **kwargs: called.update(kwargs) or pd.DataFrame(),
    )
    monkeypatch.setattr(
        cli.cli_legacy,
        "import_mentor_pool_from_excel",
        lambda path, **kwargs: called.update(kwargs) or pd.DataFrame(),
    )

    exit_code = cli.main(
        [
            "import-mentors",
            "--inspactor",
            str(pool_file),
            "--local-db",
            str(tmp_path / "cache.sqlite"),
        ],
        progress_factory=lambda: (lambda *_args, **_kwargs: None),
    )

    assert exit_code == 0
    assert called["pool_type"] == "inspactor"
    assert called["pool_source"] == "inspactor"


def test_import_mentors_cli_sets_matrix_sheet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pool_file = tmp_path / "pool.xlsx"
    with pd.ExcelWriter(pool_file, engine="openpyxl") as writer:
        pd.DataFrame({"mentor_id": [1]}).to_excel(writer, sheet_name="matrix", index=False)

    called: dict[str, object] = {}

    monkeypatch.setattr(cli, "_resolve_local_db", lambda args: object())
    monkeypatch.setattr(cli.cli_legacy, "_resolve_local_db", lambda args: object())
    monkeypatch.setattr(
        cli,
        "import_mentor_pool_from_excel",
        lambda path, **kwargs: called.update(kwargs) or pd.DataFrame(),
    )
    monkeypatch.setattr(
        cli.cli_legacy,
        "import_mentor_pool_from_excel",
        lambda path, **kwargs: called.update(kwargs) or pd.DataFrame(),
    )

    exit_code = cli.main(
        [
            "import-mentors",
            "--inspactor",
            str(pool_file),
            "--pool-type",
            "matrix",
            "--local-db",
            str(tmp_path / "cache.sqlite"),
        ],
        progress_factory=lambda: (lambda *_args, **_kwargs: None),
    )

    assert exit_code == 0
    assert called["pool_type"] == "matrix"
    assert called["pool_sheet"] == "matrix"
