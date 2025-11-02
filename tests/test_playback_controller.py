from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from moviepy import ColorClip
from app.media.playback import VideoPlaybackController

_app = None


def _ensure_app():
    global _app
    if _app is None:
        _app = QApplication.instance() or QApplication([])


def test_playback_controller_basic(tmp_path):
    _ensure_app()
    # Create a short clip
    video_path = tmp_path / "basic.mp4"
    clip = ColorClip(size=(32, 32), color=(10, 20, 30), duration=0.5)
    clip.write_videofile(str(video_path), fps=24)
    clip.close()

    controller = VideoPlaybackController()
    received = {}

    def on_frame(frame, t):
        received["frame"] = frame
        received["t"] = t

    controller.frameReady.connect(on_frame)
    controller.load(str(video_path))
    # After load+seek(0) we should have at least one frame
    assert "frame" in received and received["frame"] is not None
    first_t = received["t"]
    assert first_t == 0.0

    # Seek to mid position
    controller.seek(0.25)
    assert received["t"] == controller.position()

    # Test play advances frames (process events for a short time)
    controller.play()
    loop = QEventLoop()
    QTimer.singleShot(120, loop.quit)  # allow a few ticks (~3 frames)
    loop.exec()
    controller.pause()
    assert controller.position() > 0.0
