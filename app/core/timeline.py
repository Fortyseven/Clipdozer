"""Core timeline logic & widgets.

Currently this file mirrors the previous `app.timeline` implementation. In future
refactors we will split pure logic (time formatting, range selection, async
thumbnail generation orchestration) from Qt widget concerns. For now we keep
the TimelineWidget intact to avoid breaking tests and UI code.
"""

from __future__ import annotations

# Reuse existing implementation by importing from app.timeline for now.
# During incremental refactor we will migrate classes inward and remove the indirection.

from ..timeline import TimelineWidget  # noqa: F401  (UI widget stays in legacy module for now)
from ..services.media_generation import ThumbnailWorker, WaveformWorker  # noqa: F401
from ..utils.timefmt import format_time  # noqa: F401

__all__ = ["ThumbnailWorker", "WaveformWorker", "TimelineWidget", "format_time"]
