"""Main application window (UI layer).

Moved from app.main to app.ui.main_window for clearer layering.
"""

from __future__ import annotations

import sys
from io import BytesIO
from PIL import Image

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QStatusBar,
)
from PySide6.QtGui import QAction, QPixmap, QShortcut, QKeySequence
from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

try:
    from moviepy import VideoFileClip
except ImportError:  # pragma: no cover
    try:
        from moviepy.editor import VideoFileClip  # type: ignore
    except ImportError as _e:  # pragma: no cover
        VideoFileClip = None  # type: ignore
        _moviepy_import_error = _e


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clipdozer")
        self.setGeometry(100, 100, 800, 600)
        self._createMenuBar()
        self._createEditorLayout()
        self._initAudio()

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
        try:
            if VideoFileClip is None:
                raise RuntimeError(f"moviepy import failed: {_moviepy_import_error}")
            self.clip = VideoFileClip(file_path)
            try:
                self._video_reader_ref = getattr(self.clip, "reader", None)
                self._audio_reader_ref = getattr(
                    getattr(self.clip, "audio", None), "reader", None
                )
            except Exception:
                self._video_reader_ref = None
                self._audio_reader_ref = None
            self.current_frame_index = 0
            self.total_frames = int(self.clip.fps * self.clip.duration)
            self._showFrame(0)
            self.timeline.addItem(f"Imported: {file_path.split('/')[-1]}")
            if hasattr(self, "scrub") and self.scrub is not None:
                try:
                    self.scrub.setMedia(self.clip)
                except Exception as e:
                    print(f"Failed to set media on timeline: {e}")
                self.scrub.setPosition(0.0)
            if hasattr(self, "media_player"):
                self._loadAudio(file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load video: {e}")

    def _createEditorLayout(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        self.video_preview = QLabel("Video Preview")
        self.video_preview.setFixedHeight(300)
        self.video_preview.setStyleSheet(
            "background: #222; color: #fff; font-size: 24px; text-align: center;"
        )
        self.video_preview.setAlignment(Qt.AlignCenter)
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
        self.play_btn.clicked.connect(self._play)
        self.pause_btn.clicked.connect(self._pause)
        from PySide6.QtCore import QTimer

        self.play_timer = QTimer(self)
        try:
            self.play_timer.setTimerType(Qt.PreciseTimer)  # type: ignore[attr-defined]
        except Exception:
            pass
        self.play_timer.timeout.connect(self._advanceFrame)
        self.clip = None
        self.current_frame_index = 0
        self.total_frames = 0
        self._play_start_time = None
        self._sync_threshold_frames = 2
        if self.scrub is not None:
            self.scrub.positionChanged.connect(self._previewSeek)
            self.scrub.seekRequested.connect(self._commitSeek)
            self.scrub.inOutChanged.connect(self._inOutChanged)
            try:
                self.scrub.thumbnailsBusy.connect(self._onThumbsBusy)
            except Exception:
                pass
            QShortcut(QKeySequence("I"), self, activated=self.scrub.setInPoint)
            QShortcut(QKeySequence("O"), self, activated=self.scrub.setOutPoint)
            QShortcut(QKeySequence("Shift+I"), self, activated=self.scrub.clearInPoint)
            QShortcut(QKeySequence("Shift+O"), self, activated=self.scrub.clearOutPoint)
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
        if self.clip is None:
            return
        try:
            if isinstance(t_or_index, int):
                t = t_or_index / self.clip.fps
            else:
                t = float(t_or_index)
            mutex = getattr(self.clip, "_external_mutex", None)
            if mutex is not None:
                mutex.lock()
            try:
                frame = self.clip.get_frame(t)
            finally:
                if mutex is not None:
                    mutex.unlock()
            h, w = frame.shape[0], frame.shape[1]
            image = Image.fromarray(frame).convert("RGB")
            target_w = self.video_preview.width()
            target_h = self.video_preview.height()
            aspect = w / h
            if target_w / target_h > aspect:
                new_h = target_h
                new_w = int(new_h * aspect)
            else:
                new_w = target_w
                new_h = int(new_w / aspect)
            image = image.resize((new_w, new_h))
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            qimage = QPixmap()
            qimage.loadFromData(buffer.read())
            self.video_preview.setPixmap(qimage)
            self.video_preview.setText("")
        except Exception as e:
            self.play_timer.stop()
            QMessageBox.critical(self, "Playback Error", f"Failed to render frame: {e}")

    def _play(self):
        if self.clip is None:
            return
        if self.current_frame_index >= self.total_frames - 1 and self.total_frames > 0:
            self.current_frame_index = 0
            self._showFrame(0)
            if (
                hasattr(self, "media_player")
                and self.media_player.source().isLocalFile()
            ):
                self.media_player.setPosition(0)
        interval_ms = int(1000 / self.clip.fps)
        if not self.play_timer.isActive():
            self.play_timer.start(interval_ms)
            try:
                from time import perf_counter

                self._play_start_time = perf_counter() - (
                    self.current_frame_index / self.clip.fps
                )
            except Exception:
                self._play_start_time = None
        if hasattr(self, "media_player") and self.media_player.source().isLocalFile():
            pos_ms = int((self.current_frame_index / self.clip.fps) * 1000)
            if abs(self.media_player.position() - pos_ms) > 80:
                self.media_player.setPosition(pos_ms)
            self.media_player.play()

    def _pause(self):
        self.play_timer.stop()
        if hasattr(self, "media_player"):
            self.media_player.pause()

    def _advanceFrame(self):
        if self.clip is None:
            self.play_timer.stop()
            return
        audio_index = None
        if (
            hasattr(self, "media_player")
            and self.media_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            try:
                audio_ms = self.media_player.position()
                audio_index = int((audio_ms / 1000.0) * self.clip.fps)
            except Exception:
                audio_index = None
        wall_index = None
        if self._play_start_time is not None:
            try:
                from time import perf_counter

                elapsed = perf_counter() - self._play_start_time
                wall_index = int(elapsed * self.clip.fps)
            except Exception:
                wall_index = None
        next_index = self.current_frame_index + 1
        if audio_index is not None:
            drift = audio_index - next_index
            if abs(drift) > self._sync_threshold_frames:
                last_drift = getattr(self, "_last_audio_drift", 0)
                if (drift > 0 and last_drift > 0) or (drift < 0 and last_drift < 0):
                    next_index = audio_index
                self._last_audio_drift = drift
            else:
                self._last_audio_drift = 0
        elif wall_index is not None:
            drift_w = wall_index - next_index
            if abs(drift_w) > self._sync_threshold_frames * 2:
                last_w_drift = getattr(self, "_last_wall_drift", 0)
                if (drift_w > 0 and last_w_drift > 0) or (
                    drift_w < 0 and last_w_drift < 0
                ):
                    next_index = wall_index
                self._last_wall_drift = drift_w
            else:
                self._last_wall_drift = 0
        self.current_frame_index = next_index
        if self.current_frame_index >= self.total_frames:
            self.play_timer.stop()
            self.current_frame_index = self.total_frames - 1
            if (
                hasattr(self, "media_player")
                and self.media_player.playbackState()
                == QMediaPlayer.PlaybackState.PlayingState
            ):
                self.media_player.pause()
            return
        self._showFrame(self.current_frame_index)
        if self.clip is not None and self.scrub is not None:
            t = self.current_frame_index / self.clip.fps
            self.scrub.setPosition(t)

    def _onThumbsBusy(self, busy: bool):
        if busy:
            if self.play_timer.isActive():
                self._was_playing_before_thumbs = True
                self._pause()
            else:
                self._was_playing_before_thumbs = False
        else:
            if getattr(self, "_was_playing_before_thumbs", False):
                self._play()

    def _previewSeek(self, t: float):
        if self.clip is None:
            return
        self.play_timer.stop()
        frame_index = int(t * self.clip.fps)
        frame_index = max(0, min(frame_index, self.total_frames - 1))
        self.current_frame_index = frame_index
        self._showFrame(self.current_frame_index)

    def _commitSeek(self, t: float):
        if self.clip is None:
            return
        frame_index = int(t * self.clip.fps)
        frame_index = max(0, min(frame_index, self.total_frames - 1))
        self.current_frame_index = frame_index
        self._showFrame(self.current_frame_index)
        if hasattr(self, "media_player") and self.media_player.source().isLocalFile():
            self.media_player.setPosition(int(t * 1000))

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
    sys.exit(app.exec())


__all__ = ["MainWindow", "run"]
