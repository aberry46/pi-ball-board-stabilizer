from __future__ import annotations

import subprocess
import time

import cv2
import numpy as np

from .config import RuntimeConfig


class MjpegCamera:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.process: subprocess.Popen | None = None
        self.buffer = b""

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

    def read(self) -> np.ndarray | None:
        if self.process is None or self.process.stdout is None:
            return None

        deadline = time.time() + self.config.camera_frame_timeout_s
        while time.time() < deadline:
            jpg = self._pop_latest_jpeg()
            if jpg is not None:
                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    return cv2.resize(frame, (self.config.process_width, self.config.process_height))

            chunk = self.process.stdout.read(4096)
            if not chunk:
                time.sleep(0.005)
                continue
            self.buffer += chunk

        return None

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
        if self.process.stdout is not None:
            self.process.stdout.close()
        self.process.terminate()
        self.process = None
