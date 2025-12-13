"""CLI-facing entrypoints for infra-driven workflows.

This package re-exports the legacy single-file CLI implementation to preserve
helper access (e.g., ``_sanitize_pool_for_allocation``) while exposing
package-local golden entrypoints.
"""

from __future__ import annotations

import app.infra.cli_legacy as cli_legacy
from app.infra.cli_legacy import *  # noqa: F401,F403 - re-export legacy CLI surface

from . import cli_entrypoints_golden

__all__ = getattr(cli_legacy, "__all__", []) + ["cli_entrypoints_golden"]


def __getattr__(name: str):
    return getattr(cli_legacy, name)
