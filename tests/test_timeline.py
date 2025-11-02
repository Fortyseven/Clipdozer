from app.timeline import format_time, TimelineWidget
from PySide6.QtWidgets import QApplication

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


def test_format_time_basic():
    assert format_time(0) == "00:00.000"
    assert format_time(1.234) == "00:01.234"
    assert format_time(61.0) == "01:01.000"


def test_marker_set():  # simplified: ensure QApplication
    _ensure_app()
    w = TimelineWidget()
    w.setDuration(10.0)
    w.setPosition(2.0)
    w.setInPoint()
    assert w.inOut()[0] is not None
    w.setPosition(5.0)
    w.setOutPoint()
    i, o = w.inOut()
    assert i is not None and o is not None and o >= i
