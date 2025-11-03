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


try:
    from ...timeline import TimelineWidget as _LegacyTimelineWidget
except Exception as e:  # pragma: no cover
    raise RuntimeError(f"Failed to import legacy timeline: {e}")


class ScrubberWidget(_LegacyTimelineWidget):
    """Terminology-aligned wrapper around legacy `TimelineWidget`.

    For now we simply subclass; future iterations will relocate internals here.
    """

    def setClip(self, clip):
        """Attach a MoviePy clip (VideoFileClip) to display duration, thumbnails & waveform."""
        self.setMedia(clip)

    # Alias legacy naming for clarity in new code
    def setPosition(self, t: float):  # provided by TimelineWidget as setPosition
        return super().setPosition(t)

    # Additional helper for future configuration toggles
    def enableThumbnails(self, enabled: bool):
        if hasattr(self, "thumbnail_strip"):
            self.thumbnail_strip.setVisible(
                enabled and bool(self.thumbnail_strip._pixmaps)
            )

    def enableWaveform(self, enabled: bool):
        if hasattr(self, "waveform"):
            self.waveform.setVisible(
                enabled and bool(getattr(self.waveform, "_amps", []))
            )


__all__ = ["ScrubberWidget"]
