from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize, QRectF, QThread, QTimer, QMutex
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QSlider,
    QMenu,
)
from PySide6.QtGui import QPainter, QColor, QPen, QPixmap, QImage

from typing import List, Optional

# Import formatting utility and media generation workers
from .utils.timefmt import format_time
from .services.media_generation import ThumbnailWorker, WaveformWorker

DEBUG_TIMELINE = False  # set True for verbose thumbnail generation logging


## Backward compatibility: format_time historically lived here; keep name available.


class _TimelineSlider(QSlider):
    """Custom horizontal slider that can render in/out regions.

    Public attributes set by parent: duration, in_point, out_point.
    """

    def __init__(self):
        super().__init__(Qt.Horizontal)
        self.duration: float = 0.0
        self.in_point: float | None = None
        self.out_point: float | None = None
        self.setRange(0, 1000)
        self.setMouseTracking(True)

    def sizeHint(self):  # type: ignore[override]
        sz = super().sizeHint()
        return QSize(sz.width(), max(24, sz.height()))

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)  # base draws groove + handle
        if self.duration <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        groove_rect = self._grooveRect()
        # Draw in/out highlight beneath handle
        if self.in_point is not None or self.out_point is not None:
            ip = 0.0 if self.in_point is None else self.in_point
            op = self.duration if self.out_point is None else self.out_point
            if op < ip:
                ip, op = op, ip
            span_frac_start = max(0.0, min(1.0, ip / self.duration))
            span_frac_end = max(0.0, min(1.0, op / self.duration))
            x1 = groove_rect.x() + groove_rect.width() * span_frac_start
            x2 = groove_rect.x() + groove_rect.width() * span_frac_end
            highlight = QRectF(x1, groove_rect.y(), x2 - x1, groove_rect.height())
            p.fillRect(highlight, QColor(80, 160, 255, 90))

        # Draw marker lines
        pen = QPen(QColor(80, 160, 255), 2)
        p.setPen(pen)
        for point, color in (
            (self.in_point, QColor(0, 200, 120)),
            (self.out_point, QColor(220, 80, 120)),
        ):
            if point is None:
                continue
            frac = max(0.0, min(1.0, point / self.duration))
            x = groove_rect.x() + groove_rect.width() * frac
            p.setPen(QPen(color, 2))
            p.drawLine(
                int(x), groove_rect.y(), int(x), groove_rect.y() + groove_rect.height()
            )
        p.end()

    def _grooveRect(self) -> QRectF:
        # Approximate groove area (since style option not exposed easily). Use a margin.
        margin = 8
        return QRectF(margin, self.height() / 2 - 4, self.width() - margin * 2, 8)


class _ThumbnailStrip(QWidget):
    """Displays evenly spaced frame thumbnails and current position indicator."""

    def __init__(self):
        super().__init__()
        self._pixmaps: List[QPixmap] = []
        self._positions: List[float] = []  # seconds corresponding to each pixmap
        self._duration: float = 0.0
        self._current_time: float = 0.0
        self.setMinimumHeight(52)

    def setData(self, pixmaps: List[QPixmap], positions: List[float], duration: float):
        self._pixmaps = pixmaps
        self._positions = positions
        self._duration = duration
        self.update()

    def setCurrentTime(self, t: float):
        self._current_time = t
        self.update()

    def paintEvent(self, event):  # type: ignore[override]
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(30, 30, 30))
        if not self._pixmaps or self._duration <= 0:
            p.end()
            return
        w = self.width()
        h = self.height()
        for pix, pos in zip(self._pixmaps, self._positions):
            frac = pos / self._duration
            x = int(frac * w)
            target_w = max(1, int(w / len(self._pixmaps)))
            target_h = h
            scaled = pix.scaled(
                target_w,
                target_h,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            p.drawPixmap(x, 0, scaled)
        # current position line
        frac_cur = max(0.0, min(1.0, self._current_time / self._duration))
        x_line = int(frac_cur * w)
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawLine(x_line, 0, x_line, h)
        p.end()


# --- Waveform support ---


class _WaveformWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._amps: List[float] = []
        self._duration: float = 0.0
        self._current_time: float = 0.0
        self.setMinimumHeight(40)
        self.setVisible(False)

    def setData(self, amps: List[float], duration: float):
        self._amps = amps
        self._duration = duration
        self.setVisible(True)
        self.update()

    def setCurrentTime(self, t: float):
        self._current_time = t
        self.update()

    def paintEvent(self, e):  # type: ignore[override]
        p = QPainter(self)
        r = self.rect()
        p.fillRect(r, QColor(18, 18, 24))
        if not self._amps or self._duration <= 0:
            p.end()
            return
        w = r.width()
        h = r.height()
        mid = h / 2.0
        n = len(self._amps)
        from PySide6.QtGui import QPainterPath

        path = QPainterPath()
        path.moveTo(0, mid)
        for i, a in enumerate(self._amps):
            x = (i / (n - 1)) * w if n > 1 else 0
            amp_h = a * (h * 0.9 / 2.0)
            path.lineTo(x, mid - amp_h)
        for i, a in reversed(list(enumerate(self._amps))):
            x = (i / (n - 1)) * w if n > 1 else 0
            amp_h = a * (h * 0.9 / 2.0)
            path.lineTo(x, mid + amp_h)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(70, 130, 200))
        p.drawPath(path)
        # Playhead
        frac = max(0.0, min(1.0, self._current_time / self._duration))
        x_line = int(frac * w)
        p.setPen(QPen(QColor(255, 255, 255), 1))
        p.drawLine(x_line, 0, x_line, h)
        p.end()


