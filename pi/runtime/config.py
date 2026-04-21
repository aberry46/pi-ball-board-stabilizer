import json
import os
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class RuntimeConfig:
    camera_width: int = 960
    camera_height: int = 720
    process_width: int = 640
    process_height: int = 480
    camera_fps: int = 30
    camera_frame_timeout_s: float = 1.0
    camera_fault_after_misses: int = 25
    calibration_frames: int = 30
    safety_margin_ratio: float = 0.15

    red_low_1: tuple[int, int, int] = (0, 110, 60)
    red_high_1: tuple[int, int, int] = (12, 255, 255)
    red_low_2: tuple[int, int, int] = (168, 110, 60)
    red_high_2: tuple[int, int, int] = (180, 255, 255)
    morphology_open: int = 3
    morphology_close: int = 7
    min_blob_area: int = 90
    max_blob_area_ratio: float = 0.09
    min_confidence: float = 0.20

    kp_x: float = 1.00
    kp_y: float = 1.00
    ki_x: float = 0.010
    ki_y: float = 0.010
    kd_x: float = 0.16
    kd_y: float = 0.16
    max_tilt: float = 0.65
    min_tilt: float = 0.18
    deadband: float = 0.01
    integral_limit: float = 6.0
    lookahead_time_s: float = 0.12
    low_speed_threshold: float = 0.16
    low_speed_error_threshold: float = 0.06
    low_speed_tilt_boost: float = 0.26
    catch_velocity_threshold: float = 0.75
    catch_error_threshold: float = 0.35
    catch_multiplier: float = 1.0
    lost_track_grace_s: float = 0.10
    post_reacquire_warmup_s: float = 0.20
    control_bias_window: int = 18
    control_bias_min_mean: float = 0.22
    control_bias_dominance_ratio: float = 1.35
    control_bias_worsening_margin: float = 0.03
    control_recovery_neutral_s: float = 0.25

    swap_control_axes: bool = True
    invert_control_x: bool = False
    invert_control_y: bool = False

    serial_port: str = "/dev/ttyACM1"
    serial_baud: int = 115200
    serial_timeout_s: float = 0.1
    command_keepalive_s: float = 0.20

    controller_mode: str = "legacy"
    nn_history_steps: int = 8
    nn_dynamics_horizon: int = 5
    nn_policy_artifact_path: Path = Path("artifacts/nn/policy_model_active.npz")
    nn_dynamics_artifact_path: Path = Path("artifacts/nn/dynamics_model.npz")
    nn_normalization_path: Path = Path("artifacts/nn/normalization.json")
    nn_max_inference_ms: float = 20.0
    nn_min_ball_confidence: float = 0.75
    nn_near_edge_margin: float = 0.08
    edge_touch_dead_margin: float = 0.03
    nn_predicted_edge_margin: float = 0.06
    nn_edge_risk_threshold: float = 0.85
    nn_large_disagreement_threshold: float = 0.75
    nn_assist_blend: float = 0.35
    nn_assist_max_delta: float = 0.18
    nn_primary_max_delta: float = 0.35

    ipc_host: str = "127.0.0.1"
    ipc_port: int = 8765

    log_every_n_frames: int = 10
    snapshot_jpeg_quality: int = 75
    preview_fps: float = 2.0
    preview_running_fps: float = 0.0
    disable_preview_while_running: bool = True
    preview_max_width: int = 480
    preview_dir: Path = Path("/tmp/pi_ball_board_stabilizer")
    control_log_dir: Path = Path("runtime_data/control_logs")
    system_id_dir: Path = Path("runtime_data/system_id")
    local_override_path: Path = Path("runtime_data/local_runtime_config.json")

    @classmethod
    def load(cls) -> "RuntimeConfig":
        base = cls()
        override_path = Path(os.environ.get("PI_BALL_RUNTIME_CONFIG", str(base.local_override_path)))
        if not override_path.exists():
            return base

        payload = json.loads(override_path.read_text(encoding="utf-8"))
        valid_fields = {entry.name: entry for entry in fields(cls)}
        updates = {}
        for key, value in payload.items():
            if key not in valid_fields:
                continue
            field_info = valid_fields[key]
            if field_info.type is Path:
                updates[key] = Path(value)
            else:
                updates[key] = value
        return cls(**{**base.__dict__, **updates})
