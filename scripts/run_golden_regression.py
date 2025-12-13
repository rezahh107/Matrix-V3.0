"""Thin CLI wrapper delegating golden regression to the infra runner."""

from __future__ import annotations

from collections.abc import Sequence

from app.infra.golden import regression_runner


def main(argv: Sequence[str] | None = None) -> int:
    """Entrypoint proxy for golden regression scenarios."""
    return regression_runner.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
