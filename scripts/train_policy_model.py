from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nn_training.artifacts import write_metadata
from nn_training.dataset import build_feature_matrix, build_policy_dataset, load_sessions, train_val_split
from nn_training.mlp import Normalization, SimpleMLP


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the neural policy model from runtime control logs.")
    parser.add_argument("--data", default="runtime_data/control_logs", help="Directory or JSONL file of control traces.")
    parser.add_argument("--output-dir", default="artifacts/nn", help="Artifact output directory.")
    parser.add_argument("--history-steps", type=int, default=8, help="History steps per sample.")
    parser.add_argument("--epochs", type=int, default=300, help="Training epochs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_path = Path(args.data)
    sessions = load_sessions(data_path)
    inputs, targets = build_policy_dataset(sessions, args.history_steps)
    if len(inputs) == 0:
        print("No usable policy samples found.")
        return 1

    train_x, train_y, val_x, val_y = train_val_split(inputs, targets)
    normalization_source = build_feature_matrix(sessions, args.history_steps)
    normalizer = Normalization.fit(normalization_source if len(normalization_source) else train_x)
    train_x = normalizer.transform(train_x)
    val_x = normalizer.transform(val_x)

    model = SimpleMLP(
        input_dim=train_x.shape[1],
        hidden_dims=[64, 64, 64],
        output_dim=train_y.shape[1],
        activation="silu",
        output_activation="tanh",
    )
    result = model.train(train_x, train_y, val_x, val_y, epochs=args.epochs)

    output_dir = Path(args.output_dir)
    model_path = output_dir / "policy_model.npz"
    norm_path = output_dir / "normalization.json"
    metadata_path = output_dir / "policy_metadata.json"
    model.save(model_path)
    normalizer.save(norm_path)
    write_metadata(
        metadata_path,
        model_type="policy",
        history_steps=args.history_steps,
        output_dim=train_y.shape[1],
        source_path=str(data_path),
        extra={"epochs": args.epochs, "train_loss": result.train_loss, "val_loss": result.val_loss},
    )
    print(f"Saved policy model to {model_path}")
    print(f"Train loss: {result.train_loss:.6f}")
    print(f"Val loss:   {result.val_loss:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
