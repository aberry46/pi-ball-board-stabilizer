from __future__ import annotations

import time

import cv2
import numpy as np

from .arduino import ArduinoLink
from .camera import MjpegCamera
from .config import RuntimeConfig
from .control import Controller
from .ipc import RuntimeCommandQueue, RuntimeIpcServer, RuntimeSnapshotStore
from .models import BallEstimate, BoardCalibration, ControlOutput, RuntimeMode, RuntimeSnapshot
from .vision import BoardCalibrator, RedBallTracker, encode_jpeg_base64


class RuntimeApp:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.mode = RuntimeMode.CALIBRATING
        self.snapshot_store = RuntimeSnapshotStore()
        self.command_queue = RuntimeCommandQueue()
        self.ipc = RuntimeIpcServer(config.ipc_host, config.ipc_port, self.snapshot_store, self.command_queue)
        self.camera = MjpegCamera(config)
        self.arduino = ArduinoLink(config)
        self.controller = Controller(config)
        self.calibrator = BoardCalibrator(config)
        self.tracker = RedBallTracker(config)
        self.board = BoardCalibration(safety_margin_ratio=config.safety_margin_ratio)
        self.last_good_target_time = 0.0
        self.last_loop_time = time.time()
        self.last_frame_time = time.time()
        self.last_preview_publish_time = 0.0
        self.last_command = "CENTER"
        self.consecutive_frame_misses = 0
        self.last_raw_frame_b64: str | None = None
        self.last_mask_frame_b64: str | None = None
        self.last_detected_ball = BallEstimate()

    def run(self) -> None:
        self.ipc.start()
        self.camera.start()
        self.arduino.open()
        self.last_command = self.arduino.send_center()
        print("Runtime started in CALIBRATING mode.")

        frame_counter = 0
        try:
            while True:
                frame = self.camera.read()
                if frame is None:
                    self.consecutive_frame_misses += 1
                    if self.consecutive_frame_misses >= self.config.camera_fault_after_misses:
                        self._set_fault("camera frame unavailable")
                    time.sleep(0.01)
                    continue
                self.consecutive_frame_misses = 0

                now = time.time()
                dt = max(1e-3, now - self.last_loop_time)
                self.last_loop_time = now
                self.last_frame_time = now

                for command in self.command_queue.drain():
                    self._handle_command(command)

                display_frame = frame.copy()
                mask_frame = np.zeros(frame.shape[:2], dtype=np.uint8)
                ball = BallEstimate()

                if self.mode == RuntimeMode.CALIBRATING:
                    self.board = self.calibrator.update(frame)
                    if self.board.initialized:
                        self.mode = RuntimeMode.STOPPED
                        self.controller.reset()
                        self.tracker.reset()
                        self.last_command = self.arduino.send_center()
                        print("Calibration complete. Runtime is STOPPED and ready.")

                if self.board.initialized:
                    self._draw_board(display_frame)
                    ball, mask_frame = self.tracker.detect(frame, self.board)
                    if ball.found and ball.center_norm is not None:
                        self.last_detected_ball = ball

                if self.mode == RuntimeMode.RUNNING and self.board.initialized:
                    control = self._update_control(ball)
                else:
                    if self.last_command != "CENTER":
                        self.last_command = self.arduino.send_center()
                    control = ControlOutput(0.0, 0.0, self.last_command)

                self._draw_ball(display_frame, ball)
                self._update_preview_images(display_frame, mask_frame, now)
                snapshot = RuntimeSnapshot(
                    mode=self.mode,
                    board=self.board,
                    ball=ball,
                    control=control,
                    fps=(1.0 / dt) if dt > 0 else 0.0,
                    frame_age_ms=(time.time() - self.last_frame_time) * 1000.0,
                    last_error=None if self.mode != RuntimeMode.FAULT else "manual recovery required",
                    raw_frame_b64=self.last_raw_frame_b64,
                    mask_frame_b64=self.last_mask_frame_b64,
                )
                self.snapshot_store.set(snapshot)

                if frame_counter % self.config.log_every_n_frames == 0:
                    self._log(snapshot)
                frame_counter += 1
        finally:
            self.arduino.send_center()
            self.arduino.close()
            self.camera.stop()
            self.ipc.stop()

    def _handle_command(self, command: str) -> None:
        if command == "RUN":
            self.mode = RuntimeMode.RUNNING if self.board.initialized else RuntimeMode.CALIBRATING
            self.controller.reset()
            if self.last_detected_ball.found and self.last_detected_ball.center_norm is not None:
                self.last_good_target_time = time.time()
            print("Command: RUN")
        elif command == "PAUSE":
            self.mode = RuntimeMode.PAUSED
            self.controller.reset()
            self.last_command = self.arduino.send_center()
            print("Command: PAUSE")
        elif command == "STOP":
            self.mode = RuntimeMode.STOPPED
            self.controller.reset()
            self.last_command = self.arduino.send_center()
            print("Command: STOP")
        elif command == "RECALIBRATE":
            self.mode = RuntimeMode.CALIBRATING
            self.controller.reset()
            self.calibrator.reset()
            self.tracker.reset()
            self.board = BoardCalibration(safety_margin_ratio=self.config.safety_margin_ratio)
            self.last_command = self.arduino.send_center()
            print("Command: RECALIBRATE")

    def _set_fault(self, message: str) -> None:
        self.mode = RuntimeMode.FAULT
        self.last_command = self.arduino.send_center()
        snapshot = self.snapshot_store.get()
        snapshot.mode = RuntimeMode.FAULT
        snapshot.last_error = message
        self.snapshot_store.set(snapshot)
        print(f"FAULT: {message}")
        time.sleep(0.05)

    def _update_control(self, ball: BallEstimate) -> ControlOutput:
        now = time.time()
        if ball.found and ball.center_norm is not None:
            self.last_good_target_time = now
            tilt_x, tilt_y = self.controller.compute(
                ball.center_norm[0],
                ball.center_norm[1],
                ball.velocity_norm[0],
                ball.velocity_norm[1],
            )
            tilt_x, tilt_y = self._transform_control_axes(tilt_x, tilt_y)
            self.last_command = self.arduino.send_tilt(tilt_x, tilt_y)
            return ControlOutput(tilt_x, tilt_y, self.last_command)

        if (
            self.last_detected_ball.found
            and self.last_detected_ball.center_norm is not None
            and now - self.last_good_target_time <= self.config.lost_track_grace_s
        ):
            tilt_x, tilt_y = self.controller.compute(
                self.last_detected_ball.center_norm[0],
                self.last_detected_ball.center_norm[1],
                self.last_detected_ball.velocity_norm[0],
                self.last_detected_ball.velocity_norm[1],
            )
            tilt_x, tilt_y = self._transform_control_axes(tilt_x, tilt_y)
            self.last_command = self.arduino.send_tilt(tilt_x, tilt_y)
            return ControlOutput(tilt_x, tilt_y, self.last_command)

        self.last_command = self.arduino.send_center()
        return ControlOutput(0.0, 0.0, self.last_command)

    def _transform_control_axes(self, tilt_x: float, tilt_y: float) -> tuple[float, float]:
        out_x, out_y = tilt_x, tilt_y

        if self.config.swap_control_axes:
            out_x, out_y = out_y, out_x
        if self.config.invert_control_x:
            out_x = -out_x
        if self.config.invert_control_y:
            out_y = -out_y

        return out_x, out_y

    def _draw_board(self, frame: np.ndarray) -> None:
        corners = np.asarray(self.board.corners, dtype=np.int32)
        if corners.size == 0:
            return
        cv2.polylines(frame, [corners], True, (0, 255, 255), 2)
        center = self._norm_to_px((0.5, 0.5))
        cv2.circle(frame, center, 5, (255, 255, 0), -1)

    def _draw_ball(self, frame: np.ndarray, ball: BallEstimate) -> None:
        if not ball.found or ball.center_px is None:
            return
        cv2.circle(frame, ball.center_px, max(4, int(round(ball.radius_px))), (0, 255, 0), 2)
        cv2.circle(frame, ball.center_px, 3, (255, 0, 0), -1)

    def _update_preview_images(self, display_frame: np.ndarray, mask_frame: np.ndarray, now: float) -> None:
        if self.mode == RuntimeMode.RUNNING and self.config.disable_preview_while_running:
            self.last_raw_frame_b64 = None
            self.last_mask_frame_b64 = None
            return

        preview_fps = self.config.preview_running_fps if self.mode == RuntimeMode.RUNNING else self.config.preview_fps
        min_interval = 1.0 / max(0.1, preview_fps)
        if now - self.last_preview_publish_time < min_interval:
            return

        self.last_preview_publish_time = now
        preview_display = self._resize_for_preview(display_frame)
        preview_mask = self._resize_for_preview(cv2.cvtColor(mask_frame, cv2.COLOR_GRAY2BGR))
        self.last_raw_frame_b64 = encode_jpeg_base64(preview_display, self.config.snapshot_jpeg_quality)
        self.last_mask_frame_b64 = encode_jpeg_base64(preview_mask, self.config.snapshot_jpeg_quality)

    def _resize_for_preview(self, frame: np.ndarray) -> np.ndarray:
        height, width = frame.shape[:2]
        if width <= self.config.preview_max_width:
            return frame

        scale = self.config.preview_max_width / float(width)
        new_size = (self.config.preview_max_width, max(1, int(round(height * scale))))
        return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)

    def _norm_to_px(self, point: tuple[float, float]) -> tuple[int, int]:
        corners = np.asarray(self.board.corners, dtype=np.float32)
        src = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(src, corners)
        pt = np.array([[[point[0], point[1]]]], dtype=np.float32)
        mapped = cv2.perspectiveTransform(pt, matrix)[0, 0]
        return int(mapped[0]), int(mapped[1])

    def _log(self, snapshot: RuntimeSnapshot) -> None:
        ball = snapshot.ball
        control = snapshot.control
        print(
            f"[{snapshot.mode.value}] "
            f"fps={snapshot.fps:.1f} "
            f"ball={ball.center_norm if ball.center_norm else None} "
            f"vel={ball.velocity_norm} "
            f"conf={ball.confidence:.2f} "
            f"tilt=({control.tilt_x:.2f},{control.tilt_y:.2f})"
        )


def main() -> None:
    app = RuntimeApp(RuntimeConfig())
    app.run()


if __name__ == "__main__":
    main()
