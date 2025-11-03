from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from moviepy import ColorClip

from app.ui.main_window import MainWindow

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


def test_preview_shrinks_on_window_resize(tmp_path):
    """Regression test: preview should be able to shrink after being large.

    Steps:
    1. Load a small clip so we have a frame.
    2. Enlarge the window (thus preview) then shrink it.
    3. Ensure the preview widget width decreases accordingly.
    """
    _ensure_app()
    video_path = tmp_path / "resize_preview.mp4"
    clip = ColorClip(size=(64, 36), color=(255, 0, 0), duration=0.5)
    clip.write_videofile(str(video_path), fps=24)
    clip.close()

    win = MainWindow()
    win.resize(1000, 800)
    win.show()
    win.loadMediaPath(str(video_path))

    # Allow initial frame render
    loop = QEventLoop()
    QTimer.singleShot(100, loop.quit)
    loop.exec()
    initial_width = win.video_preview.width()

    # Shrink window drastically
    win.resize(400, 300)
    loop = QEventLoop()
    QTimer.singleShot(150, loop.quit)
    loop.exec()
    shrunk_width = win.video_preview.width()

    assert shrunk_width < initial_width, (initial_width, shrunk_width)
