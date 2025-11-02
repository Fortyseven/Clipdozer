"""Thread-safe adapter around MoviePy VideoFileClip providing simplified access.

Encapsulates mutex locking strategy so UI/services can call without duplicating code.
"""

from __future__ import annotations


try:
    from moviepy import VideoFileClip
except ImportError:  # pragma: no cover
    try:
        from moviepy.editor import VideoFileClip  # type: ignore
    except ImportError:  # pragma: no cover
        VideoFileClip = None  # type: ignore

from PySide6.QtCore import QMutex


class ClipAdapter:
    def __init__(self, clip):
        self._clip = clip
        self._mutex = QMutex()
        # Attach mutex to underlying clip for legacy workers if needed
        try:
            setattr(self._clip, "_external_mutex", self._mutex)
        except Exception:  # pragma: no cover
            pass

    @property
    def clip(self):
        return self._clip

    @property
    def duration(self) -> float:
        return float(getattr(self._clip, "duration", 0.0))

    @property
    def fps(self) -> float:
        return float(getattr(self._clip, "fps", 0.0))

    def get_frame(self, t: float):
        self._mutex.lock()
        try:
            return self._clip.get_frame(t)
        finally:
            self._mutex.unlock()

    def audio_array(self, fps: int = 200):
        audio = getattr(self._clip, "audio", None)
        if audio is None:
            return None
        self._mutex.lock()
        try:
            return audio.to_soundarray(fps=fps)
        finally:
            self._mutex.unlock()

    @classmethod
    def from_path(cls, path: str) -> "ClipAdapter":
        if VideoFileClip is None:
            raise RuntimeError("MoviePy not available")
        clip = VideoFileClip(path)
        return cls(clip)

    @classmethod
    def from_clip(cls, clip) -> "ClipAdapter":
        return cls(clip)


__all__ = ["ClipAdapter"]
