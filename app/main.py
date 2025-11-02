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
)
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStatusBar
from PySide6.QtGui import QShortcut, QKeySequence
import sys

try:
    # moviepy 2.x removed the 'editor' aggregator; import directly
    from moviepy import VideoFileClip
except ImportError:
    # fallback for 1.x if environment ever downgrades
    try:
        from moviepy.editor import VideoFileClip  # type: ignore
    except ImportError as _e:
        VideoFileClip = None  # type: ignore
        _moviepy_import_error = _e
from PIL import Image
from io import BytesIO


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clipdozer")
        self.setGeometry(100, 100, 800, 600)
        self._createMenuBar()
        self._createEditorLayout()

    def _createMenuBar(self):
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")
        import_action = QAction("Import Media", self)
        import_action.triggered.connect(self._importMedia)
        file_menu.addAction(import_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # About menu
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
            # load clip
            self.clip = VideoFileClip(file_path)
            self.current_frame_index = 0
            self.total_frames = int(self.clip.fps * self.clip.duration)
            self._showFrame(0)
            self.timeline.addItem(f"Imported: {file_path.split('/')[-1]}")
            if hasattr(self, "scrub") and self.scrub is not None:
                # Provide full media so thumbnails + duration load
                try:
                    self.scrub.setMedia(self.clip)
                except Exception as e:
                    print(f"Failed to set media on timeline: {e}")
                self.scrub.setPosition(0.0)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load video: {e}")

    def _createEditorLayout(self):
        # Central widget and main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()

        # Video preview area (placeholder)
        self.video_preview = QLabel("Video Preview")
        self.video_preview.setFixedHeight(300)
        self.video_preview.setStyleSheet(
            "background: #222; color: #fff; font-size: 24px; text-align: center;"
        )
        self.video_preview.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.video_preview)

        # Scrub / timeline bar (new)
        try:
            from .timeline import (
                TimelineWidget,
            )  # local import so file optional earlier

            self.scrub = TimelineWidget()
            main_layout.addWidget(self.scrub)
        except Exception as e:  # fail gracefully if timeline missing
            self.scrub = None
            print(f"TimelineWidget unavailable: {e}")

        # Timeline/clip list (placeholder)
        self.timeline = QListWidget()
        self.timeline.addItem("Clip 1")
        self.timeline.addItem("Clip 2")
        main_layout.addWidget(self.timeline)

        # Playback controls
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

        # playback wiring
        self.play_btn.clicked.connect(self._play)
        self.pause_btn.clicked.connect(self._pause)

        from PySide6.QtCore import QTimer

        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._advanceFrame)
        self.clip = None
        self.current_frame_index = 0
        self.total_frames = 0

        if self.scrub is not None:
            self.scrub.positionChanged.connect(self._previewSeek)
            self.scrub.seekRequested.connect(self._commitSeek)
            self.scrub.inOutChanged.connect(self._inOutChanged)
            # keyboard shortcuts
            QShortcut(QKeySequence("I"), self, activated=self.scrub.setInPoint)
            QShortcut(QKeySequence("O"), self, activated=self.scrub.setOutPoint)
            QShortcut(QKeySequence("Shift+I"), self, activated=self.scrub.clearInPoint)
            QShortcut(QKeySequence("Shift+O"), self, activated=self.scrub.clearOutPoint)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def _ensureFFmpeg(self):
        """Check ffmpeg availability; MoviePy relies on it for decoding."""
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
                # index to time
                t = t_or_index / self.clip.fps
            else:
                t = float(t_or_index)
            frame = self.clip.get_frame(t)
            h, w = frame.shape[0], frame.shape[1]
            image = Image.fromarray(frame).convert("RGB")
            # maintain aspect ratio
            target_w = self.video_preview.width()
            target_h = self.video_preview.height()
            aspect = w / h
            if target_w / target_h > aspect:
                # height-bound
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
            # On failure pause playback
            self.play_timer.stop()
            QMessageBox.critical(self, "Playback Error", f"Failed to render frame: {e}")

    def _play(self):
        if self.clip is None:
            return
        # start timer with frame interval
        interval_ms = int(1000 / self.clip.fps)
        if not self.play_timer.isActive():
            self.play_timer.start(interval_ms)

    def _pause(self):
        self.play_timer.stop()

    def _advanceFrame(self):
        if self.clip is None:
            self.play_timer.stop()
            return
        self.current_frame_index += 1
        if self.current_frame_index >= self.total_frames:
            self.play_timer.stop()
            self.current_frame_index = 0  # loop back to start
        self._showFrame(self.current_frame_index)
        if self.clip is not None and self.scrub is not None:
            t = self.current_frame_index / self.clip.fps
            self.scrub.setPosition(t)

    # --- Scrub bar handlers ---
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

    def _inOutChanged(self, in_t, out_t):
        if not self.statusBar():
            self.setStatusBar(QStatusBar())  # type: ignore
        if in_t is None and out_t is None:
            self.statusBar().showMessage("")
        else:
            try:
                from .timeline import format_time

                in_s = format_time(in_t) if in_t is not None else "--"
                out_s = format_time(out_t) if out_t is not None else "--"
                self.statusBar().showMessage(f"Selection: {in_s} to {out_s}")
            except Exception:
                pass


def run():
    app = QApplication(sys.argv)
    window = MainWindow()
    window._ensureFFmpeg()
    window.show()
    sys.exit(app.exec())
