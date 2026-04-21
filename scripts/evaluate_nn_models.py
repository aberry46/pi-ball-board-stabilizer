from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from nn_training.dataset import build_dynamics_dataset, build_policy_dataset, load_sessions_from_paths
from nn_training.mlp import Normalization, mse
from pi.runtime.nn import NumpyMLP


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate trained NN artifacts against held-out logs.")
    parser.add_argument(
        "--data",
        nargs="+",
        default=["runtime_data/control_logs", "runtime_data/system_id"],
        help="One or more directories or JSONL files of control traces.",
    )
    parser.add_argument("--artifacts", default="artifacts/nn", help="Artifact directory.")
    parser.add_argument("--policy-file", default="policy_model.npz", help="Policy artifact filename to evaluate.")
    parser.add_argument("--history-steps", type=int, default=8)
    parser.add_argument("--horizon", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_paths = [Path(entry) for entry in args.data]
    artifact_dir = Path(args.artifacts)
    sessions = load_sessions_from_paths(data_paths)
    normalization_path = artifact_dir / "normalization.json"
    if not normalization_path.exists():
        print(f"No normalization artifact found at {normalization_path}")
        return 1

    norm_payload = json.loads(normalization_path.read_text(encoding="utf-8"))
    normalizer = Normalization(
        np.asarray(norm_payload["means"], dtype=np.float32),
        np.asarray(norm_payload["stds"], dtype=np.float32),
    )

    dyn_x, dyn_y = build_dynamics_dataset(sessions, args.history_steps, args.horizon)
    pol_x, pol_y = build_policy_dataset(sessions, args.history_steps)
    if len(dyn_x) == 0 and len(pol_x) == 0:
        print("No evaluation samples found in:", ", ".join(str(path) for path in data_paths))
        return 1

    if (artifact_dir / "dynamics_model.npz").exists() and len(dyn_x):
        dynamics = NumpyMLP(artifact_dir / "dynamics_model.npz")
        dyn_pred = dynamics(normalizer.transform(dyn_x))
        print(f"Dynamics MSE: {mse(dyn_pred, dyn_y):.6f}")

    policy_path = artifact_dir / args.policy_file
    if policy_path.exists() and len(pol_x):
        policy = NumpyMLP(policy_path)
        pol_pred = policy(normalizer.transform(pol_x))
        print(f"Policy file: {policy_path.name}")
        print(f"Policy imitation MSE: {mse(pol_pred, pol_y):.6f}")
        print(f"Mean policy disagreement: {float(np.mean(np.linalg.norm(pol_pred - pol_y, axis=1))):.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
