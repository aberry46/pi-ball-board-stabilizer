# pi-ball-board-stabilizer

Real-time Raspberry Pi and Arduino ball-on-board stabilizer with a local control loop, red-ball vision, and observer-only web telemetry.

## V1 Goal

Hold a red ball near the center of the board for several seconds under normal test conditions.

## Architecture

- Raspberry Pi owns perception, state estimation, control, and runtime state.
- Arduino only enforces safe servo limits and executes normalized tilt commands.
- The web server is a passive observer and operator console.
- The runtime and the web server communicate locally over a localhost socket.

## Runtime States

- `STOPPED`: neutral board, live telemetry, no balancing
- `CALIBRATING`: detect board ROI, center, and safe margins
- `RUNNING`: active balancing
- `PAUSED`: neutral board, live telemetry
- `FAULT`: neutral board, live telemetry, operator intervention required

## Layout

- `pi/runtime`: authoritative Pi control loop
- `pi/server`: observer UI and command surface
- `arduino/firmware`: thin servo executor firmware
- `docs`: design notes and operating guidance

## Running

Start the runtime from the repo root:

```bash
python -m pi.runtime.main
```

Start the observer server from the repo root:

```bash
python -m pi.server.app
```

## Helpful Scripts

For Raspberry Pi/Linux use:

- `scripts/start_runtime.sh`
- `scripts/start_server.sh`
- `scripts/start_all_pi.sh`
- `scripts/stop_all_pi.sh`
- `scripts/update_and_restart.sh`

To pull the latest code from GitHub and restart both services in one step:

```bash
./scripts/update_and_restart.sh
```

## First Pi Bring-Up

1. Install Python dependencies from `requirements.txt`
2. Upload `arduino/firmware/pi_ball_board_servo_controller.ino` to the Arduino
3. Start the runtime
4. Start the observer server
5. Open the web UI and calibrate before running

See `docs/pi-deployment-checklist.md` for the practical step-by-step version.
