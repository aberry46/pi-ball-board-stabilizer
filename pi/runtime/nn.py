from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import RuntimeConfig
from .models import BallEstimate, ControllerMode, NeuralTelemetry


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def near_edge(center_norm: tuple[float, float] | None, margin: float) -> bool:
    if center_norm is None:
        return True
    x, y = center_norm
    return x <= margin or x >= (1.0 - margin) or y <= margin or y >= (1.0 - margin)


@dataclass
class StepFeatures:
    dt: float
    x: float
    y: float
    vx: float
    vy: float
    tilt_x: float
    tilt_y: float
    confidence: float
    distance_to_center: float
    speed: float
    near_edge: float

    def to_list(self) -> list[float]:
        return [
            self.dt,
            self.x,
            self.y,
            self.vx,
            self.vy,
            self.tilt_x,
            self.tilt_y,
            self.confidence,
            self.distance_to_center,
            self.speed,
            self.near_edge,
        ]


class Normalizer:
    def __init__(self, means: np.ndarray, stds: np.ndarray) -> None:
        self.means = means
        self.stds = np.where(stds == 0.0, 1.0, stds)

    @classmethod
    def from_path(cls, path: Path, feature_dim: int) -> "Normalizer":
        if not path.exists():
            return cls(np.zeros(feature_dim, dtype=np.float32), np.ones(feature_dim, dtype=np.float32))
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            np.asarray(payload.get("means", [0.0] * feature_dim), dtype=np.float32),
            np.asarray(payload.get("stds", [1.0] * feature_dim), dtype=np.float32),
        )

    def transform(self, values: np.ndarray) -> np.ndarray:
        return (values - self.means) / self.stds


class NumpyMLP:
    def __init__(self, path: Path) -> None:
        payload = np.load(path, allow_pickle=False)
        self.weights = []
        self.biases = []
        self.activation = str(payload["activation"].tolist())
        self.output_activation = str(payload["output_activation"].tolist())
        self.input_dim = int(payload["input_dim"])
        self.output_dim = int(payload["output_dim"])

        layer_count = int(payload["layer_count"])
        for idx in range(layer_count):
            self.weights.append(payload[f"W{idx}"].astype(np.float32))
            self.biases.append(payload[f"b{idx}"].astype(np.float32))

    def _activate(self, x: np.ndarray) -> np.ndarray:
        if self.activation == "silu":
            return x / (1.0 + np.exp(-x))
        return np.maximum(x, 0.0)

    def _activate_output(self, x: np.ndarray) -> np.ndarray:
        if self.output_activation == "tanh":
            return np.tanh(x)
        return x

    def __call__(self, inputs: np.ndarray) -> np.ndarray:
        x = inputs
        for idx, (w, b) in enumerate(zip(self.weights, self.biases)):
            x = x @ w + b
            if idx < len(self.weights) - 1:
                x = self._activate(x)
        return self._activate_output(x)


class FeatureWindow:
    def __init__(self, history_steps: int) -> None:
        self.history_steps = history_steps
        self.window: deque[StepFeatures] = deque(maxlen=history_steps)

    def reset(self) -> None:
        self.window.clear()

    def append(self, step: StepFeatures) -> None:
        self.window.append(step)

    def ready(self) -> bool:
        return len(self.window) == self.history_steps

    def flatten(self) -> np.ndarray:
        if not self.window:
            return np.zeros(0, dtype=np.float32)
        values = [entry.to_list() for entry in self.window]
        return np.asarray(values, dtype=np.float32).reshape(-1)


