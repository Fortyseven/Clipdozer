"""Legacy entrypoint maintained for backward compatibility.

Delegates to `app.ui.main_window.run`.
"""

from .ui.main_window import run, MainWindow  # noqa: F401

__all__ = ["run", "MainWindow"]
