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

Frame Skipping:
To maintain real-time playback under UI load, the controller can skip frames. When
``frame_skip`` is enabled (default for preview usage), each timer tick computes the
desired frame index from wall-clock elapsed time since play start. If decoding or
UI rendering lags, intermediate frames are dropped and playback jumps forward to
the desired index. This keeps audio/video sync closer and preserves perceptual
smoothness at the cost of not displaying every decoded frame. Disable via
``set_frame_skipping(False)`` for frame-exact stepping scenarios (e.g., export
or debugging).
"""

from __future__ import annotations

from typing import Optional, Union
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy
from PySide6.QtCore import QSize

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

    def __init__(
        self,
        parent: Optional[QObject] = None,
        *,
        frame_skip: bool = True,
        sync_threshold_frames: int = 2,
    ):
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
        # When enabled we may skip frames to keep real-time pace.
        self._frame_skip_enabled = frame_skip
        # Legacy threshold guard used for coarse drift correction if frame_skip disabled.
        self._sync_threshold_frames = sync_threshold_frames

    # Configuration API
    def set_frame_skipping(self, enabled: bool):
        """Enable or disable frame skipping during playback.

        When enabled, the controller uses wall-clock elapsed time to jump
        directly to the desired frame index, potentially dropping intermediate
        frames for smoother real-time preview.
        """
        self._frame_skip_enabled = enabled

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
        fps = self._state.fps or 24.0
        # Derive target frame using wall clock to keep pace; optionally skip frames.
        try:
            from time import perf_counter

            target_index = self._state.current_frame + 1  # default linear advance
            if self._play_start_time is not None:
                elapsed = perf_counter() - self._play_start_time
                desired = int(elapsed * fps)
                if self._frame_skip_enabled:
                    # Jump directly to desired frame if ahead of linear progression.
                    if desired > self._state.current_frame:
                        target_index = desired
                else:
                    # Only coarse resync if far behind.
                    if (
                        desired - self._state.current_frame
                        > self._sync_threshold_frames
                    ):
                        target_index = desired
            if target_index >= self._state.total_frames:
                self.stop()
                return
            self._state.current_frame = target_index
        except Exception:
            # Fallback linear advance if timing fails.
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
        # Cache last raw frame so we can rescale on widget resize without waiting
        # for the next decoded frame.
        self._last_frame = None
        # Scaling mode: 'smooth' uses Qt.SmoothTransformation, 'fast' uses Qt.FastTransformation.
        self._scaling_mode = "fast"
        # --- Scaling / size policy notes ---
        # Bug fix: Previously the preview would upscale to fill available space but
        # refuse to shrink when the window/layout contracted. This occurred because
        # QLabel's default size policy uses the pixmap dimensions as a preferred
        # size hint; once a large QPixmap is set, layouts will not shrink the label
        # below that size. By marking both dimensions as Ignored we allow the layout
        # to freely resize the widget smaller, and our resizeEvent will rescale the
        # cached frame appropriately.
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    def sizeHint(self):  # type: ignore[override]
        """Return a modest default hint independent of last pixmap size.

        Using a fixed small hint prevents the previous large frame from locking
        the layout into a large minimum. The layout may still expand the widget,
        but it can now contract freely.
        """
        return QSize(160, 90)

    def setScalingMode(self, mode: str):
        """Set scaling mode: 'smooth' (default) or 'fast'."""
        if mode in ("smooth", "fast"):
            self._scaling_mode = mode

    # --- Rendering helpers ---
    def _renderFrame(self):
        """Scale and display the cached frame to current widget size preserving aspect."""
        frame = self._last_frame
        if frame is None:
            return
        try:
            import numpy as np
            from PySide6.QtGui import QImage

            if frame.ndim == 2:  # grayscale -> expand to RGB for consistency
                frame = np.stack([frame] * 3, axis=-1)
            h, w = frame.shape[0], frame.shape[1]
            target_w = self.width()
            target_h = self.height()
            if target_w <= 0 or target_h <= 0:
                return
            aspect = w / h if h else 1.0
            if target_w / target_h > aspect:
                new_h = target_h
                new_w = int(new_h * aspect)
            else:
                new_w = target_w
                new_h = int(new_w / aspect) if aspect else target_h
            # Construct QImage directly from numpy buffer (assumed uint8 RGB)
            # Each row is w * 3 bytes.
            bytes_per_line = w * 3
            qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            transform_flag = (
                Qt.SmoothTransformation
                if self._scaling_mode == "smooth"
                else Qt.FastTransformation
            )
            scaled = qimg.scaled(new_w, new_h, Qt.KeepAspectRatio, transform_flag)
            pix = QPixmap.fromImage(scaled)
            self.setPixmap(pix)
            self.setText("")
        except Exception as e:  # pragma: no cover
            self.setText(f"Frame err: {e}")

    def _onFrame(self, frame, t: float):  # frame is numpy array
        if frame is None:
            return
        # Cache and render
        self._last_frame = frame
        self._renderFrame()

    # --- Resize behavior ---
    def resizeEvent(self, event):  # noqa: D401 - Qt override
        # Re-scale cached frame to new size.
        self._renderFrame()
        super().resizeEvent(event)


__all__ = ["VideoPlaybackController", "VideoPreviewWidget"]
