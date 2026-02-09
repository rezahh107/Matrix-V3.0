"""Compatibility helpers for enum types across Python runtimes."""

from __future__ import annotations

from enum import Enum

try:  # pragma: no cover - exercised by runtime import path
    from enum import StrEnum as StrEnum
except ImportError:  # pragma: no cover - Python < 3.11 fallback
    class StrEnum(str, Enum):
        """Compatibility fallback for :class:`enum.StrEnum` on Python < 3.11."""

