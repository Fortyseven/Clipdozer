"""Scrubber UI component.

A Scrubber is a reusable UI widget that lets the user navigate through a video clip's
frames/time. It optionally supports:
- In/Out markers
- Thumbnail strip (toggleable)
- Audio waveform (toggleable)

Implementation notes:
Wraps the current implementation (formerly TimelineWidget) while retaining
existing asynchronous thumbnail and waveform generation.

Public API (initial shim):
    setClip(clip) -> attach a MoviePy VideoFileClip for thumbnails/waveform generation
    setPosition(t: float) -> update current playhead position (seconds)
    positionChanged(float) signal -> emitted during user scrubbing (preview seek)
    seekRequested(float) signal -> emitted when drag released (commit seek)
    setInPoint(), setOutPoint(), clearInPoint(), clearOutPoint(), inOut()

Success criteria:
-- New terminology available through this wrapper class.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal

try:
    from ...timeline import TimelineWidget as _LegacyTimelineWidget
except Exception as e:  # pragma: no cover
    raise RuntimeError(f"Failed to import legacy timeline: {e}")


class ScrubberWidget(QWidget):
    """Composite scrubber widget with optional transport controls.

    Internally hosts the legacy `_LegacyTimelineWidget` plus an optional row of
    transport + marker buttons for reuse across preview panels.

    Signals re-exposed from internal timeline plus additional user actions:
        positionChanged(float)
        seekRequested(float)
        inOutChanged(in_t, out_t)
        playToggled()          # User clicked play/pause toggle
        frameStep(int)         # User requested single-frame step (+1/-1)
        markInRequested()      # User clicked In
        markOutRequested()     # User clicked Out

    Public API compatibility retained:
        setClip(clip)
        setPosition(t)
        enableThumbnails(bool)
        enableWaveform(bool)
        setInPoint()/setOutPoint()/clearInPoint()/clearOutPoint()/inOut()

    Configuration:
        show_transport: bool (default True) controls visibility of buttons row.
    """

    positionChanged = Signal(float)
    seekRequested = Signal(float)
    inOutChanged = Signal(object, object)
    dragStarted = Signal()
    dragEnded = Signal()
    playToggled = Signal()
    frameStep = Signal(int)
    markInRequested = Signal()
    markOutRequested = Signal()

    def __init__(self, parent=None, *, show_transport: bool = True):
        super().__init__(parent)
        self._timeline = _LegacyTimelineWidget()
        self._show_transport = show_transport
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._timeline)
        # Optional transport bar
        self._transport_bar = QWidget()
        tb_layout = QHBoxLayout()
        tb_layout.setContentsMargins(2, 2, 2, 2)
        tb_layout.setSpacing(4)
        self._btn_back = QPushButton("⟲")
        self._btn_play = QPushButton("▶")
        self._btn_fwd = QPushButton("⟳")
        self._btn_in = QPushButton("I")
        self._btn_out = QPushButton("O")
        for b in [
            self._btn_back,
            self._btn_play,
            self._btn_fwd,
            self._btn_in,
            self._btn_out,
        ]:
            b.setFixedHeight(22)
            b.setMinimumWidth(26)
            tb_layout.addWidget(b)
        self._transport_bar.setLayout(tb_layout)
        layout.addWidget(self._transport_bar)
        self._transport_bar.setVisible(show_transport)
        self.setLayout(layout)
        # Wire legacy signals through
        try:
            self._timeline.positionChanged.connect(self.positionChanged.emit)
            self._timeline.seekRequested.connect(self.seekRequested.emit)
            self._timeline.inOutChanged.connect(self.inOutChanged.emit)
            # Proxy drag start/end signals for tests relying on them
            if hasattr(self._timeline, "dragStarted"):
                self._timeline.dragStarted.connect(self.dragStarted.emit)
            if hasattr(self._timeline, "dragEnded"):
                self._timeline.dragEnded.connect(self.dragEnded.emit)
        except Exception:
            pass
        # Button actions -> emit our own signals (controller/parent decides behavior)
        self._btn_back.clicked.connect(lambda: self.frameStep.emit(-1))
        self._btn_fwd.clicked.connect(lambda: self.frameStep.emit(1))
        self._btn_play.clicked.connect(self.playToggled.emit)
        self._btn_in.clicked.connect(self._onMarkIn)
        self._btn_out.clicked.connect(self._onMarkOut)

    # --- Public passthrough API ---
    def setClip(self, clip):  # attach MoviePy clip
        # Legacy tests expect setMedia; provide compatibility
        if hasattr(self._timeline, "setMedia"):
            self._timeline.setMedia(clip)

    def setPosition(self, t: float):
        return self._timeline.setPosition(t)

    # Legacy compatibility wrappers
    def setMedia(self, clip):  # direct forwarder (older code path)
        return self.setClip(clip)

    def setDuration(self, duration: float):
        if hasattr(self._timeline, "setDuration"):
            return self._timeline.setDuration(duration)

    def currentPosition(self) -> float:
        if hasattr(self._timeline, "currentPosition"):
            return self._timeline.currentPosition()
        return 0.0

    def enableThumbnails(self, enabled: bool):
        if hasattr(self._timeline, "thumbnail_strip"):
            self._timeline.thumbnail_strip.setVisible(
                enabled and bool(self._timeline.thumbnail_strip._pixmaps)
            )

    def enableWaveform(self, enabled: bool):
        if hasattr(self._timeline, "waveform"):
            self._timeline.waveform.setVisible(
                enabled and bool(getattr(self._timeline.waveform, "_amps", []))
            )

    # Marker helpers delegate
    def setInPoint(self):
        if hasattr(self._timeline, "setInPoint"):
            self._timeline.setInPoint()

    def setOutPoint(self):
        if hasattr(self._timeline, "setOutPoint"):
            self._timeline.setOutPoint()

    def clearInPoint(self):
        if hasattr(self._timeline, "clearInPoint"):
            self._timeline.clearInPoint()

    def clearOutPoint(self):
        if hasattr(self._timeline, "clearOutPoint"):
            self._timeline.clearOutPoint()

    def inOut(self):
        if hasattr(self._timeline, "inOut"):
            return self._timeline.inOut()
        return (None, None)

    # --- Internal button handlers ---
    def _onMarkIn(self):
        self.setInPoint()
        self.markInRequested.emit()

    def _onMarkOut(self):
        self.setOutPoint()
        self.markOutRequested.emit()

    # --- UI control ---
    def setTransportVisible(self, visible: bool):
        if self._transport_bar:
            self._transport_bar.setVisible(visible)

    def updatePlayButton(self, playing: bool):
        # Allow external controller to refresh icon
        try:
            self._btn_play.setText("❚❚" if playing else "▶")
        except Exception:
            pass


__all__ = ["ScrubberWidget"]
