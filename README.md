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

## Testing Video Import
Run the synthetic clip test:
```bash
uv run python test_video_import.py
```

## Roadmap (short-term)
* Timeline editing (trim/cut operations)
* In/Out point marking & range-based operations
* Audio track integration
* Whisper-based caption generation
* Project save/load

## Troubleshooting
* Error "FFmpeg not found": install ffmpeg and ensure `which ffmpeg` returns a path.
* Import error for `moviepy.editor`: you're on MoviePy 2.x; update imports to `from moviepy import VideoFileClip`.
* Playback stutters: performance tuning will come after initial feature completeness.
