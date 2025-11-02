"""Main application window (UI layer).

Moved from app.main to app.ui.main_window for clearer layering.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QStatusBar,
)
from PySide6.QtGui import QAction, QShortcut, QKeySequence
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
import os
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

try:
    from moviepy import VideoFileClip
except ImportError:  # pragma: no cover
    try:
        from moviepy.editor import VideoFileClip  # type: ignore
    except ImportError as _e:  # pragma: no cover
        VideoFileClip = None  # type: ignore
        _moviepy_import_error = _e


from ..media.playback import VideoPlaybackController, VideoPreviewWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clipdozer")
        self.setGeometry(100, 100, 800, 600)
        self._createMenuBar()
        self._createEditorLayout()
        self._initAudio()
        # Defer centering until window has geometry (will also be called in run())

    def centerOnPreferredScreen(self):
        """Center the window on the selected screen.

        Selection priority:
        1. Environment variable CLIPDOZER_SCREEN_INDEX if valid.
        2. Primary screen.
        """
        try:
            screens = QGuiApplication.screens()
            if not screens:
                return
            idx_env = os.getenv("CLIPDOZER_SCREEN_INDEX")
            screen = None
            if idx_env is not None:
                try:
                    idx = int(idx_env)
                    if 0 <= idx < len(screens):
                        screen = screens[idx]
                except Exception:
                    screen = None
            if screen is None:
                screen = QGuiApplication.primaryScreen() or screens[0]
            if screen is None:
                return
            geo = screen.availableGeometry()
            win_geo = self.frameGeometry()
            win_geo.moveCenter(geo.center())
            self.move(win_geo.topLeft())
        except Exception:
            pass

    def _createMenuBar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        import_action = QAction("Import Media", self)
        import_action.triggered.connect(self._importMedia)
        file_menu.addAction(import_action)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        about_menu = menu_bar.addMenu("About")
        about_action = QAction("About Clipdozer", self)
        about_action.triggered.connect(self._showAboutDialog)
        about_menu.addAction(about_action)

    def _showAboutDialog(self):
        QMessageBox.about(
            self,
            "About Clipdozer",
            "Clipdozer\nLightweight video editor for social media clips.",
        )

    def _importMedia(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Media", "", "Video Files (*.mp4 *.mov *.avi)"
        )
        if not file_path:
            return
        self.loadMediaPath(file_path)

    def loadMediaPath(self, file_path: str):
        """Programmatic media load (used by _importMedia and potential future drag-drop)."""
        try:
            if VideoFileClip is None:
                raise RuntimeError(f"moviepy import failed: {_moviepy_import_error}")
            # Load clip for timeline thumbnails separately (legacy path) while playback uses controller
            self.clip = VideoFileClip(file_path)
            self.controller.load(self.clip)
            self.timeline.addItem(f"Imported: {file_path.split('/')[-1]}")
            if hasattr(self, "scrub") and self.scrub is not None:
                try:
                    self.scrub.setMedia(self.clip)
                except Exception as e:
                    print(f"Failed to set media on timeline: {e}")
                self.scrub.setPosition(0.0)
            if hasattr(self, "media_player"):
                self._loadAudio(file_path)
                try:
                    self.media_player.setPosition(0)
                except Exception:
                    pass
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load video: {e}")

    def _createEditorLayout(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        self.controller = VideoPlaybackController(self)
        self.video_preview = VideoPreviewWidget(self.controller)
        self.video_preview.setFixedHeight(300)
        main_layout.addWidget(self.video_preview)
        try:
            from ..timeline import TimelineWidget

            self.scrub = TimelineWidget()
            main_layout.addWidget(self.scrub)
        except Exception as e:
            self.scrub = None
            print(f"TimelineWidget unavailable: {e}")
        self.timeline = QListWidget()
        self.timeline.addItem("Clip 1")
        self.timeline.addItem("Clip 2")
        main_layout.addWidget(self.timeline)
        controls_layout = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.trim_btn = QPushButton("Trim")
        self.cut_btn = QPushButton("Cut")
        controls_layout.addWidget(self.play_btn)
        controls_layout.addWidget(self.pause_btn)
        controls_layout.addWidget(self.trim_btn)
        controls_layout.addWidget(self.cut_btn)
        main_layout.addLayout(controls_layout)
        self.play_btn.clicked.connect(self.controller.play)
        self.pause_btn.clicked.connect(self.controller.pause)
        self.clip = None
        if self.scrub is not None:
            # Preview seek while dragging (no audio reposition until release)
            self.scrub.positionChanged.connect(lambda t: self.controller.seek(t))
            # Commit seek when user releases slider
            self.scrub.seekRequested.connect(self._commitScrubSeek)
            # New bidirectional sync: pause playback during user drag & resume
            try:
                self.scrub.dragStarted.connect(self._onScrubDragStarted)
                self.scrub.dragEnded.connect(self._onScrubDragEnded)
            except Exception:
                pass
            self.scrub.inOutChanged.connect(self._inOutChanged)
            try:
                self.scrub.thumbnailsBusy.connect(self._onThumbsBusy)
            except Exception:
                pass
            QShortcut(QKeySequence("I"), self, activated=self.scrub.setInPoint)
            QShortcut(QKeySequence("O"), self, activated=self.scrub.setOutPoint)
            QShortcut(QKeySequence("Shift+I"), self, activated=self.scrub.clearInPoint)
            QShortcut(QKeySequence("Shift+O"), self, activated=self.scrub.clearOutPoint)
            # Keep timeline position updating during playback
            self.controller.positionChanged.connect(self.scrub.setPosition)
        # Audio state & drift synchronization
        self.controller.stateChanged.connect(self._onPlaybackState)
        self.controller.positionChanged.connect(self._maybeResyncAudio)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def _initAudio(self):
        try:
            self.audio_output = QAudioOutput(self)
            self.media_player = QMediaPlayer(self)
            self.media_player.setAudioOutput(self.audio_output)
            self.audio_output.setVolume(0.8)
        except Exception as e:
            print(f"Audio init failed: {e}")

    def _loadAudio(self, file_path: str):
        try:
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            self.media_player.setPosition(0)
        except Exception as e:
            print(f"Audio load failed: {e}")

    def _ensureFFmpeg(self):
        import shutil

        if shutil.which("ffmpeg") is None:
            QMessageBox.warning(
                self,
                "FFmpeg Missing",
                "FFmpeg not found in PATH. Please install ffmpeg to enable video decoding.",
            )

    def _showFrame(self, t_or_index):
        # Legacy call path kept for potential external uses; now proxies to controller.seek
        if self.clip is None:
            return
        if isinstance(t_or_index, int) and self.clip is not None:
            t = t_or_index / self.clip.fps
        else:
            t = float(t_or_index)
        self.controller.seek(t)

    def _onThumbsBusy(self, busy: bool):
        if busy:
            # Pause controller during heavy thumbnail generation to free decoding resources
            if (
                getattr(self.controller, "_state", None)
                and self.controller._state.playing
            ):  # type: ignore[attr-defined]
                self._was_playing_before_thumbs = True
                self.controller.pause()
            else:
                self._was_playing_before_thumbs = False
        else:
            if getattr(self, "_was_playing_before_thumbs", False):
                self.controller.play()

    def _previewSeek(self, t: float):  # kept for potential legacy slots
        if self.clip is None:
            return
        self.controller.seek(t)

    def _commitSeek(self, t: float):  # kept for potential legacy slots
        if self.clip is None:
            return
        self.controller.seek(t)
        if hasattr(self, "media_player") and self.media_player.source().isLocalFile():
            self.media_player.setPosition(int(t * 1000))

    def _commitScrubSeek(self, t: float):
        self._commitSeek(t)

    def _onScrubDragStarted(self):
        # Record if we should resume after drag
        self._resume_after_drag = False
        if getattr(self.controller, "_state", None) and self.controller._state.playing:  # type: ignore[attr-defined]
            self._resume_after_drag = True
            self.controller.pause()
        # Also pause audio explicitly if playing
        if (
            hasattr(self, "media_player")
            and self.media_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            self.media_player.pause()

    def _onScrubDragEnded(self):
        # Resume playback if it was playing before drag; audio seek handled in commit seek
        if getattr(self, "_resume_after_drag", False):
            self.controller.play()

    # --- Audio / controller synchronization ---
    def _onPlaybackState(self, state: str):
        if not hasattr(self, "media_player"):
            return
        mp = self.media_player
        if not mp.source().isLocalFile():
            return
        if state == "playing":
            try:
                mp.setPosition(int(self.controller.position() * 1000))
            except Exception:
                pass
            mp.play()
        elif state in ("paused", "stopped"):
            mp.pause()
            if state == "stopped":
                try:
                    mp.setPosition(0)
                except Exception:
                    pass

    def _maybeResyncAudio(self, t: float):
        if not hasattr(self, "media_player"):
            return
        mp = self.media_player
        if mp.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            return
        try:
            audio_ms = mp.position()
            video_ms = int(t * 1000)
            if abs(audio_ms - video_ms) > 120:  # >120ms drift -> correct
                mp.setPosition(video_ms)
        except Exception:
            pass

    def _inOutChanged(self, in_t, out_t):
        if not self.statusBar():
            self.setStatusBar(QStatusBar())  # type: ignore
        if in_t is None and out_t is None:
            self.statusBar().showMessage("")
        else:
            try:
                from ..timeline import format_time

                in_s = format_time(in_t) if in_t is not None else "--"
                out_s = format_time(out_t) if out_t is not None else "--"
                self.statusBar().showMessage(f"Selection: {in_s} to {out_s}")
            except Exception:
                pass


def run():  # convenience launcher
    app = QApplication(sys.argv)
    window = MainWindow()
    window._ensureFFmpeg()
    window.show()
    window.centerOnPreferredScreen()
    sys.exit(app.exec())


__all__ = ["MainWindow", "run"]
