from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

__all__ = ["QADebugContext", "QABreadcrumb"]


@dataclass(frozen=True)
class QADebugContext:
    """Lightweight, structured debug context for QA rules.

    The context stays Core-only and immutable so that debug engines can
    reason about rule lineage without coupling to I/O or UI concerns.
    """

    important_columns: tuple[str, ...]
    source_tables: tuple[str, ...]
    lineage_keys: tuple[str, ...]
    diagnosis_hints: tuple[str, ...]
    canary_thresholds: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "important_columns", tuple(self.important_columns))
        object.__setattr__(self, "source_tables", tuple(self.source_tables))
        object.__setattr__(self, "lineage_keys", tuple(self.lineage_keys))
        object.__setattr__(self, "diagnosis_hints", tuple(self.diagnosis_hints))
        object.__setattr__(
            self,
            "canary_thresholds",
            MappingProxyType(dict(self.canary_thresholds)),
        )

    @classmethod
    def from_sequences(
        cls,
        *,
        important_columns: Sequence[str] | None = None,
        source_tables: Sequence[str] | None = None,
        lineage_keys: Sequence[str] | None = None,
        diagnosis_hints: Sequence[str] | None = None,
        canary_thresholds: Mapping[str, float] | None = None,
    ) -> QADebugContext:
        """Helper to build an immutable context from plain sequences."""

        return cls(
            important_columns=tuple(important_columns or ()),
            source_tables=tuple(source_tables or ()),
            lineage_keys=tuple(lineage_keys or ()),
            diagnosis_hints=tuple(diagnosis_hints or ()),
            canary_thresholds=MappingProxyType(dict(canary_thresholds or {})),
        )


@dataclass(frozen=True)
class QABreadcrumb:
    """Minimal breadcrumb for QA pipelines."""

    step_id: str
    label: str
    row_count: int
    key_stats: Mapping[str, object]

    def to_payload(self) -> Mapping[str, object]:
        """Return a dict-serializable payload for DataFrame attrs."""

        return {
            "step_id": self.step_id,
            "label": self.label,
            "row_count": int(self.row_count),
            "key_stats": dict(self.key_stats),
        }
