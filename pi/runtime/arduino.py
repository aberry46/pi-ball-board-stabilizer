from __future__ import annotations

import serial

from .config import RuntimeConfig


class ArduinoLink:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.serial_port: serial.Serial | None = None

    def open(self) -> None:
        self.serial_port = serial.Serial(
            self.config.serial_port,
            self.config.serial_baud,
            timeout=self.config.serial_timeout_s,
        )

    def close(self) -> None:
        if self.serial_port is not None:
            self.serial_port.close()
            self.serial_port = None

    def send_center(self) -> str:
        return self.send("CENTER")

    def send_tilt(self, tilt_x: float, tilt_y: float) -> str:
        return self.send(f"TILT {tilt_x:.4f} {tilt_y:.4f}")

    def send(self, command: str) -> str:
        if self.serial_port is None:
            raise RuntimeError("Arduino serial link is not open")
        self.serial_port.write((command + "\n").encode("utf-8"))
        self.serial_port.flush()
        return command
