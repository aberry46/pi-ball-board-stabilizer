from __future__ import annotations

from flask import Flask, jsonify, request

from .ipc_client import RuntimeIpcClient


app = Flask(__name__)
client = RuntimeIpcClient()


HTML = """
<!doctype html>
<html>
<head>
  <title>Pi Ball Board Stabilizer</title>
  <style>
    body { font-family: Georgia, serif; margin: 24px; background: #f3efe5; color: #1d1a16; }
    .hero { display:flex; justify-content:space-between; align-items:end; margin-bottom:20px; gap:16px; }
    h1 { margin:0; font-size:48px; }
    .layout { display:grid; grid-template-columns: 1.4fr 1fr; gap:20px; align-items:start; }
    .card { background:#fffaf0; border:1px solid #d7cfbf; border-radius:18px; padding:18px; box-shadow:0 12px 28px rgba(0,0,0,0.08); }
    .feeds { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    img { width:100%; border-radius:12px; background:#e6e0d1; }
    .buttons { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }
    button { border:1px solid #d0c6b4; background:#fff6df; padding:10px 14px; border-radius:999px; cursor:pointer; font:inherit; }
    .stat { display:flex; justify-content:space-between; padding:10px 0; border-top:1px solid #e5ddcf; }
    .stat:first-child { border-top:0; }
    .muted { color:#6b655c; }
    .panel-stack { display:grid; gap:20px; }
    .coach-title { margin:0 0 8px 0; font-size:26px; }
    .coach-step { border-top:1px solid #e5ddcf; padding:10px 0; }
    .coach-step:first-of-type { border-top:0; padding-top:0; }
    .coach-label { font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:#6b655c; margin-bottom:6px; }
    .coach-text { font-size:18px; line-height:1.35; }
    .coach-note { margin-top:10px; color:#6b655c; line-height:1.4; }
  </style>
</head>
<body>
  <div class="hero">
    <div>
      <h1>Ball Board Stabilizer</h1>
      <div class="muted">Observer console only. Control decisions stay on the Raspberry Pi runtime.</div>
    </div>
    <div id="mode" class="card">Connecting...</div>
  </div>
  <div class="layout">
    <div class="card">
      <div class="feeds">
        <div><div>Raw</div><img id="raw" /><div id="raw-note" class="muted"></div></div>
        <div><div>Mask</div><img id="mask" /><div id="mask-note" class="muted"></div></div>
      </div>
      <div class="buttons">
        <button onclick="sendCommand('RUN')">Run</button>
        <button onclick="sendCommand('PAUSE')">Pause</button>
        <button onclick="sendCommand('STOP')">Stop</button>
        <button onclick="sendCommand('BALL_FELL_OFF')">Ball Fell Off</button>
        <button onclick="sendCommand('RECALIBRATE')">Recalibrate</button>
      </div>
      <div class="buttons">
        <button onclick="setControllerMode('legacy')">Legacy</button>
        <button onclick="setControllerMode('nn_shadow')">NN Shadow</button>
        <button onclick="setControllerMode('nn_assist')">NN Assist</button>
        <button onclick="setControllerMode('nn_primary')">NN Primary</button>
      </div>
    </div>
    <div class="panel-stack">
      <div class="card">
        <div class="stat"><span class="muted">Runtime</span><span id="runtime-state">--</span></div>
        <div class="stat"><span class="muted">Controller</span><span id="controller-mode">--</span></div>
        <div class="stat"><span class="muted">Ball Found</span><span id="ball-found">--</span></div>
        <div class="stat"><span class="muted">Ball Position</span><span id="ball-pos">--</span></div>
        <div class="stat"><span class="muted">Ball Velocity</span><span id="ball-vel">--</span></div>
        <div class="stat"><span class="muted">Confidence</span><span id="ball-conf">--</span></div>
        <div class="stat"><span class="muted">Tilt</span><span id="tilt">--</span></div>
        <div class="stat"><span class="muted">NN Status</span><span id="nn-status">--</span></div>
        <div class="stat"><span class="muted">NN Inference</span><span id="nn-latency">--</span></div>
        <div class="stat"><span class="muted">FPS</span><span id="fps">--</span></div>
        <div class="stat"><span class="muted">Calibration</span><span id="calibration">--</span></div>
      </div>
      <div class="card">
        <h2 class="coach-title">Training Coach</h2>
        <div class="coach-step">
          <div class="coach-label">What To Do Now</div>
          <div id="coach-now" class="coach-text">Waiting for runtime state...</div>
        </div>
        <div class="coach-step">
          <div class="coach-label">Why</div>
          <div id="coach-why" class="coach-text">--</div>
        </div>
        <div class="coach-step">
          <div class="coach-label">Next Best Reset</div>
          <div id="coach-reset" class="coach-text">--</div>
        </div>
        <div id="coach-note" class="coach-note">Use this panel as your live training script while collecting runs.</div>
      </div>
    </div>
  </div>
  <script>
    async function sendCommand(command) {
      await fetch('/api/command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({command})
      });
      refresh();
    }

    async function setControllerMode(mode) {
      await fetch('/api/controller-mode', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({mode})
      });
      refresh();
    }

    function fmtPair(value, digits=3) {
      if (!value) return '--';
      return `(${Number(value[0]).toFixed(digits)}, ${Number(value[1]).toFixed(digits)})`;
    }

    function speedOf(ball) {
      if (!ball || !ball.velocity_norm) return 0;
      const vx = Number(ball.velocity_norm[0] || 0);
      const vy = Number(ball.velocity_norm[1] || 0);
      return Math.hypot(vx, vy);
    }

    function edgeDistance(ball) {
      if (!ball || !ball.center_norm) return 0;
      const x = Number(ball.center_norm[0]);
      const y = Number(ball.center_norm[1]);
      return Math.min(x, y, 1 - x, 1 - y);
    }

    function updateCoach(snap) {
      const speed = speedOf(snap.ball);
      const edge = edgeDistance(snap.ball);
      let now = 'Place the ball on the board and wait for stable detection.';
      let why = 'The runtime needs a confident target before a useful training run starts.';
      let reset = 'If detection does not return, press Recalibrate.';
      let note = 'Shadow mode is best for collecting behavior without letting the NN steer yet.';

      if (snap.mode === 'CALIBRATING') {
        now = 'Keep the board fully visible and wait for calibration to finish.';
        why = 'Corner calibration needs a stable board view before any run is worth collecting.';
        reset = 'Do not move the board. If calibration stalls, press Recalibrate once.';
      } else if (snap.mode === 'STOPPED' && snap.ball.found) {
        now = 'Place the ball off-center, then press Run.';
        why = 'Stopped mode with a found ball is the cleanest way to start a useful training attempt.';
        reset = 'If the previous attempt ended badly, Ball Fell Off is the fastest clean reset.';
      } else if (snap.mode === 'STOPPED' && !snap.ball.found) {
        now = 'Put the ball back on the board where the camera can see it clearly.';
        why = 'Training runs are only useful after the tracker reacquires the ball.';
        reset = 'If reacquisition is flaky, press Ball Fell Off or Recalibrate.';
      } else if (snap.mode === 'RUNNING' && !snap.ball.found) {
        now = 'Press Ball Fell Off, place the ball back on the board, then Run again.';
        why = 'The runtime is safe-falling back because it no longer has a trustworthy ball state.';
        reset = 'Use Ball Fell Off for a fast reset. Use Stop only if the board still feels confused.';
        note = 'Losing the ball is still useful data, but restart quickly so the next run is clean.';
      } else if (snap.mode === 'RUNNING' && snap.ball.found && edge < 0.10) {
        now = 'Let this run play out unless the ball actually leaves the board.';
        why = 'Near-edge behavior is high-value data for braking and recovery learning.';
        reset = 'If it falls off, press Ball Fell Off immediately and restart.';
        note = 'This is one of the most useful situations to capture.';
      } else if (snap.mode === 'RUNNING' && snap.ball.found && speed > 0.10) {
        now = 'Let it run and watch whether it brakes before overshooting.';
        why = 'Momentum-heavy passes are exactly what the next policy needs to learn.';
        reset = 'If it escapes, use Ball Fell Off and start another off-center run.';
      } else if (snap.mode === 'RUNNING' && snap.ball.found) {
        now = 'Keep the run going and watch whether it bogs down or recenters smoothly.';
        why = 'Slow off-center and near-center behavior helps train startup authority and settling.';
        reset = 'If it gets stuck off-center for a while, Stop, reposition, and Run again.';
      } else if (snap.mode === 'PAUSED') {
        now = 'Reposition the ball, then press Run when ready.';
        why = 'Paused mode is a safe place to reset between attempts without recalibrating.';
        reset = 'If state looks wrong, press Stop or Ball Fell Off.';
      } else if (snap.mode === 'FAULT') {
        now = 'Stop testing and recover the runtime before collecting more data.';
        why = 'Fault mode means the current run is not trustworthy for training.';
        reset = 'Restart the runtime or recalibrate before continuing.';
      }

      document.getElementById('coach-now').textContent = now;
      document.getElementById('coach-why').textContent = why;
      document.getElementById('coach-reset').textContent = reset;
      document.getElementById('coach-note').textContent = note;
    }

    let refreshDelayMs = 500;
    let refreshTimer = null;

    function scheduleRefresh(delayMs) {
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(refresh, delayMs);
    }

    async function refresh() {
      let payload;
      try {
        const response = await fetch('/api/state', {cache: 'no-store'});
        payload = await response.json();
      } catch (error) {
        document.getElementById('mode').textContent = 'Connecting...';
        scheduleRefresh(1000);
        return;
      }
      const snap = payload.snapshot;
      document.getElementById('mode').textContent = snap.mode;
      document.getElementById('runtime-state').textContent = snap.mode;
      document.getElementById('controller-mode').textContent = snap.controller_mode || 'legacy';
      document.getElementById('ball-found').textContent = snap.ball.found ? 'Yes' : 'No';
      document.getElementById('ball-pos').textContent = fmtPair(snap.ball.center_norm, 3);
      document.getElementById('ball-vel').textContent = fmtPair(snap.ball.velocity_norm, 2);
      document.getElementById('ball-conf').textContent = Number(snap.ball.confidence || 0).toFixed(2);
      document.getElementById('tilt').textContent = fmtPair([snap.control.tilt_x, snap.control.tilt_y], 2);
      document.getElementById('nn-status').textContent =
        snap.neural.active ? `active (${snap.neural.mode})` :
        (snap.neural.fallback_reason ? `fallback: ${snap.neural.fallback_reason}` : snap.neural.mode || 'legacy');
      document.getElementById('nn-latency').textContent = `${Number(snap.neural.inference_ms || 0).toFixed(2)} ms`;
      document.getElementById('fps').textContent = Number(snap.fps || 0).toFixed(1);
      document.getElementById('calibration').textContent = `${Math.round((snap.board.progress || 0) * 100)}%`;
      document.getElementById('raw').src = snap.raw_frame_b64 ? `data:image/jpeg;base64,${snap.raw_frame_b64}` : '';
      document.getElementById('mask').src = snap.mask_frame_b64 ? `data:image/jpeg;base64,${snap.mask_frame_b64}` : '';
      document.getElementById('raw-note').textContent = snap.raw_frame_b64 ? '' : (snap.mode === 'RUNNING' ? 'Preview disabled while RUNNING for performance.' : '');
      document.getElementById('mask-note').textContent = snap.mask_frame_b64 ? '' : (snap.mode === 'RUNNING' ? 'Preview disabled while RUNNING for performance.' : '');
      updateCoach(snap);
      refreshDelayMs = snap.mode === 'RUNNING' ? 150 : 250;
      scheduleRefresh(refreshDelayMs);
    }

    refresh();
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    return HTML


@app.get("/api/state")
def state():
    response = client.request({"action": "GET_STATE"})
    return jsonify(response)


@app.post("/api/command")
def command():
    payload = request.get_json(force=True)
    response = client.request({"action": payload.get("command", "")})
    return jsonify(response)


@app.post("/api/controller-mode")
def controller_mode():
    payload = request.get_json(force=True)
    response = client.request({"action": "SET_CONTROLLER_MODE", "mode": payload.get("mode", "legacy")})
    return jsonify(response)


def main() -> None:
    app.run(host="0.0.0.0", port=5000, threaded=True)


if __name__ == "__main__":
    main()
