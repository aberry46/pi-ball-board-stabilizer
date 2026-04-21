from __future__ import annotations

from dataclasses import dataclass

from .config import RuntimeConfig


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


@dataclass
class Controller:
    config: RuntimeConfig
    integral_x: float = 0.0
    integral_y: float = 0.0

    def reset(self) -> None:
        self.integral_x = 0.0
        self.integral_y = 0.0

    def compute(self, x: float, y: float, vx: float, vy: float, *, ignore_velocity: bool = False) -> tuple[float, float]:
        if ignore_velocity:
            vx = 0.0
            vy = 0.0
        error_x = 0.5 - x
        error_y = 0.5 - y
        predicted_error_x = error_x - self.config.lookahead_time_s * vx
        predicted_error_y = error_y - self.config.lookahead_time_s * vy

        if abs(error_x) < self.config.deadband:
            self.integral_x = 0.0
        else:
            self.integral_x = clamp(
                self.integral_x + error_x,
                -self.config.integral_limit,
                self.config.integral_limit,
            )

        if abs(error_y) < self.config.deadband:
            self.integral_y = 0.0
        else:
            self.integral_y = clamp(
                self.integral_y + error_y,
                -self.config.integral_limit,
                self.config.integral_limit,
            )

        tilt_x = (
            self.config.kp_x * predicted_error_x
            + self.config.ki_x * self.integral_x
            - self.config.kd_x * vx
        )
        tilt_y = (
            self.config.kp_y * predicted_error_y
            + self.config.ki_y * self.integral_y
            - self.config.kd_y * vy
        )

        if abs(predicted_error_x) >= self.config.catch_error_threshold or abs(vx) >= self.config.catch_velocity_threshold:
            tilt_x *= self.config.catch_multiplier
        if abs(predicted_error_y) >= self.config.catch_error_threshold or abs(vy) >= self.config.catch_velocity_threshold:
            tilt_y *= self.config.catch_multiplier

        if abs(vx) <= self.config.low_speed_threshold and abs(error_x) >= self.config.low_speed_error_threshold:
            tilt_x += sign(error_x) * self.config.low_speed_tilt_boost
        if abs(vy) <= self.config.low_speed_threshold and abs(error_y) >= self.config.low_speed_error_threshold:
            tilt_y += sign(error_y) * self.config.low_speed_tilt_boost

        if abs(tilt_x) < self.config.deadband:
            tilt_x = 0.0
        if abs(tilt_y) < self.config.deadband:
            tilt_y = 0.0

        if tilt_x != 0.0:
            tilt_x = sign(tilt_x) * max(abs(tilt_x), self.config.min_tilt)
        if tilt_y != 0.0:
            tilt_y = sign(tilt_y) * max(abs(tilt_y), self.config.min_tilt)

        return (
            clamp(tilt_x, -self.config.max_tilt, self.config.max_tilt),
            clamp(tilt_y, -self.config.max_tilt, self.config.max_tilt),
        )
