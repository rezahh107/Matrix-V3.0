"""توابع کمکی برای تفسیر ترجیحات مرکز از Policy و ورودی کاربر."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import SupportsInt, cast

from .center_manager import resolve_center_manager_config
from .policy_loader import PolicyConfig

__all__ = [
    "parse_center_manager_config",
    "normalize_center_priority",
]


def _normalize_names(payload: object) -> list[str]:
    """تبدیل ورودی متنی یا لیستی به تاپل تمیز و یکتا."""

    if payload is None:
        return []
    items = payload if isinstance(payload, (list, tuple)) else [payload]
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        cleaned.append(text)
        seen.add(text)
    return cleaned


def _normalize_override_map(source: Mapping[object, object] | None) -> dict[int, list[str]]:
    """تبدیل نگاشت ورودی (کلید عددی یا متنی) به ساختار پایدار."""

    if source is None:
        return {}
    normalized: dict[int, list[str]] = {}
    for key, value in source.items():
        if not isinstance(key, (str, int, SupportsInt)):
            continue
        try:
            center_id = int(key)
        except (TypeError, ValueError):
            continue
        names = _normalize_names(value)
        normalized[center_id] = list(names)
    return normalized


def parse_center_manager_config(
    policy: PolicyConfig,
    ui_overrides: Mapping[object, object] | None = None,
    cli_overrides: Mapping[object, object] | None = None,
) -> dict[int, tuple[str, ...]]:
    """ساخت نگاشت «مرکز → مدیران» با ادغام Policy و ورودی کاربر."""

    result, _ = resolve_center_manager_config(
        policy=policy,
        ui_managers=cast(Mapping[int | str, object], _normalize_override_map(ui_overrides)),
        cli_managers=cast(Mapping[int | str, object], _normalize_override_map(cli_overrides)),
    )
    return {center_id: tuple(names) for center_id, names in result.items()}


def normalize_center_priority(
    policy: PolicyConfig, priority: Sequence[int] | None
) -> tuple[int, ...]:
    """نرمال‌سازی لیست اولویت مراکز با تضمین پوشش تمام مراکز policy."""

    _, normalized = resolve_center_manager_config(
        policy=policy,
        cli_priority=priority or tuple(),
    )
    return tuple(normalized)
