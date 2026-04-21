from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from nn_training.artifacts import write_metadata
from nn_training.dataset import FEATURE_NAMES, build_feature_matrix, load_sessions_from_paths, row_to_feature, train_val_split
from nn_training.mlp import Normalization, SimpleMLP
from nn_training.planner import LearnedDynamicsPlanner, PlannerConfig
from pi.runtime.nn import NumpyMLP


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a policy from planner-generated teacher actions.")
    parser.add_argument(
        "--data",
        nargs="+",
        default=["runtime_data/control_logs", "runtime_data/system_id"],
        help="One or more directories or JSONL files of control traces.",
    )
    parser.add_argument("--artifacts", default="artifacts/nn", help="Artifact directory containing dynamics model and normalization.")
    parser.add_argument("--output-dir", default="artifacts/nn", help="Artifact output directory.")
    parser.add_argument("--history-steps", type=int, default=8, help="History steps per sample.")
    parser.add_argument("--epochs", type=int, default=300, help="Training epochs.")
    parser.add_argument("--rollout-steps", type=int, default=3, help="Planner rollout depth.")
    return parser.parse_args()


def build_planner_dataset(
    sessions,
    history_steps: int,
    planner: LearnedDynamicsPlanner,
) -> tuple[np.ndarray, np.ndarray]:
    inputs: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    feature_dim = len(FEATURE_NAMES)
    for session in sessions:
        rows = session.rows
        for index in range(history_steps, len(rows)):
            history_rows = rows[index - history_steps : index]
            current_row = rows[index]
            if not bool(current_row.get("ball_found")) or current_row.get("x") is None or current_row.get("y") is None:
                continue
            if not all(bool(row.get("ball_found")) and row.get("x") is not None and row.get("y") is not None for row in history_rows):
                continue

            history_features = []
            prev_ts = None
            for row in history_rows:
                ts = float(row["timestamp"])
                dt = 0.0 if prev_ts is None else max(1e-3, ts - prev_ts)
                history_features.append(row_to_feature(row, dt))
                prev_ts = ts

            history_matrix = np.asarray(history_features, dtype=np.float32).reshape(history_steps, feature_dim)
            teacher = planner.choose_action(history_matrix)
            inputs.append(history_matrix.reshape(-1))
            targets.append(np.asarray(teacher, dtype=np.float32))

    if not inputs:
        return (
            np.zeros((0, history_steps * feature_dim), dtype=np.float32),
            np.zeros((0, 2), dtype=np.float32),
        )
    return np.stack(inputs).astype(np.float32), np.stack(targets).astype(np.float32)


def main() -> int:
    args = parse_args()
    data_paths = [Path(entry) for entry in args.data]
    artifact_dir = Path(args.artifacts)
    dynamics_path = artifact_dir / "dynamics_model.npz"
    normalization_path = artifact_dir / "normalization.json"
    if not dynamics_path.exists():
        print(f"No dynamics model found at {dynamics_path}")
        return 1
    if not normalization_path.exists():
        print(f"No normalization artifact found at {normalization_path}")
        return 1

    norm_payload = json.loads(normalization_path.read_text(encoding="utf-8"))
    normalizer = Normalization(
        np.asarray(norm_payload["means"], dtype=np.float32),
        np.asarray(norm_payload["stds"], dtype=np.float32),
    )
    dynamics_model = NumpyMLP(dynamics_path)
    planner = LearnedDynamicsPlanner(
        dynamics_model=dynamics_model,
        normalizer=normalizer,
        config=PlannerConfig(history_steps=args.history_steps, rollout_steps=args.rollout_steps),
    )

    sessions = load_sessions_from_paths(data_paths)
    inputs, targets = build_planner_dataset(sessions, args.history_steps, planner)
    if len(inputs) == 0:
        print("No usable planner policy samples found in:", ", ".join(str(path) for path in data_paths))
        return 1

    train_x, train_y, val_x, val_y = train_val_split(inputs, targets)
    normalization_source = build_feature_matrix(sessions, args.history_steps)
    feature_normalizer = Normalization.fit(normalization_source if len(normalization_source) else train_x)
    train_x = feature_normalizer.transform(train_x)
    val_x = feature_normalizer.transform(val_x)

    model = SimpleMLP(
        input_dim=train_x.shape[1],
        hidden_dims=[64, 64, 64],
        output_dim=train_y.shape[1],
        activation="silu",
        output_activation="tanh",
    )
    result = model.train(train_x, train_y, val_x, val_y, epochs=args.epochs)

    output_dir = Path(args.output_dir)
    model_path = output_dir / "policy_model_planner.npz"
    metadata_path = output_dir / "policy_planner_metadata.json"
    model.save(model_path)
    feature_normalizer.save(output_dir / "normalization.json")
    write_metadata(
        metadata_path,
        model_type="policy_planner",
        history_steps=args.history_steps,
        output_dim=train_y.shape[1],
        source_path=", ".join(str(path) for path in data_paths),
        extra={
            "epochs": args.epochs,
            "rollout_steps": args.rollout_steps,
            "train_loss": result.train_loss,
            "val_loss": result.val_loss,
        },
    )
    print(f"Saved planner-trained policy model to {model_path}")
    print(f"Train loss: {result.train_loss:.6f}")
    print(f"Val loss:   {result.val_loss:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
