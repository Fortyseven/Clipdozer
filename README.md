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
Clipdozer is migrating toward a layered package structure under `app/` to keep growth manageable:

```
app/
	core/        # Domain models & core timeline logic (ranges, formatting, orchestration)
	ui/          # Qt widgets & windows (MainWindow, dialogs, future editor panels)
	services/    # Long-running or async tasks (captioning via Whisper, import/export, render jobs)
	media/       # Abstractions around MoviePy / ffmpeg (decoding, waveform extraction, clip wrappers)
	utils/       # Small shared helpers (time formatting, threading utilities)
	timeline.py  # Backwards-compat shim; original TimelineWidget kept during transition
```

Current state:
* `TimelineWidget` still resides in `app.timeline` and is re-exported from `app.core.timeline` for forwards migration.
* New code should prefer `from app.core.timeline import TimelineWidget`.
* Tests continue using the legacy path to avoid churn until logic/widget separation is complete.
* `format_time` moved to `app.utils.timefmt` (legacy import still works through `app.timeline`).
* Thumbnail and waveform workers extracted to `app.services.media_generation` reducing widget coupling.
* NEW: `VideoPlaybackController` & `VideoPreviewWidget` (in `app.media.playback`) encapsulate playback. `MainWindow` now uses this abstraction instead of inline timers.

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

Migration path for existing code that previously called `MainWindow._showFrame` or manipulated playback indices:
1. Hold a reference to a `VideoPlaybackController`.
2. Call `controller.load(path_or_clip)` followed by `controller.play()` / `controller.pause()` / `controller.seek(t)`.
3. Listen to `frameReady` for updated frames.

This paves the way for a dual-viewer UI (source & program) or clip bins with hover scrubbing in later milestones.

Migration strategy:
1. Maintain backward compatibility while moving modules.
2. Introduce adapters/services in parallel with existing code paths.
3. Replace direct widget calls with service invocations + signal wiring.
4. Remove shim file (`timeline.py`) once all imports updated.


## Troubleshooting
* Error "FFmpeg not found": install ffmpeg and ensure `which ffmpeg` returns a path.
* Import error for `moviepy.editor`: you're on MoviePy 2.x; update imports to `from moviepy import VideoFileClip`.
* Playback stutters: performance tuning will come after initial feature completeness.
