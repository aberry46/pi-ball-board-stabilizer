from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from pi.runtime.arduino import ArduinoLink
from pi.runtime.camera import MjpegCamera
from pi.runtime.config import RuntimeConfig
from pi.runtime.logging import ControlTraceLogger, ControlTraceRecord
from pi.runtime.models import BoardCalibration
from pi.runtime.vision import BoardCalibrator, RedBallTracker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect system-ID traces by pulsing board tilt while tracking the marble.")
    parser.add_argument("--output-dir", default="runtime_data/system_id", help="Directory for saved traces.")
    parser.add_argument("--amplitudes", default="0.20,0.35,0.50", help="Comma-separated pulse amplitudes.")
    parser.add_argument("--pulse-duration", type=float, default=0.6, help="Seconds to hold each pulse.")
    parser.add_argument("--settle-duration", type=float, default=1.0, help="Seconds to wait between pulses.")
    parser.add_argument("--repeats", type=int, default=2, help="Repeats per pulse direction/amplitude.")
    parser.add_argument("--calibration-timeout", type=float, default=10.0, help="Seconds to wait for board calibration.")
    return parser.parse_args()


def calibrate_board(camera: MjpegCamera, calibrator: BoardCalibrator, timeout_s: float) -> BoardCalibration:
    start = time.time()
    board = BoardCalibration()
    while time.time() - start < timeout_s:
        frame = camera.read()
        if frame is None:
            continue
        board = calibrator.update(frame)
        if board.initialized:
            return board
    return board


def sample_ball(camera: MjpegCamera, tracker: RedBallTracker, board: BoardCalibration):
    frame = camera.read()
    if frame is None:
        return None
    ball, _ = tracker.detect(frame, board)
    return ball


def main() -> int:
    args = parse_args()
    config = RuntimeConfig()
    amplitudes = [float(part) for part in args.amplitudes.split(",") if part.strip()]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    camera = MjpegCamera(config)
    calibrator = BoardCalibrator(config)
    tracker = RedBallTracker(config)
    arduino = ArduinoLink(config)
    trace_logger = ControlTraceLogger(output_dir)
    manifest_path = output_dir / f"system_id_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    manifest = {
        "created_at": datetime.now().isoformat(),
        "pulse_duration_s": args.pulse_duration,
        "settle_duration_s": args.settle_duration,
        "repeats": args.repeats,
        "amplitudes": amplitudes,
        "session_id": trace_logger.session_id,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    camera.start()
    arduino.open()
    try:
        print("Calibrating board for system-ID...")
        board = calibrate_board(camera, calibrator, args.calibration_timeout)
        if not board.initialized:
            print("Board calibration failed.")
            return 1

        tracker.reset()
        print("Starting pulse collection. Keep the marble visible and away from the edges.")
        pulses = []
        for amplitude in amplitudes:
            pulses.extend(
                [
                    ("x+", amplitude, amplitude, 0.0),
                    ("x-", amplitude, -amplitude, 0.0),
                    ("y+", amplitude, 0.0, amplitude),
                    ("y-", amplitude, 0.0, -amplitude),
                ]
            )

        for repeat in range(args.repeats):
            for label, amplitude, tilt_x, tilt_y in pulses:
                pre_ball = sample_ball(camera, tracker, board)
                if pre_ball is None or not pre_ball.found or pre_ball.center_norm is None:
                    print(f"Skipping pulse {label} amplitude={amplitude:.2f}: ball not found.")
                    continue
                if (
                    pre_ball.center_norm[0] <= config.nn_near_edge_margin
                    or pre_ball.center_norm[0] >= 1.0 - config.nn_near_edge_margin
                    or pre_ball.center_norm[1] <= config.nn_near_edge_margin
                    or pre_ball.center_norm[1] >= 1.0 - config.nn_near_edge_margin
                ):
                    print(f"Skipping pulse {label} amplitude={amplitude:.2f}: ball too close to edge.")
                    continue
                if abs(pre_ball.velocity_norm[0]) > config.low_speed_threshold or abs(pre_ball.velocity_norm[1]) > config.low_speed_threshold:
                    print(f"Skipping pulse {label} amplitude={amplitude:.2f}: ball already moving too fast.")
                    continue

                print(f"Pulse {label} amplitude={amplitude:.2f} repeat={repeat + 1}/{args.repeats}")
                pulse_end = time.time() + args.pulse_duration
                while time.time() < pulse_end:
                    command = arduino.send_tilt(tilt_x, tilt_y)
                    ball = sample_ball(camera, tracker, board)
                    if ball is None:
                        continue
                    trace_logger.log(
                        ControlTraceRecord(
                            timestamp=time.time(),
                            session_id=trace_logger.session_id,
                            mode="SYSTEM_ID",
                            controller_mode="system_id",
                            ball_found=ball.found,
                            x=None if ball.center_norm is None else float(ball.center_norm[0]),
                            y=None if ball.center_norm is None else float(ball.center_norm[1]),
                            vx=float(ball.velocity_norm[0]),
                            vy=float(ball.velocity_norm[1]),
                            confidence=float(ball.confidence),
                            near_edge=False if ball.center_norm is None else (
                                ball.center_norm[0] <= config.nn_near_edge_margin
                                or ball.center_norm[0] >= 1.0 - config.nn_near_edge_margin
                                or ball.center_norm[1] <= config.nn_near_edge_margin
                                or ball.center_norm[1] >= 1.0 - config.nn_near_edge_margin
                            ),
                            ball_lost=not ball.found,
                            tilt_x=tilt_x,
                            tilt_y=tilt_y,
                            sent_command=command,
                            command_source="system_id",
                            command_clamped=abs(tilt_x) >= config.max_tilt or abs(tilt_y) >= config.max_tilt,
                            legacy_tilt_x=tilt_x,
                            legacy_tilt_y=tilt_y,
                            nn_tilt_x=0.0,
                            nn_tilt_y=0.0,
                            nn_enabled=False,
                            nn_mode="legacy",
                            nn_active=False,
                            nn_inference_ms=0.0,
                            nn_disagreement=0.0,
                            nn_edge_risk=0.0,
                            nn_fallback_reason=None,
                            board_corners=list(board.corners),
                            board_initialized=board.initialized,
                            experiment_tag=f"{label}:{amplitude:.2f}:repeat{repeat + 1}",
                        )
                    )
                    time.sleep(1.0 / max(config.camera_fps, 1))

                settle_end = time.time() + args.settle_duration
                while time.time() < settle_end:
                    arduino.send_center()
                    time.sleep(0.05)

        print(f"System-ID traces saved under {output_dir}")
        return 0
    finally:
        arduino.send_center()
        arduino.close()
        camera.stop()
        trace_logger.close()


if __name__ == "__main__":
    sys.exit(main())
