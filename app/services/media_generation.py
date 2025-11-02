"""Media generation services: asynchronous thumbnail and waveform extraction.

These classes were previously defined inside the timeline widget module. Moving them
here reduces UI coupling and prepares for future non-Qt usage by wrapping logic only.

Future improvements:
 - Abstract clip access behind a MediaClipAdapter (thread-safe get_frame, get_audio_samples)
 - Allow configurable thumbnail sizing / strategies
 - Provide cancellation tokens rather than relying on QThread interruption state
"""

from __future__ import annotations

from typing import List

from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtGui import QImage

DEBUG_TIMELINE = False


class ThumbnailWorker(QObject):
    finished = Signal(
        int, list, list, float
    )  # generation_id, images(QImage), times, duration
    failed = Signal(int, str)

    def __init__(
        self,
        clip,
        generation_id: int,
        max_thumbs: int,
        target_height: int,
        width_hint: int,
    ):
        super().__init__()
        self._clip = clip
        self._gen = generation_id
        self._max = max_thumbs
        self._height = target_height
        self._width_hint = width_hint

    def run(self):  # executed in thread
        if DEBUG_TIMELINE:
            print(f"[ThumbnailWorker] start gen={self._gen}")
        try:
            duration = float(getattr(self._clip, "duration", 0.0))
        except Exception as e:
            self.failed.emit(self._gen, f"duration error: {e}")
            return
        if duration <= 0:
            self.failed.emit(self._gen, "non-positive duration")
            return
        if self._width_hint > 0:
            approx = max(3, int(self._width_hint / 100))  # aim ~100px per thumb
            self._max = min(max(self._max, approx), 48)
        max_thumbs = max(1, self._max)
        step = duration / max_thumbs
        times: List[float] = []
        t = 0.0
        while t < duration and len(times) < max_thumbs:
            times.append(t)
            t += step
        from PIL import Image as _Image
        from io import BytesIO as _BytesIO

        images: List[QImage] = []
        for ts in times:
            if QThread.currentThread().isInterruptionRequested():
                if DEBUG_TIMELINE:
                    print(f"[ThumbnailWorker] interrupted gen={self._gen}")
                return
            try:
                mutex = getattr(self._clip, "_external_mutex", None)
                if mutex is not None:
                    mutex.lock()
                try:
                    frame = self._clip.get_frame(ts)
                finally:
                    if mutex is not None:
                        mutex.unlock()
            except Exception:
                continue
            image = _Image.fromarray(frame).convert("RGB")
            aspect = image.width / image.height
            new_w = int(self._height * aspect)
            image = image.resize((new_w, self._height))
            buf = _BytesIO()
            image.save(buf, format="PNG")
            buf.seek(0)
            qimg = QImage.fromData(buf.read(), format="PNG")
            images.append(qimg)
        if DEBUG_TIMELINE:
            print(f"[ThumbnailWorker] finished gen={self._gen} images={len(images)}")
        self.finished.emit(self._gen, images, times, duration)


class WaveformWorker(QObject):
    finished = Signal(int, list, float)
    failed = Signal(int, str)

    def __init__(self, clip, gen_id: int, width_hint: int):
        super().__init__()
        self._clip = clip
        self._gen = gen_id
        self._width = width_hint

    def run(self):
        try:
            duration = float(getattr(self._clip, "duration", 0.0))
        except Exception as e:
            self.failed.emit(self._gen, f"duration err: {e}")
            return
        if duration <= 0 or getattr(self._clip, "audio", None) is None:
            self.failed.emit(self._gen, "no audio")
            return
        try:
            import numpy as np

            mutex = getattr(self._clip, "_external_mutex", None)
            if mutex is not None:
                mutex.lock()
            try:
                raw = self._clip.audio.to_soundarray(fps=200)
            finally:
                if mutex is not None:
                    mutex.unlock()
            if raw is None or raw.size == 0:
                self.failed.emit(self._gen, "empty audio")
                return
            if raw.ndim == 2:
                raw = raw.mean(axis=1)
            target_points = min(
                max(80, int(self._width / 2) if self._width > 0 else 400), 1600
            )
            n = raw.shape[0]
            if target_points > n:
                target_points = n
            idx_edges = np.linspace(0, n, target_points + 1).astype(int)
            rms_vals = []
            for i in range(target_points):
                s = idx_edges[i]
                e = idx_edges[i + 1]
                if e <= s:
                    rms_vals.append(0.0)
                    continue
                seg = raw[s:e]
                rms = float(np.sqrt(np.mean(seg * seg)))
                rms_vals.append(rms)
            rms_arr = np.array(rms_vals, dtype=float)
            peak = float(rms_arr.max()) if rms_arr.size else 1.0
            if peak <= 0:
                peak = 1.0
            env = (rms_arr / peak) ** 0.85
            self.finished.emit(self._gen, env.tolist(), duration)
        except Exception as e:
            if DEBUG_TIMELINE:
                print(f"[WaveformWorker] generation failed gen={self._gen}: {e}")
            self.failed.emit(self._gen, f"audio err: {e}")


__all__ = ["ThumbnailWorker", "WaveformWorker"]
