"""GUI-owned per-run output workspace helpers.

The CLI keeps its explicit-path contract.  This module only gives the Qt GUI a
predictable, collision-safe directory and filename policy for each execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from PySide6.QtCore import QCalendar, QDateTime, QStandardPaths, Qt

_RUN_TYPES: Final[tuple[str, ...]] = ("build", "allocate")
_PRIMARY_OUTPUT_NAMES: Final[dict[str, str]] = {
    "build": "matrix",
    "allocate": "allocation",
}


@dataclass(frozen=True)
class RunOutputWorkspace:
    """Resolved filesystem workspace for one GUI execution."""

    run_type: str
    root_dir: Path
    run_dir: Path
    stamp: str
    started_at_iso: str

    @property
    def primary_output_path(self) -> Path:
        stem = _PRIMARY_OUTPUT_NAMES[self.run_type]
        return self.run_dir / f"{stem}_{self.stamp}.xlsx"

    def artifact_path(self, semantic_name: str, *, suffix: str = ".xlsx") -> Path:
        """Return a stable run-local artifact path for an optional GUI export."""

        normalized = semantic_name.strip().replace("-", "_")
        if not normalized or any(char in normalized for char in "/\\:"):
            raise ValueError("semantic artifact name must be a Windows-safe identifier")
        normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        return self.run_dir / f"{normalized}_{self.stamp}{normalized_suffix}"


def default_output_root() -> Path:
    """Return the user-facing default root without creating it."""

    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    if documents.strip():
        base = Path(documents)
    else:
        home = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.HomeLocation)
        base = Path(home) if home.strip() else Path.home()
    return base / "MentorAllocation" / "Output"


def jalali_date_string(
    moment: QDateTime,
    *,
    calendar: QCalendar | None = None,
) -> str:
    """Format a Qt date as zero-padded ASCII Solar-Hijri YYYY-MM-DD."""

    jalali = calendar or QCalendar(QCalendar.System.Jalali)
    if not jalali.isValid():
        raise RuntimeError("Qt Jalali calendar support is unavailable")
    parts = jalali.partsFromDate(moment.date())
    if not parts.isValid():
        raise ValueError("date cannot be represented by the Jalali calendar")
    return f"{int(parts.year):04d}-{int(parts.month):02d}-{int(parts.day):02d}"


def run_stamp(
    moment: QDateTime,
    *,
    calendar: QCalendar | None = None,
) -> str:
    """Return the Windows-safe shared timestamp used by a run directory/files."""

    date_text = jalali_date_string(moment, calendar=calendar)
    time_text = moment.time().toString("HHmmss")
    return f"{date_text}_{time_text}"


def create_run_workspace(
    root_dir: str | Path,
    run_type: str,
    *,
    moment: QDateTime | None = None,
    calendar: QCalendar | None = None,
) -> RunOutputWorkspace:
    """Create a unique run directory without overwriting an earlier execution."""

    if run_type not in _RUN_TYPES:
        raise ValueError(f"unsupported run type: {run_type}")

    resolved_root = Path(root_dir).expanduser()
    resolved_root.mkdir(parents=True, exist_ok=True)
    started = moment or QDateTime.currentDateTime()
    stamp = run_stamp(started, calendar=calendar)
    base_name = f"{stamp}_{run_type}"

    candidate = resolved_root / base_name
    collision_index = 1
    while candidate.exists():
        collision_index += 1
        candidate = resolved_root / f"{base_name}_{collision_index:02d}"
    candidate.mkdir(parents=False, exist_ok=False)

    return RunOutputWorkspace(
        run_type=run_type,
        root_dir=resolved_root,
        run_dir=candidate,
        stamp=stamp,
        started_at_iso=started.toString(Qt.DateFormat.ISODateWithMs),
    )