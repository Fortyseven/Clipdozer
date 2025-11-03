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
    QListWidget,
    QMessageBox,
    QFileDialog,
    QStatusBar,
    QSplitter,
    QLabel,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import QUrl, Qt
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


from ..media.playback import VideoPreviewWidget
from .components.preview_panel import ClipPreviewPanel, ProjectPreviewPanel


class ProjectPreviewWidget(VideoPreviewWidget):
    """Preview representing future composed project output.

    Currently mirrors clip selection conceptually; real composition rendering
    will replace this placeholder.
    """

    pass


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
        # Add to clip bin mapping
        base = os.path.basename(file_path)
        display = f"{base}"
        self._imported_clips[display] = file_path
        # Avoid duplicate entries
        if not any(
            self.clip_bin.item(i).text() == display
            for i in range(self.clip_bin.count())
        ):
            self.clip_bin.addItem(display)

    def loadMediaPath(self, file_path: str):
        """Programmatic media load (used by _importMedia and potential future drag-drop)."""
        try:
            if VideoFileClip is None:
                raise RuntimeError(f"moviepy import failed: {_moviepy_import_error}")
            # Load clip and register in clip bin
            self.clip = VideoFileClip(file_path)
            self.clip_controller.load(self.clip)
            self.clip_bin.addItem(f"Imported: {file_path.split('/')[-1]}")
            if getattr(self, "clip_scrub", None) is not None:
                try:
                    self.clip_scrub.setMedia(self.clip)
                    self.clip_scrub.setPosition(0.0)
                except Exception as e:
                    print(f"Failed to set media on clip scrub: {e}")
            if hasattr(self, "media_player"):
                self._loadAudio(file_path)
                try:
                    self.media_player.setPosition(0)
                except Exception:
                    pass
            # Project controller stays blank until composition implemented.
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load video: {e}")

    def _createEditorLayout(self):
        """Create new multi-pane editor layout.

        Layout hierarchy:
        +---------------------------------------------------------------+
        | Clip Bin | Clip Preview | Project Preview (future composite) |
        +---------------------------------------------------------------+
        |                Multi-Track Timeline Placeholder               |
        +---------------------------------------------------------------+
        """
        central_widget = QWidget()
        root_layout = QVBoxLayout()

        # Top splitter with three panes
        top_splitter = QSplitter()
        top_splitter.setOrientation(Qt.Horizontal)  # type: ignore

        # --- Clip Bin (left) ---
        self.clip_bin = QListWidget()
        self.clip_bin.setSelectionMode(QListWidget.SingleSelection)
        self.clip_bin.addItem("Clip 1 (placeholder)")
        self.clip_bin.addItem("Clip 2 (placeholder)")
        self.clip_bin.addItem("Clip 3 (placeholder)")
        # Clip bin holds imported source clips.
        top_splitter.addWidget(self.clip_bin)

        # --- Clip Preview Panel (middle) --- (integrated transport in its scrubber)
        self.clip_panel = ClipPreviewPanel(self)
        top_splitter.addWidget(self.clip_panel)

        # Direct references for convenience (avoid legacy alias names)
        self.clip_controller = self.clip_panel.controller
        self.video_preview = self.clip_panel.preview
        self.clip_scrub = self.clip_panel.scrubber

        # --- Project Preview Panel (right) ---
        self.project_panel = ProjectPreviewPanel(self)
        # Provide placeholder label below project panel
        proj_placeholder_container = QWidget()
        proj_placeholder_layout = QVBoxLayout()
        proj_placeholder_layout.setContentsMargins(0, 0, 0, 0)
        proj_placeholder_layout.addWidget(self.project_panel, stretch=1)
        proj_placeholder_container.setLayout(proj_placeholder_layout)
        top_splitter.addWidget(proj_placeholder_container)
        self.project_controller = self.project_panel.controller
        self.project_preview = self.project_panel.preview
        self.project_scrub = self.project_panel.scrubber

        # Bottom: multi-track composition placeholder area
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        try:
            from ..timeline import TimelineWidget as TimelineWidget

            self.project_scrub_label = QLabel("Project Scrubber (Blank)")
            self.project_scrub_label.setStyleSheet(
                "color:#bbb;font-size:11px;padding:2px 4px;"
            )
            bottom_layout.addWidget(self.project_scrub_label)
            self.project_scrub = TimelineWidget()
            # Explicit zero duration initialization
            self.project_scrub.setDuration(0.0)
            bottom_layout.addWidget(self.project_scrub)
        except Exception as e:
            self.project_scrub = None
            bottom_layout.addWidget(QLabel(f"Project scrub unavailable: {e}"))

        # Multi-track placeholder widget (future implementation)
        self.multi_track_placeholder = QLabel(
            "Multi-Track Timeline Placeholder\n(Tracks will appear here)"
        )
        self.multi_track_placeholder.setStyleSheet(
            "background:#1e1e1e;color:#aaa;padding:12px;border:1px dashed #444;"
        )
        bottom_layout.addWidget(self.multi_track_placeholder)
        bottom_container.setLayout(bottom_layout)

        # Root splitter vertical orientation
        root_splitter = QSplitter()
        root_splitter.setOrientation(Qt.Vertical)  # type: ignore
        root_splitter.addWidget(top_splitter)
        root_splitter.addWidget(bottom_container)
        root_splitter.setStretchFactor(0, 3)
        root_splitter.setStretchFactor(1, 1)

        root_layout.addWidget(root_splitter)
        central_widget.setLayout(root_layout)
        self.setCentralWidget(central_widget)

        # Connections
        self.clip = None
        self._imported_clips: dict[str, str] = {}

        # Clip bin selection -> load into clip preview controller
        self.clip_bin.currentTextChanged.connect(self._onClipBinSelectionChanged)

        # Scrubber wiring & shortcuts (terminology updated)
        if self.clip_scrub is not None:
            self.clip_scrub.seekRequested.connect(self._commitScrubSeek)
            try:
                self.clip_scrub.dragStarted.connect(self._onScrubDragStarted)
                self.clip_scrub.dragEnded.connect(self._onScrubDragEnded)
            except Exception:
                pass
            self.clip_scrub.inOutChanged.connect(self._inOutChanged)
            try:
                self.clip_scrub.thumbnailsBusy.connect(self._onThumbsBusy)
            except Exception:
                pass
            from PySide6.QtGui import QShortcut, QKeySequence

            QShortcut(QKeySequence("I"), self, activated=self.clip_scrub.setInPoint)
            QShortcut(QKeySequence("O"), self, activated=self.clip_scrub.setOutPoint)
            QShortcut(
                QKeySequence("Shift+I"), self, activated=self.clip_scrub.clearInPoint
            )
            QShortcut(
                QKeySequence("Shift+O"), self, activated=self.clip_scrub.clearOutPoint
            )

        # Synchronize audio (clip only for now)
        self.clip_controller.stateChanged.connect(self._onPlaybackState)
        self.clip_controller.positionChanged.connect(self._maybeResyncAudio)

    def _onClipBinSelectionChanged(self, text: str):
        # Load selected clip into preview if we have a file path stored.
        path = self._imported_clips.get(text)
        if path:
            self.loadMediaPath(path)

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
        self.clip_controller.seek(t)

    def _onThumbsBusy(self, busy: bool):
        if busy:
            # Pause controller during heavy thumbnail generation to free decoding resources
            if (
                getattr(self.clip_controller, "_state", None)
                and self.clip_controller._state.playing
            ):  # type: ignore[attr-defined]
                self._was_playing_before_thumbs = True
                self.clip_controller.pause()
            else:
                self._was_playing_before_thumbs = False
        else:
            if getattr(self, "_was_playing_before_thumbs", False):
                self.clip_controller.play()

    def _previewSeek(self, t: float):  # kept for potential legacy slots
        if self.clip is None:
            return
        self.clip_controller.seek(t)

    def _commitSeek(self, t: float):  # kept for potential legacy slots
        if self.clip is None:
            return
        self.clip_controller.seek(t)
        if hasattr(self, "media_player") and self.media_player.source().isLocalFile():
            self.media_player.setPosition(int(t * 1000))

    def _commitScrubSeek(self, t: float):
        self._commitSeek(t)

    def _onScrubDragStarted(self):
        # Record if we should resume after drag
        self._resume_after_drag = False
        if (
            getattr(self.clip_controller, "_state", None)
            and self.clip_controller._state.playing
        ):  # type: ignore[attr-defined]
            self._resume_after_drag = True
            self.clip_controller.pause()
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
            self.clip_controller.play()

    # --- Audio / controller synchronization ---
    def _onPlaybackState(self, state: str):
        # Delegate play button visual update to scrubber integrated controls
        try:
            self.clip_scrub.updatePlayButton(state == "playing")
        except Exception:
            pass
        if not hasattr(self, "media_player"):
            return
        mp = self.media_player
        if not mp.source().isLocalFile():
            return
        if state == "playing":
            try:
                mp.setPosition(int(self.clip_controller.position() * 1000))
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
            # Only correct when audio is BEHIND video significantly (fast-forward audio).
            # Avoid rewinding audio when video decode lags; rewinds cause audible chunk repeats.
            drift = video_ms - audio_ms
            if drift > 160:  # video ahead -> push audio forward
                mp.setPosition(video_ms)
            # If audio ahead, let video catch up naturally; frame skipping now reduces drift.
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
