from __future__ import annotations

import subprocess
import threading
import time

import cv2
import numpy as np

from .config import RuntimeConfig


class MjpegCamera:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.process: subprocess.Popen | None = None
        self.buffer = b""
        self.latest_frame: np.ndarray | None = None
        self.latest_frame_time = 0.0
        self._lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        self.process = subprocess.Popen(
            [
                "rpicam-vid",
                "--nopreview",
                "--inline",
                "--width",
                str(self.config.camera_width),
                "--height",
                str(self.config.camera_height),
                "--framerate",
                str(self.config.camera_fps),
                "--buffer-count",
                "1",
                "--timeout",
                "0",
                "--codec",
                "mjpeg",
                "--output",
                "-",
            ],
            stdout=subprocess.PIPE,
            bufsize=10**7,
        )
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def read(self) -> np.ndarray | None:
        deadline = time.time() + self.config.camera_frame_timeout_s
        while time.time() < deadline:
            with self._lock:
                frame = None if self.latest_frame is None else self.latest_frame.copy()
            if frame is not None:
                return frame
            time.sleep(0.005)

        return None

    def _reader_loop(self) -> None:
        if self.process is None or self.process.stdout is None:
            return

        while self._running:
            chunk = self.process.stdout.read(4096)
            if not chunk:
                time.sleep(0.005)
                continue

            self.buffer += chunk
            while True:
                jpg = self._pop_latest_jpeg()
                if jpg is None:
                    break

                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                frame = cv2.resize(frame, (self.config.process_width, self.config.process_height))
                with self._lock:
                    self.latest_frame = frame
                    self.latest_frame_time = time.time()

    def _pop_latest_jpeg(self) -> bytes | None:
        end = self.buffer.rfind(b"\xff\xd9")
        if end == -1:
            return None

        start = self.buffer.rfind(b"\xff\xd8", 0, end)
        if start == -1:
            self.buffer = self.buffer[max(0, end - 2):]
            return None

        jpg = self.buffer[start : end + 2]
        self.buffer = self.buffer[end + 2 :]
        return jpg

    def stop(self) -> None:
        if self.process is None:
            return
        self._running = False
        if self.process.stdout is not None:
            self.process.stdout.close()
        self.process.terminate()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=0.5)
            self._reader_thread = None
        self.process = None
        with self._lock:
            self.latest_frame = None
            self.latest_frame_time = 0.0
