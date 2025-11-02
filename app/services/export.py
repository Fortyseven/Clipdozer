"""Export pipeline scaffold.

Future responsibilities:
 - Assemble timeline (respect in/out points, ordering, transitions)
 - Apply caption overlays and simple effects
 - Invoke ffmpeg (via MoviePy or direct subprocess) to render final mp4
 - Provide progress callbacks/signals for UI
 - Support different presets (social media aspect ratios, bitrate targets)
"""

from __future__ import annotations

from typing import Callable, Optional
from pathlib import Path

from ..core.project import Project

ProgressCallback = Callable[[float], None]  # 0.0 - 1.0


class ExportSettings:
    def __init__(
        self,
        fps: int = 30,
        preset: str = "social-default",
        width: int | None = None,
        height: int | None = None,
    ):
        self.fps = fps
        self.preset = preset
        self.width = width
        self.height = height


def export_project(
    project: Project,
    output_path: str | Path,
    settings: ExportSettings | None = None,
    progress: Optional[ProgressCallback] = None,
) -> None:
    """Stub: export project to a video file.

    Parameters
    ----------
    project: Project to render.
    output_path: Destination file path.
    settings: ExportSettings controlling fps and basic dimensions.
    progress: Optional callback receiving progress fraction.
    """
    # Future implementation will iterate clips, apply trims (in/out), concatenate.
    # For now just signal immediate completion.
    if progress:
        progress(1.0)
    # Placeholder: write a tiny marker file to show invocation occurred (not a real video)
    p = Path(output_path)
    p.write_text("EXPORT PLACEHOLDER")


__all__ = ["ExportSettings", "export_project"]
