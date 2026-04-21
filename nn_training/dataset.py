from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


FEATURE_NAMES = [
    "dt",
    "x",
    "y",
    "vx",
    "vy",
    "tilt_x",
    "tilt_y",
    "confidence",
    "distance_to_center",
    "speed",
    "near_edge",
]


@dataclass
class SessionData:
    path: Path
    rows: list[dict]


def load_sessions(path: Path) -> list[SessionData]:
    files = [path] if path.is_file() else sorted(path.glob("*.jsonl"))
    sessions: list[SessionData] = []
    for file_path in files:
        rows: list[dict] = []
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        if rows:
            sessions.append(SessionData(path=file_path, rows=rows))
    return sessions


def load_sessions_from_paths(paths: list[Path]) -> list[SessionData]:
    sessions: list[SessionData] = []
    for path in paths:
        sessions.extend(load_sessions(path))
    return sessions


def row_to_feature(row: dict, dt: float) -> np.ndarray:
    x = row.get("x", 0.5) if row.get("x") is not None else 0.5
    y = row.get("y", 0.5) if row.get("y") is not None else 0.5
    vx = float(row.get("vx", 0.0))
    vy = float(row.get("vy", 0.0))
    tilt_x = float(row.get("tilt_x", 0.0))
    tilt_y = float(row.get("tilt_y", 0.0))
    confidence = float(row.get("confidence", 0.0))
    distance_to_center = float(np.hypot(0.5 - x, 0.5 - y))
    speed = float(np.hypot(vx, vy))
    near_edge = 1.0 if bool(row.get("near_edge", False)) else 0.0
    return np.asarray(
        [dt, x, y, vx, vy, tilt_x, tilt_y, confidence, distance_to_center, speed, near_edge],
        dtype=np.float32,
    )


def _valid_row(row: dict) -> bool:
    return bool(row.get("ball_found")) and row.get("x") is not None and row.get("y") is not None


def build_dynamics_dataset(
    sessions: list[SessionData],
    history_steps: int,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    inputs: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    for session in sessions:
        rows = session.rows
        for index in range(history_steps, len(rows) - horizon):
            history_rows = rows[index - history_steps : index]
            future_rows = rows[index : index + horizon]
            if not all(_valid_row(row) for row in history_rows + future_rows):
                continue
            if any(bool(row.get("near_edge", False)) for row in future_rows):
                continue

            history_features = []
            prev_ts = None
            for row in history_rows:
                ts = float(row["timestamp"])
                dt = 0.0 if prev_ts is None else max(1e-3, ts - prev_ts)
                history_features.append(row_to_feature(row, dt))
                prev_ts = ts

            anchor = history_rows[-1]
            anchor_x = float(anchor["x"])
            anchor_y = float(anchor["y"])
            anchor_vx = float(anchor["vx"])
            anchor_vy = float(anchor["vy"])

            future_targets = []
            for row in future_rows:
                future_targets.extend(
                    [
                        float(row["x"]) - anchor_x,
                        float(row["y"]) - anchor_y,
                        float(row["vx"]) - anchor_vx,
                        float(row["vy"]) - anchor_vy,
                    ]
                )

            inputs.append(np.concatenate(history_features))
            targets.append(np.asarray(future_targets, dtype=np.float32))

    if not inputs:
        return (
            np.zeros((0, history_steps * len(FEATURE_NAMES)), dtype=np.float32),
            np.zeros((0, horizon * 4), dtype=np.float32),
        )
    return np.stack(inputs).astype(np.float32), np.stack(targets).astype(np.float32)


def build_feature_matrix(
    sessions: list[SessionData],
    history_steps: int,
) -> np.ndarray:
    features: list[np.ndarray] = []
    for session in sessions:
        rows = session.rows
        for index in range(history_steps, len(rows) + 1):
            history_rows = rows[index - history_steps : index]
            if not all(_valid_row(row) for row in history_rows):
                continue
            history_features = []
            prev_ts = None
            for row in history_rows:
                ts = float(row["timestamp"])
                dt = 0.0 if prev_ts is None else max(1e-3, ts - prev_ts)
                history_features.append(row_to_feature(row, dt))
                prev_ts = ts
            features.append(np.concatenate(history_features))
    if not features:
        return np.zeros((0, history_steps * len(FEATURE_NAMES)), dtype=np.float32)
    return np.stack(features).astype(np.float32)


def build_policy_dataset(
    sessions: list[SessionData],
    history_steps: int,
) -> tuple[np.ndarray, np.ndarray]:
    inputs: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    for session in sessions:
        rows = session.rows
        for index in range(history_steps, len(rows)):
            history_rows = rows[index - history_steps : index]
            row = rows[index]
            if not _valid_row(row) or not all(_valid_row(entry) for entry in history_rows):
                continue

            history_features = []
            prev_ts = None
            for entry in history_rows:
                ts = float(entry["timestamp"])
                dt = 0.0 if prev_ts is None else max(1e-3, ts - prev_ts)
                history_features.append(row_to_feature(entry, dt))
                prev_ts = ts

            teacher = np.asarray(
                [
                    float(row.get("legacy_tilt_x", row.get("tilt_x", 0.0))),
                    float(row.get("legacy_tilt_y", row.get("tilt_y", 0.0))),
                ],
                dtype=np.float32,
            )
            inputs.append(np.concatenate(history_features))
            targets.append(teacher)

    if not inputs:
        return (
            np.zeros((0, history_steps * len(FEATURE_NAMES)), dtype=np.float32),
            np.zeros((0, 2), dtype=np.float32),
        )
    return np.stack(inputs).astype(np.float32), np.stack(targets).astype(np.float32)


def train_val_split(
    inputs: np.ndarray,
    targets: np.ndarray,
    validation_ratio: float = 0.2,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if len(inputs) == 0:
        return inputs, targets, inputs, targets
    split_index = max(1, int(round(len(inputs) * (1.0 - validation_ratio))))
    split_index = min(split_index, len(inputs) - 1) if len(inputs) > 1 else 1
    return (
        inputs[:split_index],
        targets[:split_index],
        inputs[split_index:],
        targets[split_index:],
    )
