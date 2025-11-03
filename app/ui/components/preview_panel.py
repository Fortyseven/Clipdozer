"""Preview Panel components.

Terminology:
- Clip Preview Panel: video player + Scrubber (with thumbnails & waveform enabled)
- Project Preview Panel: video player + Scrubber (without thumbnails & waveform)

This module introduces `BasePreviewPanel` plus concrete `ClipPreviewPanel` and
`ProjectPreviewPanel` classes that wrap a `VideoPlaybackController`, a
`VideoPreviewWidget` for visual frame display, and a `ScrubberWidget` for user
navigation.

For now we adapt existing `VideoPlaybackController`, `VideoPreviewWidget`, and
`ScrubberWidget`. Future evolution may split responsibilities:
- Frame decoding timing separated from preview scaling logic
- Distinct scrubber configuration state object

Public API (initial):
    load(path_or_clip) -> load source media into playback controller & scrubber
    controller (VideoPlaybackController)
    preview (VideoPreviewWidget)
    scrubber (ScrubberWidget)

Signals reused from controller & scrubber.
"""

from __future__ import annotations

from typing import Union

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ...media.playback import VideoPlaybackController, VideoPreviewWidget
from .scrubber import ScrubberWidget

try:  # MoviePy import for path loading convenience
    from moviepy import VideoFileClip
except ImportError:  # pragma: no cover
    try:
        from moviepy.editor import VideoFileClip  # type: ignore
    except ImportError:  # pragma: no cover
        VideoFileClip = None  # type: ignore


class BasePreviewPanel(QWidget):
    """Common panel assembly for a preview + scrubber."""

    def __init__(
        self,
        parent=None,
        show_thumbnails=True,
        show_waveform=True,
        label: str | None = None,
    ):
        super().__init__(parent)
        self.controller = VideoPlaybackController(self)
        self.preview = VideoPreviewWidget(self.controller)
        # Transport visibility decided by subclass; default hide (project panel) unless overridden
        self.scrubber = ScrubberWidget(show_transport=False)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        if label:
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#bbb;font-size:11px;padding:2px 4px;")
            layout.addWidget(lbl)
        layout.addWidget(self.preview, stretch=1)
        layout.addWidget(self.scrubber)
        self.setLayout(layout)
        # Wire interactions: scrubber drives controller seek; controller updates scrubber position
        self.scrubber.positionChanged.connect(
            lambda t: self.controller.seek(t, emit_frame=True)
        )
        self.controller.positionChanged.connect(self.scrubber.setPosition)
        # Configure optional elements
        if not show_thumbnails:
            self.scrubber.enableThumbnails(False)
        if not show_waveform:
            self.scrubber.enableWaveform(False)

    def load(self, source: Union[str, VideoFileClip]):
        """Load a clip path or existing VideoFileClip into the controller + scrubber."""
        if isinstance(source, str):
            if VideoFileClip is None:
                raise RuntimeError("MoviePy not available for path load")
            clip = VideoFileClip(source)
        else:
            clip = source
        self.controller.load(clip)
        self.scrubber.setClip(clip)
        self.scrubber.setPosition(0.0)


class ClipPreviewPanel(BasePreviewPanel):
    def __init__(self, parent=None):
        # Rebuild base with transport visible
        super().__init__(
            parent, show_thumbnails=True, show_waveform=True, label="Clip Preview"
        )
        # Replace scrubber with one that has transport visible
        layout = self.layout()
        if layout is not None:
            # Remove old scrubber widget
            layout.removeWidget(self.scrubber)
            self.scrubber.deleteLater()
            self.scrubber = ScrubberWidget(show_transport=True)
            layout.addWidget(self.scrubber)
        # Re-wire required signals after replacement
        self.scrubber.positionChanged.connect(
            lambda t: self.controller.seek(t, emit_frame=True)
        )
        self.controller.positionChanged.connect(self.scrubber.setPosition)
        # Wire transport actions to playback controller
        self.scrubber.playToggled.connect(self._onPlayToggle)
        self.scrubber.frameStep.connect(self._onFrameStep)
        # Update play button when controller state changes
        self.controller.stateChanged.connect(self._updatePlayButton)

    def _onPlayToggle(self):
        playing = getattr(getattr(self.controller, "_state", None), "playing", False)
        if playing:
            self.controller.pause()
        else:
            self.controller.play()

    def _onFrameStep(self, delta: int):
        # Pause if currently playing
        if getattr(getattr(self.controller, "_state", None), "playing", False):
            self.controller.pause()
        fps = getattr(getattr(self.controller, "_state", None), "fps", 24.0) or 24.0
        cur_t = self.controller.position()
        new_t = max(0.0, cur_t + (delta / fps))
        duration = getattr(getattr(self.controller, "_state", None), "duration", None)
        if duration is not None:
            new_t = min(new_t, duration)
        self.controller.seek(new_t)
        self.scrubber.setPosition(new_t)

    def _updatePlayButton(self, state: str):
        self.scrubber.updatePlayButton(state == "playing")


class ProjectPreviewPanel(BasePreviewPanel):
    def __init__(self, parent=None):
        super().__init__(
            parent, show_thumbnails=False, show_waveform=False, label="Project Preview"
        )
        # Project composition not implemented yet; load() will be a no-op until provided a composite clip.


__all__ = ["ClipPreviewPanel", "ProjectPreviewPanel", "BasePreviewPanel"]
