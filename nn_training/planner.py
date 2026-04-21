from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dataset import FEATURE_NAMES
from .mlp import Normalization
from pi.runtime.nn import NumpyMLP


@dataclass
class PlannerConfig:
    history_steps: int = 8
    rollout_steps: int = 3
    max_tilt: float = 0.65
    candidate_levels: tuple[float, ...] = (-1.0, 0.0, 1.0)
    position_weight: float = 4.0
    speed_weight: float = 3.5
    edge_weight: float = 10.0
    acceleration_weight: float = 1.5
    command_weight: float = 0.2
    command_delta_weight: float = 0.15
    center_speed_weight: float = 4.0
    edge_margin: float = 0.08


def feature_index(name: str) -> int:
    return FEATURE_NAMES.index(name)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def near_edge(x: float, y: float, margin: float) -> bool:
    return x <= margin or x >= (1.0 - margin) or y <= margin or y >= (1.0 - margin)


class LearnedDynamicsPlanner:
    def __init__(
        self,
        *,
        dynamics_model: NumpyMLP,
        normalizer: Normalization,
        config: PlannerConfig,
    ) -> None:
        self.dynamics_model = dynamics_model
        self.normalizer = normalizer
        self.config = config
        self.feature_dim = len(FEATURE_NAMES)
        self.idx_dt = feature_index("dt")
        self.idx_x = feature_index("x")
        self.idx_y = feature_index("y")
        self.idx_vx = feature_index("vx")
        self.idx_vy = feature_index("vy")
        self.idx_tilt_x = feature_index("tilt_x")
        self.idx_tilt_y = feature_index("tilt_y")
        self.idx_conf = feature_index("confidence")
        self.idx_dist = feature_index("distance_to_center")
        self.idx_speed = feature_index("speed")
        self.idx_edge = feature_index("near_edge")
        self.candidate_actions = self._build_candidate_actions()

    def _build_candidate_actions(self) -> list[tuple[float, float]]:
        actions: list[tuple[float, float]] = []
        for x_scale in self.config.candidate_levels:
            for y_scale in self.config.candidate_levels:
                actions.append((x_scale * self.config.max_tilt, y_scale * self.config.max_tilt))
        return actions

    @classmethod
    def from_profile(
        cls,
        *,
        history_steps: int,
        rollout_steps: int,
        max_tilt: float,
        profile: str,
    ) -> "PlannerConfig":
        profiles = {
            "fast": (-1.0, 0.0, 1.0),
            "balanced": (-1.0, -0.5, 0.0, 0.5, 1.0),
            "dense": (-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0),
        }
        return cls(
            history_steps=history_steps,
            rollout_steps=rollout_steps,
            max_tilt=max_tilt,
            candidate_levels=profiles.get(profile, profiles["fast"]),
        )

    def choose_action(self, history: np.ndarray) -> tuple[float, float]:
        if history.shape[0] != self.config.history_steps or history.shape[1] != self.feature_dim:
            raise ValueError("history shape does not match planner configuration")

        best_action = (0.0, 0.0)
        best_cost = float("inf")
        for action in self.candidate_actions:
            cost = self._rollout_cost(history.copy(), action)
            if cost < best_cost:
                best_cost = cost
                best_action = action
        return best_action

    def _rollout_cost(self, history: np.ndarray, first_action: tuple[float, float]) -> float:
        cumulative_cost = 0.0
        action = first_action
        prev_action = (
            float(history[-1, self.idx_tilt_x]),
            float(history[-1, self.idx_tilt_y]),
        )
        rollout_history = history.copy()
        for step in range(self.config.rollout_steps):
            predicted = self._predict_next_state(rollout_history, action)
            cumulative_cost += self._state_cost(predicted, action, prev_action, step)
            prev_action = action
            rollout_history = np.vstack([rollout_history[1:], self._state_to_feature(predicted, action, rollout_history[-1, self.idx_dt])])
            action = self._greedy_followup(rollout_history, prev_action)
        return cumulative_cost

    def _predict_next_state(self, history: np.ndarray, action: tuple[float, float]) -> dict[str, float]:
        working = history.copy()
        working[-1, self.idx_tilt_x] = action[0]
        working[-1, self.idx_tilt_y] = action[1]
        normalized = self.normalizer.transform(working.reshape(1, -1))
        deltas = self.dynamics_model(normalized)[0]
        anchor = working[-1]
        dx, dy, dvx, dvy = [float(value) for value in deltas[:4]]
        x = float(anchor[self.idx_x] + dx)
        y = float(anchor[self.idx_y] + dy)
        vx = float(anchor[self.idx_vx] + dvx)
        vy = float(anchor[self.idx_vy] + dvy)
        return {"x": x, "y": y, "vx": vx, "vy": vy}

    def _state_to_feature(self, state: dict[str, float], action: tuple[float, float], dt: float) -> np.ndarray:
        x = clamp(state["x"], 0.0, 1.0)
        y = clamp(state["y"], 0.0, 1.0)
        vx = state["vx"]
        vy = state["vy"]
        dist = float(np.hypot(0.5 - x, 0.5 - y))
        speed = float(np.hypot(vx, vy))
        return np.asarray(
            [
                dt,
                x,
                y,
                vx,
                vy,
                action[0],
                action[1],
                1.0,
                dist,
                speed,
                1.0 if near_edge(x, y, self.config.edge_margin) else 0.0,
            ],
            dtype=np.float32,
        )

    def _state_cost(
        self,
        state: dict[str, float],
        action: tuple[float, float],
        prev_action: tuple[float, float],
        step: int,
    ) -> float:
        x = state["x"]
        y = state["y"]
        vx = state["vx"]
        vy = state["vy"]
        distance = float(np.hypot(0.5 - x, 0.5 - y))
        speed = float(np.hypot(vx, vy))
        edge_penalty = 1.0 if near_edge(x, y, self.config.edge_margin) else 0.0
        accel_penalty = max(0.0, speed - 0.12)
        center_speed_penalty = speed if distance < 0.18 else 0.0
        action_mag = float(np.hypot(action[0], action[1]))
        action_delta = float(np.hypot(action[0] - prev_action[0], action[1] - prev_action[1]))
        horizon_discount = 1.0 - 0.15 * step
        return horizon_discount * (
            self.config.position_weight * distance * distance
            + self.config.speed_weight * speed * speed
            + self.config.edge_weight * edge_penalty
            + self.config.acceleration_weight * accel_penalty * accel_penalty
            + self.config.center_speed_weight * center_speed_penalty * center_speed_penalty
            + self.config.command_weight * action_mag * action_mag
            + self.config.command_delta_weight * action_delta * action_delta
        )

    def _greedy_followup(self, history: np.ndarray, prev_action: tuple[float, float]) -> tuple[float, float]:
        best_action = (0.0, 0.0)
        best_cost = float("inf")
        for action in self.candidate_actions:
            predicted = self._predict_next_state(history, action)
            cost = self._state_cost(predicted, action, prev_action, 0)
            if cost < best_cost:
                best_cost = cost
                best_action = action
        return best_action