def _initialize_waveform(tw: "TimelineWidget"):
    if getattr(tw, "waveform", None) is not None:
        return
    tw.waveform = _WaveformWidget()
    layout = tw.layout()
    if layout is not None:
        layout.insertWidget(2, tw.waveform)  # after thumbnails
    tw._wave_gen_id = 0
    tw._wave_thread: Optional[QThread] = None
    tw._wave_worker: Optional[WaveformWorker] = None

    def _startWaveformGeneration(self: "TimelineWidget"):
        if self._clip is None:
            return
        if (
            getattr(self, "_wave_thread", None) is not None
            and self._wave_thread.isRunning()
        ):
            self._wave_thread.requestInterruption()
            self._wave_thread.quit()
            self._wave_thread.wait(50)
        self._wave_gen_id += 1
        gen = self._wave_gen_id
        worker = WaveformWorker(self._clip, gen, self.width())
        thread = QThread()
        self._wave_thread = thread
        self._wave_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._waveformReady)
        worker.failed.connect(self._waveformFailed)
        worker.finished.connect(lambda *_: thread.quit())
        worker.failed.connect(lambda *_: thread.quit())
        thread.finished.connect(worker.deleteLater)
        thread.start()

    def _waveformReady(self: "TimelineWidget", gen: int, amps: list, duration: float):
        if gen != self._wave_gen_id:
            return
        if amps:
            self.waveform.setData(amps, duration)
            self.waveform.setCurrentTime(0.0)
        else:
            self.waveform.setVisible(False)

    def _waveformFailed(self: "TimelineWidget", gen: int, reason: str):
        if gen != self._wave_gen_id:
            return
        self.waveform.setVisible(False)

    tw._startWaveformGeneration = _startWaveformGeneration.__get__(tw, tw.__class__)  # type: ignore
    tw._waveformReady = _waveformReady.__get__(tw, tw.__class__)  # type: ignore
    tw._waveformFailed = _waveformFailed.__get__(tw, tw.__class__)  # type: ignore


