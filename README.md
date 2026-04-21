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
- `nn_training`: offline neural-model training utilities
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

If a repo virtualenv exists at `.venv`, the scripts will use it automatically.

## Neural Control Workflow

The runtime now supports four controller modes through `pi/runtime/config.py`:

- `legacy`: deterministic controller only
- `nn_shadow`: run neural inference, log telemetry, do not affect commands
- `nn_assist`: bounded neural correction blended with the legacy controller
- `nn_primary`: neural pilot with hard safety fallback

For Pi-local overrides that should not be committed, create:

- `runtime_data/local_runtime_config.json`

The runtime loads that file automatically at startup. A sample is in:

- `docs/local-runtime-config.example.json`

### Control Logging

Each runtime session can write replay-quality JSONL traces under:

- `runtime_data/control_logs/`

Those traces include:

- ball state
- confidence
- control command
- controller mode
- NN telemetry
- board calibration snapshot

### System Identification

To collect scripted X/Y pulse traces on the Pi:

```bash
PYTHONPATH=. ./.venv/bin/python scripts/collect_system_id.py
```

This saves pulse-response traces under:

- `runtime_data/system_id/`

### Train Dynamics and Policy Models

From the repo root:

```bash
PYTHONPATH=. python scripts/train_dynamics_model.py --data runtime_data/control_logs
PYTHONPATH=. python scripts/train_policy_model.py --data runtime_data/control_logs
```

To train a smarter second-pass policy from a planner built on the learned dynamics model:

```bash
PYTHONPATH=. python scripts/train_policy_with_planner.py
```

That writes:

- `artifacts/nn/policy_model_planner.npz`

Artifacts are written by default to:

- `artifacts/nn/dynamics_model.npz`
- `artifacts/nn/policy_model.npz`
- `artifacts/nn/normalization.json`

### Evaluate Trained Models

```bash
PYTHONPATH=. python scripts/evaluate_nn_models.py --data runtime_data/control_logs
```

To evaluate the planner-trained policy artifact instead:

```bash
PYTHONPATH=. python scripts/evaluate_nn_models.py --policy-file policy_model_planner.npz
```

### Live Mode Switching

The observer UI now includes controller-mode buttons for:

- `legacy`
- `nn_shadow`
- `nn_assist`
- `nn_primary`

That lets you switch live runtime mode without editing config files or restarting the process.

## First Pi Bring-Up

1. Install Python dependencies from `requirements.txt`
2. Upload `arduino/firmware/pi_ball_board_servo_controller.ino` to the Arduino
3. Start the runtime
4. Start the observer server
5. Open the web UI and calibrate before running

See `docs/pi-deployment-checklist.md` for the practical step-by-step version.
