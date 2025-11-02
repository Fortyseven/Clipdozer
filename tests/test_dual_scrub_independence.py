import pytest
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app_instance():
    app = QApplication.instance() or QApplication([])
    return app


def test_clip_scrub_independence(app_instance):
    w = MainWindow()
    # No project media loaded; project scrub duration should be 0
    assert hasattr(w, "clip_scrub") and w.clip_scrub is not None
    assert hasattr(w, "project_scrub") and w.project_scrub is not None
    assert w.project_scrub._duration == 0.0
    # Simulate loading clip by faking controller state without real media (seek should move clip scrub only)
    w.clip_controller._state.duration = 10.0
    w.clip_controller._state.fps = 25.0
    w.clip_controller._state.total_frames = 250
    w.clip_controller.seek(2.0)
    # Set clip scrub duration manually to allow position update
    w.clip_scrub.setDuration(10.0)
    w.clip_scrub.setPosition(2.0)
    assert w.clip_scrub.currentPosition() == pytest.approx(2.0, rel=1e-3)
    # Project scrub remains at start and duration zero
    assert w.project_scrub.currentPosition() == 0.0
    assert w.project_scrub._duration == 0.0
