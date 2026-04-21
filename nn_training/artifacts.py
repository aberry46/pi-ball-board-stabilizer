from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .dataset import FEATURE_NAMES


def write_metadata(
    path: Path,
    *,
    model_type: str,
    history_steps: int,
    output_dim: int,
    source_path: str,
    extra: dict | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now().isoformat(),
        "model_type": model_type,
        "history_steps": history_steps,
        "feature_names": FEATURE_NAMES,
        "output_dim": output_dim,
        "source_path": source_path,
    }
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

