from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_TRUE_VALUES: set[str] = {"1", "true", "yes", "on", "y", "t"}
_FALSE_VALUES: set[str] = {"0", "false", "no", "off", "n", "f"}


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


@dataclass(frozen=True)
class FeatureFlags:
    join_buckets: bool


@dataclass(frozen=True)
class UserSettings:
    """User-personalized toggles for optional diagnostics and exports."""

    enable_history_metrics: bool = False
    enable_trace_debug_sheets: bool = False
    enable_trace_export: bool = False
    enable_mentor_trace_debug: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "enable_history_metrics": self.enable_history_metrics,
            "enable_trace_debug_sheets": self.enable_trace_debug_sheets,
            "enable_trace_export": self.enable_trace_export,
            "enable_mentor_trace_debug": self.enable_mentor_trace_debug,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> UserSettings:
        if payload is None:
            return cls()
        return cls(
            enable_history_metrics=bool(payload.get("enable_history_metrics", False)),
            enable_trace_debug_sheets=bool(payload.get("enable_trace_debug_sheets", False)),
            enable_trace_export=bool(payload.get("enable_trace_export", False)),
            enable_mentor_trace_debug=bool(payload.get("enable_mentor_trace_debug", False)),
        )


def load_feature_flags(env: Mapping[str, str] | None = None) -> FeatureFlags:
    environment = dict(os.environ) if env is None else env
    return FeatureFlags(
        join_buckets=_parse_bool(
            environment.get("SMARTALLOC_OPT_JOIN_BUCKETS"),
            default=False,
        ),
    )


def _resolve_settings_path(path: Path | None) -> Path:
    if path is not None:
        return path
    return Path.home() / ".smart_alloc" / "user_settings.json"


def coerce_user_settings(settings: Any) -> UserSettings:
    """Convert incoming settings payloads into :class:`UserSettings`."""

    if isinstance(settings, UserSettings):
        return settings
    if isinstance(settings, Mapping):
        return UserSettings.from_mapping(settings)
    return UserSettings()


def load_user_settings(path: Path | None = None) -> UserSettings:
    """Load persisted user settings, falling back to defaults when missing."""

    settings_path = _resolve_settings_path(path)
    if not settings_path.exists():
        return UserSettings()

    try:
        with settings_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return UserSettings()

    return coerce_user_settings(payload)


def save_user_settings(settings: UserSettings, path: Path | None = None) -> Path:
    """Persist settings to a simple JSON file for reuse across UI/CLI."""

    settings_path = _resolve_settings_path(path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with settings_path.open("w", encoding="utf-8") as fh:
        json.dump(settings.to_dict(), fh, ensure_ascii=False, indent=2)
    return settings_path
