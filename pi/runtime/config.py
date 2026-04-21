from dataclasses import dataclass
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

    kp_x: float = 1.2
    kp_y: float = 1.2
    kd_x: float = 0.20
    kd_y: float = 0.20
    max_tilt: float = 1.0
    min_tilt: float = 0.00
    deadband: float = 0.05
    catch_velocity_threshold: float = 0.80
    catch_error_threshold: float = 0.28
    catch_multiplier: float = 1.10
    lost_track_grace_s: float = 0.35

    swap_control_axes: bool = False
    invert_control_x: bool = True
    invert_control_y: bool = True

    serial_port: str = "/dev/ttyACM1"
    serial_baud: int = 115200
    serial_timeout_s: float = 0.1

    ipc_host: str = "127.0.0.1"
    ipc_port: int = 8765

    log_every_n_frames: int = 10
    snapshot_jpeg_quality: int = 75
    preview_dir: Path = Path("/tmp/pi_ball_board_stabilizer")
