# mypy: follow_imports=skip

"""توابع کمکی لایهٔ Core برای برچسب زدن وضعیت صلاحیت و مراحل."""

from __future__ import annotations

from collections.abc import Mapping

# mypy: follow_imports = skip

from app.core.policy_loader import PolicyConfig, load_policy

from .types import TraceStageFlags, TraceStageName, ensure_trace_stage_name

__all__ = ["build_stage_pass_flags"]


def build_stage_pass_flags(
    stage_candidate_counts: Mapping[TraceStageName, int] | None,
    *,
    policy: PolicyConfig | None = None,
) -> TraceStageFlags:
    """تبدیل شمارندهٔ مراحل به فلگ عبور/عدم‌عبور برای Trace."""

    if policy is None:
        policy = load_policy()
    flags: TraceStageFlags = {
        ensure_trace_stage_name(stage): False for stage in policy.trace_stage_names
    }
    if not stage_candidate_counts:
        return flags
    for stage in policy.trace_stage_names:
        typed_stage = ensure_trace_stage_name(stage)
        try:
            flags[typed_stage] = int(stage_candidate_counts.get(typed_stage, 0)) > 0
        except Exception:
            flags[typed_stage] = False
    return flags
