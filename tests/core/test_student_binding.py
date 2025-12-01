from dataclasses import replace

from app.core.common.domain import BuildConfig, StudentBindingKind, classify_student_binding
from app.core.policy_loader import load_policy


def _build_cfg_with_school_codes() -> BuildConfig:
    policy = load_policy()
    tuned_policy = replace(
        policy, allocation_channels=replace(policy.allocation_channels, school_codes=(1001, 2002))
    )
    return BuildConfig(policy=tuned_policy)


def _base_row(
    cfg: BuildConfig, *, school_code: int | None, status: int | None, postal: str = ""
) -> dict[str, object]:
    status_col = cfg.policy.stage_column("graduation_status")
    school_col = cfg.policy.columns.school_code
    row = {status_col: status if status is not None else None, school_col: school_code}
    # Postal code should have no effect on classification
    if postal:
        row["کدپستی"] = postal
    return row


def test_student_binding_school_member_active_student() -> None:
    cfg = _build_cfg_with_school_codes()
    row = _base_row(cfg, school_code=1001, status=1)
    assert classify_student_binding(row, cfg=cfg) is StudentBindingKind.SCHOOL


def test_student_binding_school_member_not_student_is_normal() -> None:
    cfg = _build_cfg_with_school_codes()
    row = _base_row(cfg, school_code=1001, status=0)
    assert classify_student_binding(row, cfg=cfg) is StudentBindingKind.NORMAL


def test_student_binding_non_member_student_is_normal() -> None:
    cfg = _build_cfg_with_school_codes()
    row = _base_row(cfg, school_code=9999, status=1)
    assert classify_student_binding(row, cfg=cfg) is StudentBindingKind.NORMAL


def test_student_binding_missing_school_code_defaults_to_normal() -> None:
    cfg = _build_cfg_with_school_codes()
    row = _base_row(cfg, school_code=0, status=1)
    assert classify_student_binding(row, cfg=cfg) is StudentBindingKind.NORMAL


def test_student_binding_ignores_postal_code() -> None:
    cfg = _build_cfg_with_school_codes()
    row = _base_row(cfg, school_code=0, status=1, postal="050")
    assert classify_student_binding(row, cfg=cfg) is StudentBindingKind.NORMAL


def test_student_binding_missing_status_uses_default() -> None:
    cfg = _build_cfg_with_school_codes()
    row = _base_row(cfg, school_code=2002, status=None)

    assert classify_student_binding(row, cfg=cfg) is StudentBindingKind.SCHOOL


def test_student_binding_non_student_string_status_is_normal() -> None:
    cfg = _build_cfg_with_school_codes()
    row = _base_row(cfg, school_code=2002, status="0")

    assert classify_student_binding(row, cfg=cfg) is StudentBindingKind.NORMAL
