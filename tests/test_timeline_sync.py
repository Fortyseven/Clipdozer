from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from moviepy import ColorClip
from app.ui.main_window import MainWindow

_app = None


def _ensure():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


def test_timeline_updates_during_play(tmp_path):
    _ensure()
    path = tmp_path / "sync.mp4"
    clip = ColorClip(size=(32, 32), color=(255, 128, 0), duration=0.4)
    clip.write_videofile(str(path), fps=24)
    clip.close()
    win = MainWindow()
    win.loadMediaPath(str(path))
    # Start playback
    win.clip_controller.play()
    start_pos = win.clip_scrub.currentPosition() if win.clip_scrub else 0.0
    loop = QEventLoop()
    QTimer.singleShot(180, loop.quit)  # allow several frames
    loop.exec()
    end_pos = win.clip_scrub.currentPosition() if win.clip_scrub else 0.0
    assert end_pos > start_pos
