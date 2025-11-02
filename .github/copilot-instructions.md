# Clipdozer AI Coding Instructions

Concise guide for AI agents contributing to this repo. Focus on CURRENT patterns (not aspirational). Keep changes small, respect layering, and use `uv` for all Python commands.

## Core Goals & Architecture
- Purpose: Lightweight desktop editor for short-form portrait video clips (prototype stage).
- Layered under `app/`:
  - `core/`: Pure domain models (e.g. `project.Project`, `ClipDescriptor`). Avoid Qt here.
  - `media/`: Adapters around MoviePy/FFmpeg (`clip_adapter.ClipAdapter`, playback controller/widgets in `playback.py`). Thread-safe frame/audio access.
  - `services/`: Asynchronous/background generation (`media_generation.ThumbnailWorker`, `WaveformWorker`), future caption/export services.
  - `ui/`: Qt windows/widgets (`main_window.MainWindow`). Only place for direct widget creation & user interaction.
  - `utils/`: Small stateless helpers (`timefmt.format_time`).
  - `timeline.py`: Transitional legacy timeline widget (kept during migration). New code should import `TimelineWidget` via `app.timeline` until final relocation.

## Key Patterns
- Thread safety: Access clip frames/audio behind a mutex (`_external_mutex` attached in `ClipAdapter` and by `TimelineWidget.setMedia`). New background workers must lock this mutex when decoding.
- Asynchronous media generation: Use QThread + worker QObject pattern (signals: `finished`, `failed`) as in `ThumbnailWorker` / `WaveformWorker`. Emit generation id to discard stale results.
- Playback abstraction: UI interacts with `VideoPlaybackController` (signals: `frameReady`, `positionChanged`, `stateChanged`, `clipLoaded`). Do NOT reimplement frame timers in widgets; extend controller if needed.
- Time formatting: Always use `format_time(seconds)` for UI labels; it applies ROUND_HALF_UP rounding and negative clamping. Never reinvent formatting in widgets/tests.
- In/Out markers: Managed inside `TimelineWidget` with slider painting; modifications go through its public methods (`setInPoint`, `setOutPoint`, `clearInPoint`, `inOut()`). Avoid direct attribute mutation.
- Signals boundary: Services/media adapters return plain Python or emit simple Qt signals; UI layer converts to visuals (e.g. `VideoPreviewWidget`). Keep computation out of `MainWindow`.
- File separation: Keep each concept/component in its own file (e.g. playback controller vs preview widget, workers vs UI widgets). Avoid monolithic modules accumulating unrelated classes. If adding a new domain concept, place a focused file under the appropriate subpackage rather than expanding an existing one.

## Tests & Conventions
- Tests live in `tests/` (and a few legacy root-level test_* files still present). Use `pytest` via `uv run pytest`.
- Test style: Direct functional assertions (no heavy fixtures). Create temporary clips using `ColorClip` (see `tests/test_video_import.py`). Close clips explicitly to release file handles.
- Import paths: Tests may use legacy `from app.timeline import format_time` for backward compatibility; new tests can import `from app.utils.timefmt import format_time`.

## Working With Projects
- `Project` & `ClipDescriptor` are minimal JSON-serializable dataclasses (`save(path)`, `load(path)`). When extending, preserve backward-compatible fields and bump `version` only when format changes.

## Dependency & Runtime Management
- Use `uv` exclusively: `uv sync` to install, `uv add <pkg>` to add, `uv run python -m app.ui.main_window` or `uv run python main.py` to start.
- External requirement: ffmpeg must be on PATH. Avoid code that assumes its absence; show user-friendly warnings (`_ensureFFmpeg`).

## Adding Features
- Place pure logic in `core/` or `services/`; keep UI as thin signal wiring.
- For new background operations (e.g., captioning): create a worker in `services/` following existing generation id + interruption pattern; expose high-level method for UI to trigger.
- For export functionality: integrate with `services/export.py` (currently stub); avoid tying export directly to widget state—pass a `Project` plus source clips.

## Performance & Safety Notes
- Avoid decoding frames in loops without yielding to event loop—use controller or workers.
- When resizing timeline or regenerating thumbnails, ensure threads are interrupted quickly (`requestInterruption`, `quit`, `wait(50)` pattern).

## Common Pitfalls
- Recreating playback timers in `MainWindow` (use `VideoPlaybackController`).
- Directly accessing `VideoFileClip.get_frame` in UI threads without mutex (wrap with `ClipAdapter`).
- Adding logic to legacy `timeline.py` that should live in `services/media_generation.py` or `media/playback.py`.

## Example Integration Snippets
```python
# Load clip & start playback
controller = VideoPlaybackController()
controller.load("/path/to/video.mp4")
controller.play()

# Generate thumbnails in a new worker (pattern)
worker = ThumbnailWorker(clip, gen_id, 12, 50, width_hint)
thread = QThread(); worker.moveToThread(thread)
thread.started.connect(worker.run)
worker.finished.connect(lambda gen, imgs, times, dur: ...)
thread.start()
```

## When Unsure
Prefer extending existing abstractions rather than introducing parallel ones. Reference similar patterns before creating new modules. Keep instruction comments concise and colocated where behavior is non-obvious (e.g., mutex usage, generation id checks).
