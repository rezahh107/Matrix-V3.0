"""User settings helpers for diagnostic feature toggles.

This module provides a thin re-export layer over :mod:`app.infra.config_flags`
to give callers a stable import path for persisted user settings.
"""

from __future__ import annotations

from app.infra.config_flags import (  # re-export
    UserSettings,
    coerce_user_settings,
    load_user_settings,
    save_user_settings,
)

__all__ = [
    "UserSettings",
    "coerce_user_settings",
    "load_user_settings",
    "save_user_settings",
]
