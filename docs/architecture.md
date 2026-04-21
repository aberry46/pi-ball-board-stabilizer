# Fresh V1 Architecture

## Control Authority

The Raspberry Pi is the only decision-maker. It captures frames, estimates board-relative ball state, computes control, and sends normalized tilt commands to the Arduino.

## Arduino Role

The Arduino is a deterministic servo executor. It applies limits, inversion, neutral behavior, and fast actuation. It does not own balancing logic.

## Observer UI

The observer server is not part of the control path. It displays the raw feed, the red-ball mask, runtime state, and exposes `RUN`, `PAUSE`, `STOP`, and `RECALIBRATE`.

## Calibration Model

The camera is treated as fixed after startup. Calibration establishes:

- board ROI
- board center
- safe interior margins

The calibration is refreshed only on explicit operator request.
