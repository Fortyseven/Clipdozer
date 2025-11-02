from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from app.media.playback import VideoPlaybackController


class DummyClipAdapter:
    def __init__(self, duration=2.0, fps=20):
        self.duration = duration
        self.fps = fps
        self._frames = int(duration * fps)

    @classmethod
    def from_clip(cls, clip):
        return cls()

    def get_frame(self, t):
        return None  # we don't need actual frames


def test_playback_monotonic_qtimer():
    QCoreApplication.instance() or QCoreApplication([])
    controller = VideoPlaybackController()
    # Inject dummy adapter directly
    controller._clip_adapter = DummyClipAdapter(duration=2.0, fps=15)
    controller._state.fps = controller._clip_adapter.fps
    controller._state.total_frames = int(
        controller._clip_adapter.duration * controller._clip_adapter.fps
    )
    controller.play()
    positions = []

    def on_pos(p):
        positions.append(p)

    controller.positionChanged.connect(on_pos)
    # Process events for a short period
    loop = QEventLoop()
    # Drive ~25 iterations using a single-shot timer chain
    iterations = {"count": 0}

    def step():
        iterations["count"] += 1
        if iterations["count"] >= 25:
            loop.quit()
        else:
            QTimer.singleShot(25, step)

    QTimer.singleShot(25, step)
    loop.exec()
    controller.pause()
    # Ensure positions are strictly increasing (monotonic)
    assert positions == sorted(positions), (
        "Playback positions should be monotonic increasing"
    )
    # Ensure we progressed more than a few frames
    assert len(positions) > 5
