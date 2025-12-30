from __future__ import annotations

import pytest

from app.core.policy_loader import _normalize_center_management, _to_center_management_config


def test_unknown_manager_mode_validation_happens_in_normalization() -> None:
    center_map = {"*": 0}
    with pytest.raises(ValueError):
        _normalize_center_management(
            {"unknown_manager_mode": "invalid"},
            center_map,
        )


def test_to_center_management_config_accepts_normalized_value() -> None:
    normalized = _normalize_center_management(
        {"unknown_manager_mode": "wildcard"},
        {"*": 0},
    )
    config = _to_center_management_config(normalized)
    assert config.unknown_manager_mode == "wildcard"
