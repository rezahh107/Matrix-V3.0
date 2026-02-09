"""Compatibility helpers for enum types across Python runtimes."""

from __future__ import annotations

from enum import Enum

try:  # pragma: no cover - exercised by runtime import path
    from enum import StrEnum as StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback
    StrEnum = Enum("StrEnum", {}, type=str)
