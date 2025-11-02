"""Caption generation service scaffold using Whisper (future implementation).

This module defines a data structure for caption entries and a stub function for
caption generation. Real implementation will:
 - Load Whisper model lazily (tiny/base by default configurable)
 - Chunk audio for long clips
 - Perform language detection / translation optionally
 - Return time-aligned caption segments
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CaptionSegment:
    start: float
    end: float
    text: str
    confidence: Optional[float] = None


@dataclass
class CaptionResult:
    segments: List[CaptionSegment]
    language: str | None = None


def generate_captions(path: str, model_size: str = "base") -> CaptionResult:
    """Stub caption generation.

    Parameters
    ----------
    path: Path to media file.
    model_size: Whisper model size identifier.

    Returns
    -------
    CaptionResult with empty segments (placeholder).
    """
    # Future: integrate openai/whisper or faster-whisper library.
    return CaptionResult(segments=[], language=None)


__all__ = ["CaptionSegment", "CaptionResult", "generate_captions"]
