"""Reusable video playback controller & preview widget.

Goals:
- Abstract playback (play/pause/seek) from MainWindow so multiple clips can be controlled.
- Provide frame-ready signal with numpy frame for any consumer (preview widget, waveform gen, etc.).
- Keep MoviePy access threaded via QTimer on GUI thread with mutex protected ClipAdapter.

Design:
VideoPlaybackController wraps a ClipAdapter (or raw MoviePy clip) and exposes:
    load(clip_or_path)
    play()
    pause()
    seek(seconds)
    set_in_out(in_point, out_point)
    position() -> float
Signals:
    frameReady(np.ndarray, float)   # frame array + timestamp seconds
    positionChanged(float)          # updated during playback or seek
    stateChanged(str)               # 'stopped'|'playing'|'paused'
    clipLoaded(float)               # duration

The controller does NOT scale/convert to QPixmap to stay decoupled from Qt GUI specifics.
An optional VideoPreviewWidget listens to frameReady and converts to QPixmap.

Threading: We keep a precise QTimer loop (interval derived from fps) similar to previous logic; we
monitor wall clock elapsed to reduce drift. Future improvement: move to a dedicated worker thread.
"""

from __future__ import annotations

from typing import Optional, Union
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

try:  # MoviePy import compat
    from moviepy import VideoFileClip
except ImportError:  # pragma: no cover
    try:
        from moviepy.editor import VideoFileClip  # type: ignore
    except ImportError:  # pragma: no cover
        VideoFileClip = None  # type: ignore

from .clip_adapter import ClipAdapter


@dataclass
class PlaybackState:
    playing: bool = False
    current_frame: int = 0
    total_frames: int = 0
    duration: float = 0.0
    fps: float = 0.0


class VideoPlaybackController(QObject):
    frameReady = Signal(object, float)  # (numpy array, t seconds)
    positionChanged = Signal(float)
    stateChanged = Signal(str)
    clipLoaded = Signal(float)  # duration

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._clip_adapter: Optional[ClipAdapter] = None
        self._state = PlaybackState()
        self._timer = QTimer(self)
        try:
            self._timer.setTimerType(Qt.PreciseTimer)  # type: ignore[attr-defined]
        except Exception:
            pass
        self._timer.timeout.connect(self._tick)
        self._play_start_time: Optional[float] = None
        self._sync_threshold_frames = 2

    # Public API
    def load(self, source: Union[str, ClipAdapter, "VideoFileClip"]):
        if isinstance(source, str):
            if VideoFileClip is None:
                raise RuntimeError("MoviePy not available for loading path")
            clip = VideoFileClip(source)
            adapter = ClipAdapter.from_clip(clip)
        elif isinstance(source, ClipAdapter):
            adapter = source
        else:
            adapter = ClipAdapter.from_clip(source)
        self._clip_adapter = adapter
        fps = adapter.fps or 24.0
        duration = adapter.duration
        total_frames = int(round(fps * duration)) if duration > 0 else 0
        self._state = PlaybackState(
            playing=False,
            current_frame=0,
            total_frames=total_frames,
            duration=duration,
            fps=fps,
        )
        self.clipLoaded.emit(duration)
        self.stateChanged.emit("stopped")
        # Emit first frame lazily on demand (seek(0))
        self.seek(0.0, emit_frame=True)

    def play(self):
        if not self._clip_adapter:
            return
        if self._state.current_frame >= self._state.total_frames - 1:
            self._state.current_frame = 0
        interval_ms = int(1000 / (self._state.fps or 24.0))
        if not self._timer.isActive():
            from time import perf_counter

            self._play_start_time = perf_counter() - (
                self._state.current_frame / (self._state.fps or 24.0)
            )
            self._timer.start(interval_ms)
        self._state.playing = True
        self.stateChanged.emit("playing")

    def pause(self):
        if self._timer.isActive():
            self._timer.stop()
        self._state.playing = False
        self.stateChanged.emit("paused")

    def stop(self):
        self.pause()
        self.seek(0.0)
        self.stateChanged.emit("stopped")

    def seek(self, t: float, emit_frame: bool = True):
        if not self._clip_adapter:
            return
        fps = self._state.fps or 24.0
        frame_index = int(max(0, min(int(t * fps), self._state.total_frames - 1)))
        self._state.current_frame = frame_index
        if emit_frame:
            self._emit_current_frame()
        self.positionChanged.emit(self.position())

    def position(self) -> float:
        if not self._clip_adapter or self._state.total_frames <= 0:
            return 0.0
        return self._state.current_frame / (self._state.fps or 24.0)

    # Internal
    def _emit_current_frame(self):
        if not self._clip_adapter:
            return
        t = self.position()
        array = self._clip_adapter.get_frame(t)
        self.frameReady.emit(array, t)

    def _tick(self):
        if not self._clip_adapter:
            self._timer.stop()
            return
        next_index = self._state.current_frame + 1
        if next_index >= self._state.total_frames:
            self.stop()
            return
        self._state.current_frame = next_index
        self._emit_current_frame()
        self.positionChanged.emit(self.position())


class VideoPreviewWidget(QLabel):
    """Simple QLabel-based preview that listens to a controller."""

    def __init__(self, controller: VideoPlaybackController, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#222;color:#fff;font-size:24px;")
        controller.frameReady.connect(self._onFrame)

    def _onFrame(self, frame, t: float):  # frame is numpy array
        try:
            from PIL import Image
            from io import BytesIO

            if frame is None:
                return
            h, w = frame.shape[0], frame.shape[1]
            image = Image.fromarray(frame).convert("RGB")
            target_w = self.width()
            target_h = self.height()
            if target_w <= 0 or target_h <= 0:
                return
            aspect = w / h
            if target_w / target_h > aspect:
                new_h = target_h
                new_w = int(new_h * aspect)
            else:
                new_w = target_w
                new_h = int(new_w / aspect)
            image = image.resize((new_w, new_h))
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            pix = QPixmap()
            pix.loadFromData(buffer.read())
            self.setPixmap(pix)
            self.setText("")
        except Exception as e:  # pragma: no cover
            self.setText(f"Frame err: {e}")


__all__ = ["VideoPlaybackController", "VideoPreviewWidget"]
