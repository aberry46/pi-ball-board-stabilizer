from __future__ import annotations

import time

import serial

from .config import RuntimeConfig


class ArduinoLink:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.serial_port: serial.Serial | None = None
        self.last_tilt_x = 0.0
        self.last_tilt_y = 0.0
        self.last_command = "CENTER"
        self.last_send_time = 0.0

    def open(self) -> None:
        self.serial_port = serial.Serial(
            self.config.serial_port,
            self.config.serial_baud,
            timeout=self.config.serial_timeout_s,
        )
        self.last_tilt_x = 0.0
        self.last_tilt_y = 0.0
        self.last_command = "CENTER"
        self.last_send_time = 0.0

    def close(self) -> None:
        if self.serial_port is not None:
            self.serial_port.close()
            self.serial_port = None

    def send_center(self) -> str:
        now = time.time()
        if self.last_command == "CENTER" and (now - self.last_send_time) < self.config.command_keepalive_s:
            return self.last_command
        self.last_tilt_x = 0.0
        self.last_tilt_y = 0.0
        return self.send("CENTER")

    def send_tilt(self, tilt_x: float, tilt_y: float) -> str:
        now = time.time()
        if (
            self.last_command.startswith("TILT ")
            and abs(tilt_x - self.last_tilt_x) < 0.02
            and abs(tilt_y - self.last_tilt_y) < 0.02
            and (now - self.last_send_time) < self.config.command_keepalive_s
        ):
            return self.last_command
        self.last_tilt_x = tilt_x
        self.last_tilt_y = tilt_y
        return self.send(f"TILT {tilt_x:.4f} {tilt_y:.4f}")

    def send(self, command: str) -> str:
        if self.serial_port is None:
            raise RuntimeError("Arduino serial link is not open")
        self.serial_port.write((command + "\n").encode("utf-8"))
        self.serial_port.flush()
        self.last_command = command
        self.last_send_time = time.time()
        return command