class NeuralController:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.mode = self._parse_mode(config.controller_mode)
        self.feature_dim = len(
            StepFeatures(
                dt=0.0,
                x=0.0,
                y=0.0,
                vx=0.0,
                vy=0.0,
                tilt_x=0.0,
                tilt_y=0.0,
                confidence=0.0,
                distance_to_center=0.0,
                speed=0.0,
                near_edge=0.0,
            ).to_list()
        )
        self.window = FeatureWindow(config.nn_history_steps)
        self.normalizer = Normalizer.from_path(config.nn_normalization_path, self.feature_dim * config.nn_history_steps)
        self.policy_model: NumpyMLP | None = None
        self.dynamics_model: NumpyMLP | None = None
        self.policy_loaded = False
        self.dynamics_loaded = False
        self._load_models()

    @property
    def model_loaded(self) -> bool:
        return self.policy_loaded and self.dynamics_loaded

    def _parse_mode(self, raw_mode: str) -> ControllerMode:
        try:
            return ControllerMode(raw_mode)
        except ValueError:
            return ControllerMode.LEGACY

    def _load_models(self) -> None:
        if self.config.nn_policy_artifact_path.exists():
            self.policy_model = NumpyMLP(self.config.nn_policy_artifact_path)
            self.policy_loaded = True
        if self.config.nn_dynamics_artifact_path.exists():
            self.dynamics_model = NumpyMLP(self.config.nn_dynamics_artifact_path)
            self.dynamics_loaded = True

    def reset(self) -> None:
        self.window.reset()

    def set_mode(self, mode: str) -> None:
        self.mode = self._parse_mode(mode)

    def update_history(self, ball: BallEstimate, tilt_x: float, tilt_y: float, dt: float) -> None:
        if not ball.found or ball.center_norm is None:
            return
        x, y = ball.center_norm
        vx, vy = ball.velocity_norm
        dist = float(np.hypot(0.5 - x, 0.5 - y))
        speed = float(np.hypot(vx, vy))
        step = StepFeatures(
            dt=dt,
            x=x,
            y=y,
            vx=vx,
            vy=vy,
            tilt_x=tilt_x,
            tilt_y=tilt_y,
            confidence=ball.confidence,
            distance_to_center=dist,
            speed=speed,
            near_edge=1.0 if near_edge(ball.center_norm, self.config.nn_near_edge_margin) else 0.0,
        )
        self.window.append(step)

    def infer(self, ball: BallEstimate, legacy_tilt_x: float, legacy_tilt_y: float, dt: float) -> tuple[tuple[float, float], NeuralTelemetry]:
        self.update_history(ball, legacy_tilt_x, legacy_tilt_y, dt)
        telemetry = NeuralTelemetry(
            enabled=self.mode != ControllerMode.LEGACY,
            mode=self.mode.value,
            model_loaded=self.model_loaded,
        )
        if self.mode == ControllerMode.LEGACY:
            telemetry.fallback_reason = "legacy mode"
            return (legacy_tilt_x, legacy_tilt_y), telemetry
        if not telemetry.model_loaded:
            telemetry.fallback_reason = "model missing"
            return (legacy_tilt_x, legacy_tilt_y), telemetry
        if not ball.found or ball.center_norm is None or ball.confidence < self.config.nn_min_ball_confidence:
            telemetry.fallback_reason = "low confidence"
            return (legacy_tilt_x, legacy_tilt_y), telemetry
        if near_edge(ball.center_norm, self.config.nn_near_edge_margin):
            telemetry.fallback_reason = "near edge"
            return (legacy_tilt_x, legacy_tilt_y), telemetry
        if not self.window.ready():
            telemetry.fallback_reason = "history warming up"
            return (legacy_tilt_x, legacy_tilt_y), telemetry

        start = time.perf_counter()
        features = self.normalizer.transform(self.window.flatten())[None, :]
        policy_out = self.policy_model(features)[0] if self.policy_model is not None else np.zeros(2, dtype=np.float32)
        if self.dynamics_model is not None:
            dynamics_out = self.dynamics_model(features)[0]
            telemetry.edge_risk = self._estimate_edge_risk(ball, dynamics_out)
        inference_ms = (time.perf_counter() - start) * 1000.0
        telemetry.inference_ms = inference_ms
        telemetry.policy_tilt = (float(policy_out[0]), float(policy_out[1]))
        telemetry.disagreement = float(np.hypot(policy_out[0] - legacy_tilt_x, policy_out[1] - legacy_tilt_y))

        if inference_ms > self.config.nn_max_inference_ms:
            telemetry.fallback_reason = "inference timeout"
            return (legacy_tilt_x, legacy_tilt_y), telemetry
        if telemetry.edge_risk > 0.5:
            telemetry.fallback_reason = "predicted edge risk"
            return (legacy_tilt_x, legacy_tilt_y), telemetry

        if self.mode == ControllerMode.NN_SHADOW:
            telemetry.fallback_reason = "shadow mode"
            return (legacy_tilt_x, legacy_tilt_y), telemetry

        if self.mode == ControllerMode.NN_ASSIST:
            bounded_dx = clamp(float(policy_out[0]) - legacy_tilt_x, -self.config.nn_assist_max_delta, self.config.nn_assist_max_delta)
            bounded_dy = clamp(float(policy_out[1]) - legacy_tilt_y, -self.config.nn_assist_max_delta, self.config.nn_assist_max_delta)
            assisted = (
                clamp(legacy_tilt_x + self.config.nn_assist_blend * bounded_dx, -1.0, 1.0),
                clamp(legacy_tilt_y + self.config.nn_assist_blend * bounded_dy, -1.0, 1.0),
            )
            telemetry.active = True
            return assisted, telemetry

        if self.mode == ControllerMode.NN_PRIMARY:
            primary = (
                clamp(legacy_tilt_x + clamp(float(policy_out[0]) - legacy_tilt_x, -self.config.nn_primary_max_delta, self.config.nn_primary_max_delta), -1.0, 1.0),
                clamp(legacy_tilt_y + clamp(float(policy_out[1]) - legacy_tilt_y, -self.config.nn_primary_max_delta, self.config.nn_primary_max_delta), -1.0, 1.0),
            )
            telemetry.active = True
            return primary, telemetry

        telemetry.fallback_reason = "unknown mode"
        return (legacy_tilt_x, legacy_tilt_y), telemetry

    def _estimate_edge_risk(self, ball: BallEstimate, dynamics_out: np.ndarray) -> float:
        if ball.center_norm is None:
            return 1.0
        x0, y0 = ball.center_norm
        horizon_steps = max(1, len(dynamics_out) // 4)
        risk = 0.0
        for step in range(horizon_steps):
            dx = float(dynamics_out[step * 4 + 0])
            dy = float(dynamics_out[step * 4 + 1])
            future_x = x0 + dx
            future_y = y0 + dy
            if near_edge((future_x, future_y), self.config.nn_near_edge_margin):
                risk = 1.0
                break
        return risk
