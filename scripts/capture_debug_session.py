from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from pi.runtime.config import RuntimeConfig
from pi.runtime.camera import MjpegCamera
from pi.runtime.models import BallEstimate, BoardCalibration
from pi.runtime.vision import BoardCalibrator, RedBallTracker


def draw_board(frame, board: BoardCalibration) -> None:
    if not board.initialized or not board.corners:
        return

    corners = np.asarray(board.corners, dtype=np.int32)
    cv2.polylines(frame, [corners], True, (0, 255, 255), 2)


def draw_ball(frame, ball: BallEstimate) -> None:
    if not ball.found or ball.center_px is None:
        return

    cv2.circle(frame, ball.center_px, max(4, int(round(ball.radius_px))), (0, 255, 0), 2)
    cv2.circle(frame, ball.center_px, 3, (255, 0, 0), -1)


def write_jsonl_line(path: Path, payload: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def build_output_dir(base_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = base_dir / f"debug_session_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "raw").mkdir()
    (output_dir / "mask").mkdir()
    (output_dir / "overlay").mkdir()
    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture raw frames, masks, overlays, and metadata for calibration/debugging."
    )
    parser.add_argument(
        "--output-dir",
        default="captures",
        help="Base directory where the session folder should be created.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=30,
        help="Number of post-calibration samples to save.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.25,
        help="Seconds between saved samples after calibration completes.",
    )
    parser.add_argument(
        "--calibration-timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for automatic board calibration before failing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = RuntimeConfig.load()
    camera = MjpegCamera(config)
    calibrator = BoardCalibrator(config)
    tracker = RedBallTracker(config)
    output_dir = build_output_dir(Path(args.output_dir))
    metadata_path = output_dir / "metadata.jsonl"
    summary_path = output_dir / "session.json"

    summary = {
        "created_at": datetime.now().isoformat(),
        "config": {
            "camera_width": config.camera_width,
            "camera_height": config.camera_height,
            "process_width": config.process_width,
            "process_height": config.process_height,
            "camera_fps": config.camera_fps,
            "red_low_1": list(config.red_low_1),
            "red_high_1": list(config.red_high_1),
            "red_low_2": list(config.red_low_2),
            "red_high_2": list(config.red_high_2),
            "min_blob_area": config.min_blob_area,
            "max_blob_area_ratio": config.max_blob_area_ratio,
        },
        "samples_requested": args.samples,
        "interval_s": args.interval,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Debug capture starting.")
    print(f"Output directory: {output_dir}")
    print("Make sure the runtime is stopped before using this tool.")

    camera.start()
    try:
        print("Calibrating board...")
        start_time = time.time()
        board = BoardCalibration(safety_margin_ratio=config.safety_margin_ratio)
        while time.time() - start_time < args.calibration_timeout:
            frame = camera.read()
            if frame is None:
                continue
            board = calibrator.update(frame)
            if board.initialized:
                break

        if not board.initialized:
            print("Calibration did not complete in time.")
            return 1

        print("Calibration complete. Capturing samples...")
        tracker.reset()
        captured = 0
        next_capture_time = time.time()

        while captured < args.samples:
            frame = camera.read()
            if frame is None:
                continue

            ball, mask = tracker.detect(frame, board)
            now = time.time()
            if now < next_capture_time:
                continue

            overlay = frame.copy()
            draw_board(overlay, board)
            draw_ball(overlay, ball)

            stem = f"{captured:04d}"
            raw_path = output_dir / "raw" / f"{stem}.jpg"
            mask_path = output_dir / "mask" / f"{stem}.png"
            overlay_path = output_dir / "overlay" / f"{stem}.jpg"

            cv2.imwrite(str(raw_path), frame)
            cv2.imwrite(str(mask_path), mask)
            cv2.imwrite(str(overlay_path), overlay)

            payload = {
                "sample": captured,
                "timestamp": now,
                "board_initialized": board.initialized,
                "board_corners": board.corners,
                "ball_found": ball.found,
                "ball_center_px": ball.center_px,
                "ball_center_norm": ball.center_norm,
                "ball_velocity_norm": ball.velocity_norm,
                "ball_radius_px": ball.radius_px,
                "ball_area_px": ball.area_px,
                "ball_confidence": ball.confidence,
                "raw_path": str(raw_path.relative_to(output_dir)),
                "mask_path": str(mask_path.relative_to(output_dir)),
                "overlay_path": str(overlay_path.relative_to(output_dir)),
            }
            write_jsonl_line(metadata_path, payload)

            print(
                f"Saved sample {captured + 1}/{args.samples}: "
                f"found={ball.found} center={ball.center_norm} conf={ball.confidence:.2f}"
            )

            captured += 1
            next_capture_time = now + args.interval

        print(f"Done. Session saved to {output_dir}")
        return 0
    finally:
        camera.stop()


if __name__ == "__main__":
    sys.exit(main())
