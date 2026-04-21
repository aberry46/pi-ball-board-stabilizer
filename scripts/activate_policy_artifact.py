from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote a policy artifact to the active runtime policy path.")
    parser.add_argument(
        "policy_file",
        help="Path to the policy artifact to activate, for example artifacts/nn/policy_model.npz",
    )
    parser.add_argument(
        "--target",
        default="artifacts/nn/policy_model_active.npz",
        help="Active policy artifact path used by the runtime.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = Path(args.policy_file)
    target = Path(args.target)
    if not source.exists():
        print(f"Policy artifact not found: {source}")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(f"Activated policy artifact: {source} -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
