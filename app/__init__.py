"""Top-level application package exports.

Public API surface (keep minimal):
 - MainWindow (UI entry point)
 - TimelineWidget, format_time (timeline UI/logic)

Backward compatibility: code may still import from `app.timeline` directly; tests
use that path. Prefer importing from `app.core.timeline` for new modules.
"""

from .ui.main_window import MainWindow  # noqa: F401
from .core.timeline import TimelineWidget, format_time  # noqa: F401

__all__ = ["MainWindow", "TimelineWidget", "format_time"]
