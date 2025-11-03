from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from moviepy import ColorClip
from app.ui.main_window import MainWindow

_app = None


def _ensure():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


def test_scrub_pause_resume(tmp_path):
    _ensure()
    path = tmp_path / "scrub.mp4"
    clip = ColorClip(size=(32, 32), color=(0, 0, 0), duration=0.6)
    clip.write_videofile(str(path), fps=24)
    clip.close()
    win = MainWindow()
    win.loadMediaPath(str(path))
    win.clip_controller.play()
    # Let a few frames play
    loop = QEventLoop()
    QTimer.singleShot(120, loop.quit)
    loop.exec()
    pre_drag_pos = win.clip_controller.position()
    assert pre_drag_pos > 0
    # Simulate drag start
    win.clip_scrub.dragStarted.emit()
    assert not win.clip_controller._state.playing
    # Change position mid-drag
    new_t = min(pre_drag_pos + 0.1, win.clip_controller._state.duration - 0.01)
    win.clip_scrub.positionChanged.emit(new_t)
    # End drag (seek commit and resume)
    win.clip_scrub.seekRequested.emit(new_t)
    win.clip_scrub.dragEnded.emit()
    # Allow resume and a couple more frames
    loop2 = QEventLoop()
    QTimer.singleShot(140, loop2.quit)
    loop2.exec()
    assert win.clip_controller.position() > new_t
