Clipdozer
=========

Lightweight desktop editor for short-form portrait video clips.

## Features (early prototype)
* Import local video files (mp4, mov, avi)
* Preview first frame and basic playback (Play/Pause) using MoviePy 2.x
* Aspect-ratio aware scaling in preview
* Scrub bar for random access seeking
* In/Out point marking (context menu on scrub bar or use shortcuts I / O, shift+I / shift+O to clear)
* Visual timeline with highlighted In/Out region and generated frame thumbnails (auto on import)
	* Thumbnails now generated asynchronously; they will refine shortly after import.
	* Resizing the window triggers a debounced regeneration sized to available width.
* Audio playback synchronized with video scrubbing (basic play/pause/seek, looping)

## Requirements
* Python 3.11+
* ffmpeg available on your PATH (required by MoviePy)
* `uv` for dependency & virtual environment management (https://github.com/astral-sh/uv)

Install ffmpeg (Linux example):
```bash
sudo apt update && sudo apt install -y ffmpeg
```

## Setup & Run (with uv)
```bash
# Sync dependencies
uv sync

# Run the application
uv run python main.py
```

While running:
* Press I to set the In point at current playhead.
* Press O to set the Out point.
* Shift+I / Shift+O clear respective markers.
* Right-click the scrub bar for a context menu offering the same actions.
* Resizing the window will regenerate timeline thumbnails after a short delay.

## MoviePy 2.x Import Change
MoviePy 2.x removed the legacy aggregator module `moviepy.editor`. Import core classes directly:
```python
from moviepy import VideoFileClip
```
Code contains a fallback for older environments.

## Running Tests
All tests live under `tests/`.

Run the full suite:
```bash
uv run pytest -q
```

Run a single test file (example):
```bash
uv run pytest tests/test_video_import.py -q
```

Previous ad-hoc root-level test scripts have been consolidated into the suite.

## Roadmap (short-term)
* Timeline editing (trim/cut operations)
* In/Out point marking & range-based operations
* Audio track integration
* Whisper-based caption generation
* Project save/load

## Architecture Overview
Clipdozer uses a layered package structure under `app/`:

```
app/
	core/        # Domain models & core timeline logic (ranges, formatting, orchestration)
	ui/          # Qt widgets & windows (MainWindow, dialogs, future editor panels)
		components/  # Reusable UI components (buttons, sliders, etc.)
		components/scrubber.py  # ScrubberWidget implementation
	services/    # Long-running or async tasks (captioning via Whisper, import/export, render jobs)
	media/       # Abstractions around MoviePy / ffmpeg (decoding, waveform extraction, clip wrappers)
	utils/       # Small shared helpers (time formatting, threading utilities)
```

Key components:
* `ScrubberWidget` (`app/ui/components/scrubber.py`) – navigation, markers, thumbnails, waveform.
* `ClipPreviewPanel` / `ProjectPreviewPanel` – composed preview + scrubber containers.
* `VideoPlaybackController` & `VideoPreviewWidget` – playback abstraction and frame display.
* `format_time` utility – canonical time formatting in `app/utils/timefmt.py`.
* Thumbnail & waveform workers – async generation (`app/services/media_generation.py`).

Planned refactors:
* Extract pure formatting (`format_time`) into `app.utils.timefmt` (kept exported for convenience).
* Separate thumbnail & waveform generation into service classes (so UI becomes a thin view + signals).
* Introduce a `Project` model in `app.core` encapsulating clips, tracks, and metadata for save/load.
* Add a rendering pipeline service coordinating ffmpeg export.

New modules added:
* `app/core/project.py` – minimal `Project` and `ClipDescriptor` dataclasses with JSON save/load.
* `app/media/clip_adapter.py` – thread-safe wrapper around MoviePy `VideoFileClip` (mutex + convenience APIs).
* `app/services/captions.py` – caption generation scaffold (Whisper integration planned).
* `app/services/export.py` – export pipeline stub with settings and placeholder implementation.
* `app/ui/main_window.py` – relocated `MainWindow` (UI layer separation from legacy entrypoint `app/main.py`).

Design principles:
* Keep Qt specifics isolated in `ui/` so future headless operations (CLI batch export) can reuse core/services.
* Avoid hard coupling MoviePy objects to widgets—wrap them in media adapters providing thread-safe access.
* Use signals only at the UI boundary; internal services return plain Python data structures.
* Centralize video playback logic so multiple simultaneous clips (future multi-track, source vs timeline viewer) can share a uniform API.

### Playback Abstraction
The new `VideoPlaybackController` separates raw frame decoding & state (play/pause/seek) from any specific UI widget. It emits:

```
frameReady(np.ndarray, t_seconds)
positionChanged(t_seconds)
stateChanged(str)  # playing|paused|stopped
clipLoaded(duration_seconds)
```

`VideoPreviewWidget` is a thin QLabel-based consumer converting frames to a scaled `QPixmap`. Other components (future scopes, filters preview, export thumbnails) can subscribe directly to `frameReady` without depending on UI code in `MainWindow`.

Usage recap:
1. Create a `VideoPlaybackController` and load media.
2. `ClipPreviewPanel` handles wiring of preview + scrubber automatically.
3. Listen to `frameReady` for raw frames (numpy arrays) if you need custom rendering.

## Current UI Layout (Work in Progress)
The main window uses a split-pane layout preparing for multi-track editing:

Top (three horizontal panes):
1. Clip Bin – list of imported clips (select to load into clip preview).
2. Clip Preview – playback controls + its own dedicated clip scrubber (with I/O shortcuts).
3. Project Preview – currently blank (no media) with placeholder label; will render composite timeline output later.

Bottom:
Project scrubber (independent from the clip scrub) plus a multi-track placeholder area where track lanes will appear.

Behavior:
* Importing media loads only the Clip Preview and its scrubber.
* Project preview and project scrubber remain idle (duration zero) until project assembly logic is implemented.
* In/Out shortcuts (I/O and Shift+I / Shift+O) operate on the clip scrubber only.
* Clip Scrubber and Project Scrubber are visually labeled; seeking one does not change the other's position.
* A test (`tests/test_dual_scrub_independence.py`) asserts that clip scrub movement leaves project scrub at 0 when project is blank.

This scaffolding separates source clip manipulation from future project-level timeline editing.

## Terminology Alignment (Preview Panels & Scrubber)

To standardize language moving forward the UI adopts these concepts:

* Scrubber: Reusable widget for navigating a clip or project output (playhead slider, time labels) with optional In/Out markers, frame thumbnails, and waveform visualization. Implemented by `ScrubberWidget`.
* Clip Preview Panel: A container combining a `VideoPlaybackController`, a `VideoPreviewWidget`, and a `ScrubberWidget` with thumbnails + waveform enabled. Class: `ClipPreviewPanel` in `app/ui/components/preview_panel.py`.
* Project Preview Panel: Same structure but thumbnails + waveform disabled until project composition exists. Class: `ProjectPreviewPanel`.

Guidelines:
1. Use preview panels; do not manually assemble controller + preview + scrubber.
2. Keep non-UI logic out of widgets—use services and core models.
3. Prefer `format_time` for displaying timestamps consistently.

Example usage:
```python
from app.ui.components.preview_panel import ClipPreviewPanel

panel = ClipPreviewPanel()
panel.load("/path/to/video.mp4")
panel.controller.play()
```

This terminology will be used in future documentation, tests, and code reviews.

## Future Refactor Steps

Planned improvements:
1. Move thumbnail & waveform generation orchestration out of `ScrubberWidget`.
2. Introduce `ScrubberConfig` dataclass for feature toggles.
3. Implement project composition pipeline feeding `ProjectPreviewPanel`.
4. Add caption overlay rendering in preview panels.
5. Consolidate playback timing logic for off-GUI decoding.
6. Expand tests for preview panel behavior and configuration.


## Troubleshooting
* Error "FFmpeg not found": install ffmpeg and ensure `which ffmpeg` returns a path.
* Import error for `moviepy.editor`: you're on MoviePy 2.x; update imports to `from moviepy import VideoFileClip`.
* Playback stutters: performance tuning will come after initial feature completeness.
