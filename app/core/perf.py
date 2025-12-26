"""Lightweight performance instrumentation helpers for Core."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import AbstractContextManager, ContextDecorator, nullcontext
from types import TracebackType

__all__ = ["PerfTracker", "measure_time"]

PerfTracker = Callable[[str, float], None]


class _TimingContext(ContextDecorator):
    """Context manager that records elapsed time via a tracker."""

    def __init__(
        self, stage: str, tracker: PerfTracker, clock: Callable[[], float]
    ) -> None:
        self._stage = stage
        self._tracker = tracker
        self._clock = clock
        self._start: float | None = None

    def __enter__(self) -> None:
        self._start = self._clock()
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if self._start is not None:
            elapsed = self._clock() - self._start
            self._tracker(self._stage, elapsed)
        return False


def measure_time(
    stage: str, tracker: PerfTracker | None, *, clock: Callable[[], float] | None = None
) -> AbstractContextManager[None]:
    """Return a context manager that tracks elapsed time for a stage.

    When ``tracker`` is ``None`` the returned context manager is a no-op with
    effectively zero overhead. The ``clock`` parameter is intended for testing
    or deterministic timing and defaults to :func:`time.perf_counter`.
    """

    if tracker is None:
        return nullcontext()

    active_clock = clock or time.perf_counter
    return _TimingContext(stage, tracker, active_clock)

