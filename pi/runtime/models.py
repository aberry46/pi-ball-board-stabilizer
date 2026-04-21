from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class RuntimeMode(str, Enum):
    STOPPED = "STOPPED"
    CALIBRATING = "CALIBRATING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAULT = "FAULT"


@dataclass
class BoardCalibration:
    corners: list[tuple[float, float]] = field(default_factory=list)
    center_norm: tuple[float, float] = (0.5, 0.5)
    safety_margin_ratio: float = 0.15
    initialized: bool = False
    progress: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BallEstimate:
    found: bool = False
    center_px: Optional[tuple[int, int]] = None
    center_norm: Optional[tuple[float, float]] = None
    velocity_norm: tuple[float, float] = (0.0, 0.0)
    radius_px: float = 0.0
    area_px: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ControlOutput:
    tilt_x: float = 0.0
    tilt_y: float = 0.0
    sent_command: str = "CENTER"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RuntimeSnapshot:
    mode: RuntimeMode = RuntimeMode.STOPPED
    board: BoardCalibration = field(default_factory=BoardCalibration)
    ball: BallEstimate = field(default_factory=BallEstimate)
    control: ControlOutput = field(default_factory=ControlOutput)
    fps: float = 0.0
    frame_age_ms: float = 0.0
    last_error: Optional[str] = None
    raw_frame_b64: Optional[str] = None
    mask_frame_b64: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "board": self.board.to_dict(),
            "ball": self.ball.to_dict(),
            "control": self.control.to_dict(),
            "fps": self.fps,
            "frame_age_ms": self.frame_age_ms,
            "last_error": self.last_error,
            "raw_frame_b64": self.raw_frame_b64,
            "mask_frame_b64": self.mask_frame_b64,
        }
