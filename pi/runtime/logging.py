from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ControlTraceRecord:
    timestamp: float
    session_id: str
    mode: str
    controller_mode: str
    ball_found: bool
    x: float | None
    y: float | None
    vx: float
    vy: float
    confidence: float
    near_edge: bool
    ball_lost: bool
    tilt_x: float
    tilt_y: float
    sent_command: str
    command_source: str
    command_clamped: bool
    legacy_tilt_x: float
    legacy_tilt_y: float
    nn_tilt_x: float
    nn_tilt_y: float
    nn_enabled: bool
    nn_mode: str
    nn_active: bool
    nn_inference_ms: float
    nn_disagreement: float
    nn_edge_risk: float
    nn_fallback_reason: str | None
    board_corners: list[tuple[float, float]]
    board_initialized: bool
    experiment_tag: str | None = None


class ControlTraceLogger:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        self.path = self.base_dir / f"session_{self.session_id}.jsonl"
        self._handle = self.path.open("a", encoding="utf-8")

    def log(self, record: ControlTraceRecord) -> None:
        self._handle.write(json.dumps(asdict(record)) + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()
