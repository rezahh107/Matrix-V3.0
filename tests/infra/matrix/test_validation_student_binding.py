from __future__ import annotations

from dataclasses import replace

from app.core.common.domain import BuildConfig, StudentBindingKind
from app.core.matrix.validation import student_binding_for_row
from app.core.policy_loader import load_policy


def _build_cfg() -> BuildConfig:
    policy = load_policy()
    channel_rules = replace(policy.allocation_channels, school_codes=(1001, 2002))
    tuned_policy = replace(policy, allocation_channels=channel_rules)
    return BuildConfig(policy=tuned_policy)


def test_student_binding_delegates_to_school_rule() -> None:
    cfg = _build_cfg()
    status_col = cfg.policy.stage_column("graduation_status")
    school_col = cfg.policy.columns.school_code
    binding = student_binding_for_row({status_col: 1, school_col: 1001}, cfg=cfg)
    assert binding is StudentBindingKind.SCHOOL


def test_student_binding_defaults_to_normal_for_non_school() -> None:
    cfg = _build_cfg()
    status_col = cfg.policy.stage_column("graduation_status")
    school_col = cfg.policy.columns.school_code
    binding = student_binding_for_row({status_col: 1, school_col: 9999}, cfg=cfg)
    assert binding is StudentBindingKind.NORMAL
