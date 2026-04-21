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
    .layout { display:grid; grid-template-columns: 1.4fr 1fr; gap:20px; }
    .card { background:#fffaf0; border:1px solid #d7cfbf; border-radius:18px; padding:18px; box-shadow:0 12px 28px rgba(0,0,0,0.08); }
    .feeds { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    img { width:100%; border-radius:12px; background:#e6e0d1; }
    .buttons { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }
    button { border:1px solid #d0c6b4; background:#fff6df; padding:10px 14px; border-radius:999px; cursor:pointer; font:inherit; }
    .stat { display:flex; justify-content:space-between; padding:10px 0; border-top:1px solid #e5ddcf; }
    .stat:first-child { border-top:0; }
    .muted { color:#6b655c; }
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
        <div><div>Raw</div><img id="raw" /></div>
        <div><div>Mask</div><img id="mask" /></div>
      </div>
      <div class="buttons">
        <button onclick="sendCommand('RUN')">Run</button>
        <button onclick="sendCommand('PAUSE')">Pause</button>
        <button onclick="sendCommand('STOP')">Stop</button>
        <button onclick="sendCommand('RECALIBRATE')">Recalibrate</button>
      </div>
    </div>
    <div class="card">
      <div class="stat"><span class="muted">Runtime</span><span id="runtime-state">--</span></div>
      <div class="stat"><span class="muted">Ball Found</span><span id="ball-found">--</span></div>
      <div class="stat"><span class="muted">Ball Position</span><span id="ball-pos">--</span></div>
      <div class="stat"><span class="muted">Ball Velocity</span><span id="ball-vel">--</span></div>
      <div class="stat"><span class="muted">Confidence</span><span id="ball-conf">--</span></div>
      <div class="stat"><span class="muted">Tilt</span><span id="tilt">--</span></div>
      <div class="stat"><span class="muted">FPS</span><span id="fps">--</span></div>
      <div class="stat"><span class="muted">Calibration</span><span id="calibration">--</span></div>
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

    function fmtPair(value, digits=3) {
      if (!value) return '--';
      return `(${Number(value[0]).toFixed(digits)}, ${Number(value[1]).toFixed(digits)})`;
    }

    async function refresh() {
      const response = await fetch('/api/state', {cache: 'no-store'});
      const payload = await response.json();
      const snap = payload.snapshot;
      document.getElementById('mode').textContent = snap.mode;
      document.getElementById('runtime-state').textContent = snap.mode;
      document.getElementById('ball-found').textContent = snap.ball.found ? 'Yes' : 'No';
      document.getElementById('ball-pos').textContent = fmtPair(snap.ball.center_norm, 3);
      document.getElementById('ball-vel').textContent = fmtPair(snap.ball.velocity_norm, 2);
      document.getElementById('ball-conf').textContent = Number(snap.ball.confidence || 0).toFixed(2);
      document.getElementById('tilt').textContent = fmtPair([snap.control.tilt_x, snap.control.tilt_y], 2);
      document.getElementById('fps').textContent = Number(snap.fps || 0).toFixed(1);
      document.getElementById('calibration').textContent = `${Math.round((snap.board.progress || 0) * 100)}%`;
      document.getElementById('raw').src = snap.raw_frame_b64 ? `data:image/jpeg;base64,${snap.raw_frame_b64}` : '';
      document.getElementById('mask').src = snap.mask_frame_b64 ? `data:image/jpeg;base64,${snap.mask_frame_b64}` : '';
    }

    refresh();
    setInterval(refresh, 200);
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


def main() -> None:
    app.run(host="0.0.0.0", port=5000, threaded=True)


if __name__ == "__main__":
    main()
