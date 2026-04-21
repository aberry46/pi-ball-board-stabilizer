# Pi Deployment Checklist

## 1. Copy the repo to the Pi

Place the repository somewhere stable, for example:

```bash
~/pi-ball-board-stabilizer
```

## 2. Install Python dependencies

From the repo root on the Pi:

```bash
python3 -m pip install -r requirements.txt
```

## 3. Upload the Arduino firmware

Upload:

```text
arduino/firmware/pi_ball_board_servo_controller.ino
```

The firmware expects:

- servo X on pin `9`
- servo Y on pin `10`
- USB serial at `115200`

## 4. Confirm the Arduino serial device

Check which device the Pi sees:

```bash
ls /dev/ttyACM* /dev/ttyUSB*
```

If needed, update `serial_port` in `pi/runtime/config.py`.

## 5. Stop stale camera/runtime processes

```bash
./scripts/stop_all_pi.sh
```

## 6. Start the runtime

```bash
./scripts/start_runtime.sh
```

Expected behavior:

- runtime starts in `CALIBRATING`
- board neutral command is sent to Arduino
- after successful calibration, runtime moves to `STOPPED`

## 7. Start the observer server

In another terminal:

```bash
./scripts/start_server.sh
```

Open:

```text
http://<pi-ip>:5000
```

## 8. First-use checklist

- raw feed visible
- mask feed visible
- board outline visible after calibration
- runtime state shows `STOPPED`
- `RUN`, `PAUSE`, `STOP`, `RECALIBRATE` buttons respond
- Arduino returns to neutral on `STOP` and `PAUSE`

## 9. Fault recovery

If the camera or runtime gets stuck:

```bash
./scripts/stop_all_pi.sh
./scripts/start_runtime.sh
./scripts/start_server.sh
```

## 10. First tuning targets

If detection is weak:

- adjust red HSV thresholds in `pi/runtime/config.py`
- adjust `min_blob_area`
- adjust `min_confidence`

If control is weak or unstable:

- adjust `kp_x`, `kp_y`
- adjust `kd_x`, `kd_y`
- adjust `catch_velocity_threshold`
- adjust `catch_error_threshold`
