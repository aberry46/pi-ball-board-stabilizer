from __future__ import annotations

import argparse
import sys
import time

import serial


TESTS = [
    ("CENTER", "Board should return to neutral."),
    ("TILT 1.00 0.00", "Observe which physical tilt direction Arduino X+ produces."),
    ("CENTER", "Board should return to neutral."),
    ("TILT -1.00 0.00", "Observe which physical tilt direction Arduino X- produces."),
    ("CENTER", "Board should return to neutral."),
    ("TILT 0.00 1.00", "Observe which physical tilt direction Arduino Y+ produces."),
    ("CENTER", "Board should return to neutral."),
    ("TILT 0.00 -1.00", "Observe which physical tilt direction Arduino Y- produces."),
    ("CENTER", "Board should return to neutral."),
]


def wait_for_enter(prompt: str) -> None:
    try:
        input(prompt)
    except EOFError:
        pass


def read_serial_lines(ser: serial.Serial, duration_s: float) -> None:
    end = time.time() + duration_s
    while time.time() < end:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            print(f"Arduino: {line}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manual calibration helper for board axis and sign mapping."
    )
    parser.add_argument("--port", default="/dev/ttyACM1", help="Arduino serial port")
    parser.add_argument("--baud", type=int, default=115200, help="Arduino serial baud rate")
    parser.add_argument(
        "--pause",
        type=float,
        default=1.5,
        help="Seconds to wait after each command while reading Arduino output",
    )
    args = parser.parse_args()

    print("Axis Mapping Test")
    print("-----------------")
    print("1. Make sure the runtime is stopped before using this.")
    print("2. Watch the board, not the terminal.")
    print("3. Write down what physical motion each command causes.")
    print()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.25)
    except Exception as exc:
        print(f"Could not open serial port {args.port}: {exc}")
        return 1

    try:
        print(f"Opened {args.port} at {args.baud} baud.")
        time.sleep(2.0)
        read_serial_lines(ser, 1.0)

        for idx, (command, note) in enumerate(TESTS, start=1):
            print()
            print(f"Step {idx}/{len(TESTS)}")
            print(f"Command: {command}")
            print(f"Note: {note}")
            wait_for_enter("Press Enter to send this command...")

            ser.write((command + "\n").encode("utf-8"))
            ser.flush()
            read_serial_lines(ser, args.pause)

        print()
        print("Record your observations like this:")
        print("  X+ -> board tilts ...")
        print("  X- -> board tilts ...")
        print("  Y+ -> board tilts ...")
        print("  Y- -> board tilts ...")
        print()
        print("Then compare that to the UI image axes:")
        print("  image x = left/right")
        print("  image y = top/bottom")
        print()
        print("That gives us the final swap/invert mapping.")
        return 0
    finally:
        try:
            ser.write(b"CENTER\n")
            ser.flush()
        except Exception:
            pass
        ser.close()


if __name__ == "__main__":
    sys.exit(main())
