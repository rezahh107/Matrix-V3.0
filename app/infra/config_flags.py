from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

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


def load_feature_flags(env: Mapping[str, str] | None = None) -> FeatureFlags:
    environment = dict(os.environ) if env is None else env
    return FeatureFlags(
        join_buckets=_parse_bool(
            environment.get("SMARTALLOC_OPT_JOIN_BUCKETS"),
            default=False,
        ),
    )
