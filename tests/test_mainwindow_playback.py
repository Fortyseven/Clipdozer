from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from moviepy import ColorClip
from app.ui.main_window import MainWindow

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


def test_mainwindow_load_and_preview(tmp_path):
    _ensure_app()
    video_path = tmp_path / "preview.mp4"
    clip = ColorClip(size=(48, 24), color=(0, 0, 255), duration=0.3)
    clip.write_videofile(str(video_path), fps=24)
    clip.close()

    win = MainWindow()
    win.loadMediaPath(str(video_path))
    # Process events to allow controller to emit initial frame
    loop = QEventLoop()
    QTimer.singleShot(50, loop.quit)
    loop.exec()
    pix = win.video_preview.pixmap()
    assert pix is not None and not pix.isNull()
