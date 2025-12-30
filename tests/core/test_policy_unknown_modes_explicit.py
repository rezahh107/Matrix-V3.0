from __future__ import annotations

import json
from pathlib import Path

import yaml


def test_policy_json_unknown_modes_explicit() -> None:
    data = json.loads(Path("config/policy.json").read_text(encoding="utf-8"))
    assert data["unknown_data_mode"] == "issue"
    assert data["center_management"]["unknown_manager_mode"] == "wildcard"


def test_policy_yaml_unknown_modes_explicit() -> None:
    data = yaml.safe_load(Path("policy.yaml").read_text(encoding="utf-8"))
    sample = yaml.safe_load(Path("policy_sample.yaml").read_text(encoding="utf-8"))
    assert data["unknown_data_mode"] == "issue"
    assert data["center_management"]["unknown_manager_mode"] == "wildcard"
    assert sample["unknown_data_mode"] == "issue"
    assert sample["center_management"]["unknown_manager_mode"] == "wildcard"
