"""Project model encapsulating an ordered list of clips and simple metadata.

In the future this will include tracks (video/audio/text), transitions, effects,
caption layers, etc. For now it's a minimal list of clip descriptors with basic
serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any
import json
from pathlib import Path


@dataclass
class ClipDescriptor:
    path: str  # original file path
    in_point: Optional[float] = None  # seconds
    out_point: Optional[float] = None  # seconds
    mute: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def duration_range(self) -> Optional[float]:
        if self.in_point is None or self.out_point is None:
            return None
        return max(0.0, self.out_point - self.in_point)


@dataclass
class Project:
    name: str = "Untitled"
    clips: List[ClipDescriptor] = field(default_factory=list)
    version: int = 1
    extra: dict[str, Any] = field(default_factory=dict)

    def add_clip(self, clip: ClipDescriptor) -> None:
        self.clips.append(clip)

    def remove_clip(self, index: int) -> ClipDescriptor:
        if index < 0 or index >= len(self.clips):
            raise IndexError("clip index out of range")
        return self.clips.pop(index)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        clips_data = data.get("clips", [])
        clips = [ClipDescriptor(**c) for c in clips_data]
        return cls(
            name=data.get("name", "Untitled"),
            clips=clips,
            version=data.get("version", 1),
            extra=data.get("extra", {}),
        )

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        p = Path(path)
        data = json.loads(p.read_text())
        return cls.from_dict(data)


__all__ = ["Project", "ClipDescriptor"]
