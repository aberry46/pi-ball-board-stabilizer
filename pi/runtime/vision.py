from __future__ import annotations

import base64
from collections import deque

import cv2
import numpy as np

from .config import RuntimeConfig
from .models import BallEstimate, BoardCalibration


class BoardCalibrator:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.samples: list[np.ndarray] = []

    def reset(self) -> None:
        self.samples.clear()

    def update(self, frame_bgr: np.ndarray) -> BoardCalibration:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh = cv2.morphologyEx(
            thresh,
            cv2.MORPH_CLOSE,
            np.ones((9, 9), dtype=np.uint8),
            iterations=2,
        )
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_score = 0.0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 4000:
                continue
            rect = cv2.minAreaRect(contour)
            (_, _), (w, h), _ = rect
            rect_area = max(w * h, 1.0)
            fill = area / rect_area
            score = area * fill
            if score > best_score:
                best = rect
                best_score = score

        progress = min(1.0, (len(self.samples) + 1) / self.config.calibration_frames)
        if best is None:
            return BoardCalibration(initialized=False, progress=progress, safety_margin_ratio=self.config.safety_margin_ratio)

        corners = cv2.boxPoints(best).astype(np.float32)
        self.samples.append(self._order_corners(corners))
        if len(self.samples) < self.config.calibration_frames:
            return BoardCalibration(initialized=False, progress=progress, safety_margin_ratio=self.config.safety_margin_ratio)

        averaged = np.mean(np.stack(self.samples[-self.config.calibration_frames:]), axis=0)
        return BoardCalibration(
            corners=[(float(x), float(y)) for x, y in averaged],
            initialized=True,
            progress=1.0,
            safety_margin_ratio=self.config.safety_margin_ratio,
        )

    def _order_corners(self, corners: np.ndarray) -> np.ndarray:
        sums = corners.sum(axis=1)
        diffs = corners[:, 1] - corners[:, 0]
        ordered = np.zeros((4, 2), dtype=np.float32)
        ordered[0] = corners[np.argmin(sums)]
        ordered[2] = corners[np.argmax(sums)]
        ordered[1] = corners[np.argmin(diffs)]
        ordered[3] = corners[np.argmax(diffs)]
        return ordered


class RedBallTracker:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.last_positions: deque[tuple[float, float, float]] = deque(maxlen=3)

    def reset(self) -> None:
        self.last_positions.clear()

    def detect(self, frame_bgr: np.ndarray, calibration: BoardCalibration) -> tuple[BallEstimate, np.ndarray]:
        mask = np.zeros(frame_bgr.shape[:2], dtype=np.uint8)
        if not calibration.initialized or not calibration.corners:
            return BallEstimate(), mask

        corners = np.asarray(calibration.corners, dtype=np.float32)
        roi_mask = np.zeros_like(mask)
        cv2.fillConvexPoly(roi_mask, corners.astype(np.int32), 255)

        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array(self.config.red_low_1), np.array(self.config.red_high_1))
        mask2 = cv2.inRange(hsv, np.array(self.config.red_low_2), np.array(self.config.red_high_2))
        mask = cv2.bitwise_or(mask1, mask2)
        mask = cv2.bitwise_and(mask, roi_mask)

        open_kernel = np.ones((self.config.morphology_open, self.config.morphology_open), dtype=np.uint8)
        close_kernel = np.ones((self.config.morphology_close, self.config.morphology_close), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return BallEstimate(), mask

        roi_area = float(np.count_nonzero(roi_mask))
        max_blob_area = roi_area * self.config.max_blob_area_ratio

        best = None
        best_score = -1.0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.config.min_blob_area or area > max_blob_area:
                continue
            perimeter = max(cv2.arcLength(contour, True), 1.0)
            compactness = float((4.0 * np.pi * area) / (perimeter * perimeter))
            moments = cv2.moments(contour)
            if moments["m00"] <= 0:
                continue
            cx = moments["m10"] / moments["m00"]
            cy = moments["m01"] / moments["m00"]
            score = area + compactness * 120.0
            if score > best_score:
                (_, _), radius = cv2.minEnclosingCircle(contour)
                best = (cx, cy, radius, area, compactness)
                best_score = score

        if best is None:
            return BallEstimate(), mask

        cx, cy, radius, area, compactness = best
        center_norm = self._map_to_unit_square((cx, cy), corners)
        now = cv2.getTickCount() / cv2.getTickFrequency()
        velocity = (0.0, 0.0)
        if self.last_positions:
            px, py, pt = self.last_positions[-1]
            dt = max(1e-3, now - pt)
            velocity = ((center_norm[0] - px) / dt, (center_norm[1] - py) / dt)
        self.last_positions.append((center_norm[0], center_norm[1], now))

        confidence = min(1.0, 0.35 + (area / max(self.config.min_blob_area, 1)) / 6.0 + compactness * 0.4)
        estimate = BallEstimate(
            found=confidence >= self.config.min_confidence,
            center_px=(int(round(cx)), int(round(cy))),
            center_norm=center_norm,
            velocity_norm=velocity,
            radius_px=float(radius),
            area_px=float(area),
            confidence=float(confidence),
        )
        return estimate, mask

    def _map_to_unit_square(self, point: tuple[float, float], corners: np.ndarray) -> tuple[float, float]:
        dst = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
        pts = np.array([[[float(point[0]), float(point[1])]]], dtype=np.float32)
        mapped = cv2.perspectiveTransform(pts, matrix)[0, 0]
        return float(mapped[0]), float(mapped[1])


def encode_jpeg_base64(image: np.ndarray, quality: int) -> str | None:
    ok, buffer = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return None
    return base64.b64encode(buffer.tobytes()).decode("ascii")