class TimelineWidget(QWidget):
    """Simple scrub bar with future in/out marker support.

    Signals:
        positionChanged(float): Emitted while the user drags (preview seek).
        seekRequested(float): Emitted when user releases the slider (final seek commit).
        inOutChanged(float|None, float|None): Emitted when in/out markers change.
    """

    positionChanged = Signal(float)
    seekRequested = Signal(float)
    inOutChanged = Signal(object, object)
    thumbnailsBusy = Signal(bool)  # True when regeneration active

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._duration = 0.0
        self._in_point: float | None = None
        self._out_point: float | None = None
        self._suppress_signal = False
        self._clip = None
        self._thumb_gen_id = 0
        self._pending_thread: Optional[QThread] = None
        self._thumb_worker: Optional[ThumbnailWorker] = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._regenerateThumbnails)
        # Mutex exposed for worker threads to coordinate clip decoding
        self._clip_mutex = QMutex()
        # Bind mutex onto clip later in setMedia so workers can access via _external_mutex

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)

        # Time label row
        label_row = QHBoxLayout()
        self.label_current = QLabel("00:00.000")
        self.label_spacer = QLabel("/")
        self.label_duration = QLabel("00:00.000")
        self.label_range = QLabel("")  # shows [IN-OUT]
        label_row.addWidget(self.label_current)
        label_row.addWidget(self.label_spacer)
        label_row.addWidget(self.label_duration)
        label_row.addStretch(1)
        label_row.addWidget(self.label_range)
        outer.addLayout(label_row)

        # Thumbnails strip (optional, hidden until media supplied)
        self.thumbnail_strip = _ThumbnailStrip()
        self.thumbnail_strip.setVisible(False)
        outer.addWidget(self.thumbnail_strip)

        # Slider (custom)
        self.slider = _TimelineSlider()
        self.slider.sliderPressed.connect(self._onSliderPressed)
        self.slider.sliderMoved.connect(self._onSliderMoved)
        self.slider.sliderReleased.connect(self._onSliderReleased)
        self.slider.setSingleStep(1)
        outer.addWidget(self.slider)

        self.setLayout(outer)
        # Initialize waveform support (invisible until data loaded)
        _initialize_waveform(self)

    # --- Public API ---
    def setDuration(self, duration: float):
        self._duration = max(0.0, float(duration))
        self.label_duration.setText(format_time(self._duration))
        self.slider.duration = self._duration
        # Clamp markers if necessary
        if self._in_point is not None and self._in_point > self._duration:
            self._in_point = None
        if self._out_point is not None and self._out_point > self._duration:
            self._out_point = None
        self._updateRangeLabel()
        self.slider.in_point = self._in_point
        self.slider.out_point = self._out_point
        self.slider.update()

    def setPosition(self, t: float):
        if self._duration <= 0:
            return
        frac = min(max(t / self._duration, 0.0), 1.0)
        # Avoid feedback loops during drag
        if not self.slider.isSliderDown():
            self._suppress_signal = True
            try:
                self.slider.setValue(int(frac * self.slider.maximum()))
            finally:
                self._suppress_signal = False
        self.label_current.setText(format_time(t))
        if self.thumbnail_strip.isVisible():
            self.thumbnail_strip.setCurrentTime(t)
        if hasattr(self, "waveform") and self.waveform.isVisible():
            self.waveform.setCurrentTime(t)

    def setInPoint(self):
        if self._duration <= 0:
            return
        pos = self.currentPosition()
        self._in_point = pos
        if self._out_point is not None and self._out_point < self._in_point:
            self._out_point = None  # reset inconsistent
        self._updateRangeLabel()
        self.inOutChanged.emit(self._in_point, self._out_point)
        self.slider.in_point = self._in_point
        self.slider.out_point = self._out_point
        self.slider.update()

    def clearInPoint(self):
        self._in_point = None
        self._updateRangeLabel()
        self.inOutChanged.emit(self._in_point, self._out_point)
        self.slider.in_point = self._in_point
        self.slider.update()

    def setOutPoint(self):
        if self._duration <= 0:
            return
        pos = self.currentPosition()
        self._out_point = pos
        if self._in_point is not None and self._out_point < self._in_point:
            self._in_point = None
        self._updateRangeLabel()
        self.inOutChanged.emit(self._in_point, self._out_point)
        self.slider.out_point = self._out_point
        self.slider.in_point = self._in_point
        self.slider.update()

    def clearOutPoint(self):
        self._out_point = None
        self._updateRangeLabel()
        self.inOutChanged.emit(self._in_point, self._out_point)
        self.slider.out_point = self._out_point
        self.slider.update()

    def currentPosition(self) -> float:
        if self._duration <= 0:
            return 0.0
        return (self.slider.value() / self.slider.maximum()) * self._duration

    def inOut(self) -> tuple[float | None, float | None]:
        return self._in_point, self._out_point

    # --- Internal helpers ---
    def _updateRangeLabel(self):
        if self._in_point is None and self._out_point is None:
            self.label_range.setText("")
        else:
            part_in = (
                format_time(self._in_point) if self._in_point is not None else "--"
            )
            part_out = (
                format_time(self._out_point) if self._out_point is not None else "--"
            )
            self.label_range.setText(f"[{part_in} - {part_out}]")
        self.slider.in_point = self._in_point
        self.slider.out_point = self._out_point
        self.slider.update()

    # --- Slider callbacks ---
    def _onSliderPressed(self):
        # we don't emit yet; user is starting drag
        pass

    def _onSliderMoved(self, value: int):
        if self._suppress_signal:
            return
        if self._duration <= 0:
            return
        t = (value / self.slider.maximum()) * self._duration
        self.label_current.setText(format_time(t))
        self.positionChanged.emit(t)
        if self.thumbnail_strip.isVisible():
            self.thumbnail_strip.setCurrentTime(t)
        if hasattr(self, "waveform") and self.waveform.isVisible():
            self.waveform.setCurrentTime(t)

    def _onSliderReleased(self):
        if self._duration <= 0:
            return
        value = self.slider.value()
        t = (value / self.slider.maximum()) * self._duration
        self.label_current.setText(format_time(t))
        self.seekRequested.emit(t)
        if self.thumbnail_strip.isVisible():
            self.thumbnail_strip.setCurrentTime(t)
        if hasattr(self, "waveform") and self.waveform.isVisible():
            self.waveform.setCurrentTime(t)

    # --- Context menu for future marker control ---
    def contextMenuEvent(self, event):  # type: ignore[override]
        menu = QMenu(self)
        if self._in_point is None:
            menu.addAction("Set In", self.setInPoint)
        else:
            menu.addAction("Clear In", self.clearInPoint)
            menu.addAction("Move In Here", self.setInPoint)
        if self._out_point is None:
            menu.addAction("Set Out", self.setOutPoint)
        else:
            menu.addAction("Clear Out", self.clearOutPoint)
            menu.addAction("Move Out Here", self.setOutPoint)
        menu.exec(event.globalPos())

    # --- New API: media + thumbnails ---
    def setMedia(self, clip, max_thumbs: int = 12):
        """Provide a MoviePy VideoFileClip for generating thumbnails and duration asynchronously."""
        self._clip = clip
        # Attach mutex for external workers
        try:
            setattr(self._clip, "_external_mutex", self._clip_mutex)
        except Exception:
            pass
        # Set duration immediately so scrubbing works before thumbs
        try:
            self.setDuration(float(getattr(clip, "duration", 0.0)))
        except Exception:
            pass
        self._startThumbnailGeneration(max_thumbs=max_thumbs)
        # Start waveform generation
        if hasattr(self, "_startWaveformGeneration"):
            self._startWaveformGeneration()

    # --- Thumbnail async flow ---
    def _startThumbnailGeneration(self, max_thumbs: int = 12):
        if self._clip is None:
            return
        self.thumbnailsBusy.emit(True)
        # Cancel previous thread if running
        if self._pending_thread is not None:
            # Request interruption and allow previous to wind down; do not block long.
            if self._pending_thread.isRunning():
                self._pending_thread.requestInterruption()
                self._pending_thread.quit()
                self._pending_thread.wait(50)
        self._thumb_gen_id += 1
        gen_id = self._thumb_gen_id
        worker = ThumbnailWorker(self._clip, gen_id, max_thumbs, 50, self.width())
        thread = QThread()
        self._pending_thread = thread
        self._thumb_worker = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._onThumbsReady)
        worker.failed.connect(self._onThumbsFailed)
        # Ensure cleanup
        worker.finished.connect(lambda *_: thread.quit())
        worker.failed.connect(lambda *_: thread.quit())
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._clearThread(thread))
        thread.start()
        if DEBUG_TIMELINE:
            print(
                f"[TimelineWidget] spawned gen={gen_id} thread id={int(thread.currentThreadId())}"
            )

    def _clearThread(self, thread):
        if self._pending_thread is thread:
            self._pending_thread = None
            self._thumb_worker = None
            self.thumbnailsBusy.emit(False)
            if DEBUG_TIMELINE:
                print("[TimelineWidget] thread cleared")

    def _onThumbsReady(self, gen_id: int, images: list, times: list, duration: float):
        if gen_id != self._thumb_gen_id:
            return  # stale
        self.setDuration(duration)
        pixmaps: List[QPixmap] = []
        for img in images:
            if isinstance(img, QImage):
                pixmaps.append(QPixmap.fromImage(img))
        if pixmaps:
            self.thumbnail_strip.setData(pixmaps, times, duration)
            self.thumbnail_strip.setVisible(True)
            self.thumbnail_strip.setCurrentTime(0.0)
        else:
            self.thumbnail_strip.setVisible(False)
        if DEBUG_TIMELINE:
            print(
                f"[TimelineWidget] thumbnails applied gen={gen_id} count={len(pixmaps)}"
            )

    def _onThumbsFailed(self, gen_id: int, reason: str):
        if gen_id != self._thumb_gen_id:
            return
        self.thumbnail_strip.setVisible(False)
        if DEBUG_TIMELINE:
            print(
                f"[TimelineWidget] thumbnail generation failed gen={gen_id}: {reason}"
            )

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        # Debounce thumbnail regeneration on width changes.
        if self._clip is None:
            return
        self._resize_timer.start(300)

    def _regenerateThumbnails(self):
        # Only regenerate if width meaningfully changed (could track previous width; simple approach now)
        if self._clip is None:
            return
        self._startThumbnailGeneration()
        if hasattr(self, "_startWaveformGeneration"):
            self._startWaveformGeneration()

    def closeEvent(self, event):  # type: ignore[override]
        # Cleanly stop any running worker thread on widget close to avoid warnings.
        if self._pending_thread is not None and self._pending_thread.isRunning():
            self._pending_thread.requestInterruption()
            self._pending_thread.quit()
            self._pending_thread.wait(200)
        super().closeEvent(event)
        if (
            hasattr(self, "_wave_thread")
            and self._wave_thread is not None
            and self._wave_thread.isRunning()
        ):
            self._wave_thread.requestInterruption()
            self._wave_thread.quit()
            self._wave_thread.wait(200)
