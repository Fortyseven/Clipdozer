This project is designed to be a lightweight video editor to create short-form portrait video clips for social media.

## Features
### Now
- Save and load Clipdozer projects
- Trim and cut video clips
- Add music and sound effects
- Import media from local files (mp4, etc)
- Add text overlays and automatic (editable) captioning using Whisper
- Export to mp4


## Cross-Platform Technology Stack

To ensure Clipdozer is lightweight, easy to develop, and runs on Windows, macOS, and Linux, the recommended approach is:

- **Language:** Python — rapid development, huge ecosystem, proven in video editing.
- **Video Processing:** FFmpeg (via MoviePy, ffmpeg-python, or direct calls) — industry standard for video/audio manipulation.
- **UI Framework:** Qt (via PyQt or PySide) — mature, cross-platform desktop GUI.
- **Captioning:** OpenAI Whisper (Python) — state-of-the-art automatic speech-to-text.
- **Audio:** Pydub — simple audio editing.
- **Image/Frame Processing:** OpenCV (Python) — for advanced video/image operations.
- **Media Import (future):** yt-dlp — direct import from URLs.

**Why this stack?**
- All components are open source and cross-platform.
- Python enables rapid prototyping and easy integration of AI features.
- FFmpeg and Qt are industry standards for media and UI.
- This approach is used by successful open source editors (e.g., OpenShot, MoviePy).


- Import directly from provided URLs (using yt-dlp)
- Apply filters and effects
- Share directly to social media platforms

Use `uv` for managing packages and our virtual environment. (`uv add <package>` to add a package, `uv run <command>` to run a command within the virtual environment.) Do not use the system Python or pip directly.