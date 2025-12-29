from pathlib import Path

from app.infra import cli


def test_allocate_parser_defaults_to_inspactor(tmp_path: Path) -> None:
    parser = cli._build_parser()
    args = parser.parse_args(["allocate", "--output", str(tmp_path / "out.xlsx")])

    assert args.pool_type == "inspactor"
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
