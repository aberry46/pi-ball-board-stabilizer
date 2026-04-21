# Control Notes

## First Success Metric

Hold the red ball near the center of the board for several seconds.

## Why Red

The red ball intentionally simplifies detection. V1 uses deterministic OpenCV rather than ML.

## Why Separate Runtime and UI

The observer server must never be allowed to block or shape the balancing loop. The runtime can continue operating even if the UI is disconnected or restarted.
