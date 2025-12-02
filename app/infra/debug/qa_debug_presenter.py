"""Format helpers for QA debug stories shared between CLI and UI."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.infra.debug.qa_debug_engine import QADebugStory

__all__ = ["format_story_for_text", "summarize_story"]


def summarize_story(story: QADebugStory) -> str:
    """Return a short, single-line summary for list views."""

    lead = story.story[0] if story.story else str(story.rule_id)
    return f"{story.rule_id} — {lead}".strip()


def _iter_context_items(context: Mapping[str, object]) -> list[str]:
    lines: list[str] = []
    for key in sorted(context):
        value = context[key]
        rendered = _render_value(value)
        lines.append(f"{key}: {rendered}")
    return lines


def _render_value(value: object) -> str:
    if isinstance(value, Mapping):
        inner = ", ".join(f"{k}={_render_value(v)}" for k, v in sorted(value.items()))
        return f"{{{inner}}}"
    if isinstance(value, (list, tuple, set, frozenset)):
        return ", ".join(_render_value(v) for v in value)
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return ", ".join(str(part) for part in value)
    return str(value)


def format_story_for_text(story: QADebugStory) -> str:
    """Render a debug story as markdown-ish text for copy/export."""

    law_refs = ", ".join(story.law_refs) if story.law_refs else "—"
    lines = [
        f"Rule: {story.rule_id}",
        f"Severity: {story.severity}",
        f"LAW refs: {law_refs}",
    ]
    if story.evidence:
        lines.append(f"Evidence: {story.evidence}")
    context_items = _iter_context_items(story.context)
    if context_items:
        lines.append("Context:")
        lines.extend(f"- {item}" for item in context_items)
    if lines:
        lines.append("")
    lines.extend(story.story)
    return "\n".join(lines)
