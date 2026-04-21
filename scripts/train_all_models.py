from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the full neural stack in sequence.")
    parser.add_argument(
        "--data",
        nargs="+",
        default=["runtime_data/control_logs", "runtime_data/system_id"],
        help="One or more directories or JSONL files of control traces.",
    )
    parser.add_argument("--output-dir", default="artifacts/nn", help="Artifact directory.")
    parser.add_argument("--history-steps", type=int, default=8, help="History steps per sample.")
    parser.add_argument("--horizon", type=int, default=5, help="Dynamics prediction horizon.")
    parser.add_argument("--epochs", type=int, default=300, help="Training epochs for each model.")
    parser.add_argument("--with-planner", action="store_true", help="Also train a planner-distilled policy.")
    parser.add_argument("--planner-profile", choices=["fast", "balanced", "dense"], default="fast")
    parser.add_argument("--sample-stride", type=int, default=2, help="Use every Nth planner sample.")
    return parser.parse_args()


def run_step(command: list[str], cwd: Path) -> None:
    print()
    print("$ " + " ".join(shlex.quote(part) for part in command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    python_bin = sys.executable
    data_args = [str(path) for path in args.data]

    run_step(
        [
            python_bin,
            "scripts/train_dynamics_model.py",
            "--output-dir",
            args.output_dir,
            "--history-steps",
            str(args.history_steps),
            "--horizon",
            str(args.horizon),
            "--epochs",
            str(args.epochs),
            "--data",
            *data_args,
        ],
        root,
    )
    run_step(
        [
            python_bin,
            "scripts/train_policy_model.py",
            "--output-dir",
            args.output_dir,
            "--history-steps",
            str(args.history_steps),
            "--epochs",
            str(args.epochs),
            "--data",
            *data_args,
        ],
        root,
    )
    if args.with_planner:
        run_step(
            [
                python_bin,
                "scripts/train_policy_with_planner.py",
                "--artifacts",
                args.output_dir,
                "--output-dir",
                args.output_dir,
                "--history-steps",
                str(args.history_steps),
                "--epochs",
                str(args.epochs),
                "--planner-profile",
                args.planner_profile,
                "--sample-stride",
                str(args.sample_stride),
                "--data",
                *data_args,
            ],
            root,
        )
    print()
    print("Training pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
