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
    :root {
      --bg-1:#faf6ec;
      --bg-2:#efe7d7;
      --bg-3:#eadfcd;
      --card-1:#fffaf0;
      --card-2:#fff7e8;
      --line:#d7cfbf;
      --text:#1d1a16;
      --muted:#6b655c;
      --soft:#f7edd7;
      --gold:#b38317;
      --gold-2:#d7a94f;
      --green:#2d8a4f;
      --red:#a34a2f;
      --blue:#3d76b5;
      --shadow:0 16px 38px rgba(64,43,17,0.10);
    }
    * { box-sizing:border-box; }
    body { font-family: Georgia, serif; margin: 24px; background:
      radial-gradient(circle at top left, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 34%),
      radial-gradient(circle at top, var(--bg-1) 0%, var(--bg-2) 45%, var(--bg-3) 100%);
      color: var(--text); }
    .page-shell { max-width: 1480px; margin: 0 auto; }
    .hero { display:flex; justify-content:space-between; align-items:end; margin-bottom:20px; gap:16px; }
    h1 { margin:0; font-size:64px; line-height:0.92; letter-spacing:-0.04em; }
    .layout { display:grid; grid-template-columns: 1.45fr 1fr; gap:20px; align-items:start; }
    .card { background:linear-gradient(180deg, var(--card-1) 0%, var(--card-2) 100%); border:1px solid var(--line); border-radius:22px; padding:18px; box-shadow:var(--shadow); position:relative; overflow:hidden; }
    .card::after { content:''; position:absolute; inset:auto -8% -55% 38%; height:120px; background:radial-gradient(circle, rgba(215,169,79,0.12), rgba(215,169,79,0)); pointer-events:none; }
    .feeds { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
    img { width:100%; border-radius:12px; background:#e6e0d1; }
    .buttons { display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }
    button { border:1px solid #d0c6b4; background:#fff6df; padding:10px 14px; border-radius:999px; cursor:pointer; font:inherit; transition:transform 0.08s ease, background 0.18s ease, border-color 0.18s ease, opacity 0.18s ease, box-shadow 0.18s ease; }
    button:hover { background:#fff0c8; border-color:#b9ae98; box-shadow:0 8px 16px rgba(74,57,24,0.10); }
    button:active { transform:scale(0.98); }
    button.pending { background:#f8df9b; border-color:#a8801f; }
    button.active-mode { background:#ead2a5; border-color:#8b6842; font-weight:700; }
    button:disabled { opacity:0.55; cursor:wait; }
    .stat { display:flex; justify-content:space-between; padding:10px 0; border-top:1px solid #e5ddcf; gap:12px; }
    .stat:first-child { border-top:0; }
    .muted { color:var(--muted); }
    .alert { color:#8a2f1f; font-weight:600; }
    .panel-stack { display:grid; gap:20px; }
    .coach-title { margin:0 0 8px 0; font-size:26px; }
    .coach-step { border-top:1px solid #e5ddcf; padding:10px 0; }
    .coach-step:first-of-type { border-top:0; padding-top:0; }
    .coach-label { font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:#6b655c; margin-bottom:6px; }
    .coach-text { font-size:18px; line-height:1.35; }
    .coach-note { margin-top:10px; color:#6b655c; line-height:1.4; }
    .status-row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:16px; }
    .pill { display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px; background:var(--soft); border:1px solid #d9ccb3; color:#493c2f; }
    .pill strong { font-size:13px; letter-spacing:0.05em; text-transform:uppercase; }
    .pulse { width:10px; height:10px; border-radius:999px; background:var(--gold); box-shadow:0 0 0 0 rgba(179,131,23,0.4); }
    .pulse.live { background:var(--green); animation:pulse 1.6s infinite; }
    .pulse.warn { background:var(--red); animation:pulse 1.6s infinite; }
    .command-log { margin-top:12px; font-size:15px; line-height:1.4; color:#5b4b39; min-height:1.4em; }
    .mode-card { min-width:300px; text-align:right; background:
      linear-gradient(180deg, rgba(255,250,240,0.92) 0%, rgba(255,247,232,0.92) 100%),
      radial-gradient(circle at top left, rgba(76,144,212,0.12), rgba(76,144,212,0) 55%); }
    .mode-kicker { font-size:12px; letter-spacing:0.12em; text-transform:uppercase; color:#7a6d60; }
    .mode-value { display:block; font-size:36px; font-weight:700; margin-top:6px; }
    .hero-sub { max-width:760px; font-size:20px; color:#6b655c; margin-top:10px; line-height:1.35; }
    .section-title { margin:0 0 12px 0; font-size:24px; }
    .mode-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:12px; margin-bottom:16px; }
    .mode-chip { border:1px solid #ddcfb7; border-radius:16px; padding:12px 14px; background:#fbf3e3; transition:transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease; }
    .mode-chip.active-chip { transform:translateY(-2px); box-shadow:0 10px 18px rgba(61,118,181,0.10); border-color:#b5c7de; }
    .mode-chip-label { display:block; font-size:11px; letter-spacing:0.08em; text-transform:uppercase; color:#7d6c58; margin-bottom:6px; }
    .mode-chip-value { display:block; font-size:20px; color:#241c15; }
    .nn-grid { display:grid; gap:12px; }
    .nn-row { display:grid; grid-template-columns:120px 1fr 64px; gap:12px; align-items:center; }
    .nn-row-label { font-size:14px; color:#6c5f51; text-transform:uppercase; letter-spacing:0.06em; }
    .bar { position:relative; height:14px; border-radius:999px; background:#eadfca; overflow:hidden; }
    .bar-fill { position:absolute; top:0; bottom:0; left:50%; width:0; border-radius:999px; transition:all 0.16s ease; }
    .bar-fill.legacy { background:linear-gradient(90deg, #8b6842, #c39a6a); opacity:0.9; }
    .bar-fill.neural { background:linear-gradient(90deg, #275e93, #4c90d4); opacity:0.8; }
    .bar-fill.final { background:linear-gradient(90deg, #29734d, #55aa78); opacity:0.95; }
    .bar-fill.active { box-shadow:0 0 0 3px rgba(76,144,212,0.16); }
    .nn-meta { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; margin-top:10px; }
    .meta-tile { border:1px solid #dfd3bf; border-radius:14px; padding:10px 12px; background:#fcf5e8; }
    .meta-kicker { display:block; font-size:11px; letter-spacing:0.08em; text-transform:uppercase; color:#7d6c58; margin-bottom:4px; }
    .meta-value { font-size:20px; color:#221a12; }
    .surface-note { margin-top:12px; color:#746756; line-height:1.45; }
    .topline { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; margin-bottom:18px; }
    .hero-strip { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:16px; margin-bottom:20px; }
    .headline-card { padding:16px 18px; border-radius:18px; border:1px solid var(--line); background:linear-gradient(180deg, rgba(255,250,240,0.95) 0%, rgba(255,245,228,0.95) 100%); box-shadow:var(--shadow); }
    .headline-label { display:block; font-size:11px; letter-spacing:0.10em; text-transform:uppercase; color:#7d6c58; margin-bottom:8px; }
    .headline-value { display:block; font-size:24px; }
    .headline-sub { display:block; margin-top:6px; color:#6f6458; font-size:14px; line-height:1.35; }
    .nn-stage-list { display:grid; gap:10px; margin-top:8px; }
    .nn-stage { border:1px solid #dfd3bf; border-radius:16px; background:#fcf5e8; padding:12px 14px; transition:border-color 0.16s ease, background 0.16s ease, transform 0.16s ease; }
    .nn-stage.active-stage { border-color:#8caed4; background:#f1f7ff; transform:translateY(-1px); }
    .nn-stage-title { display:flex; justify-content:space-between; gap:10px; font-size:18px; }
    .nn-stage-kicker { font-size:11px; letter-spacing:0.08em; text-transform:uppercase; color:#7d6c58; }
    .nn-stage-desc { margin-top:6px; color:#66594d; line-height:1.4; }
    .mode-pill { display:inline-flex; align-items:center; padding:4px 10px; border-radius:999px; font-size:12px; letter-spacing:0.06em; text-transform:uppercase; border:1px solid #d3c7b2; background:#f8efde; color:#594935; }
    .mode-pill.shadow { background:#edf4ff; border-color:#bfd2ee; color:#365a86; }
    .mode-pill.assist { background:#eef9f1; border-color:#c2e5cb; color:#2b6b42; }
    .mode-pill.primary { background:#fff1ee; border-color:#e8c0b8; color:#8b4337; }
    .mode-pill.legacy { background:#f8efde; border-color:#d3c7b2; color:#594935; }
    .nn-callout { margin-top:14px; padding:12px 14px; border-radius:16px; background:#f5efe1; border:1px solid #ded1bc; color:#5f5144; line-height:1.45; }
    .mode-map { display:grid; gap:10px; }
    .mode-map-row { display:grid; grid-template-columns:130px 1fr; gap:14px; padding:10px 0; border-top:1px solid #e5ddcf; }
    .mode-map-row:first-child { border-top:0; }
    .mode-map-name { font-size:13px; letter-spacing:0.06em; text-transform:uppercase; color:#756756; }
    .mode-map-desc { color:#44382d; line-height:1.4; }
    @media (max-width: 1180px) {
      .layout { grid-template-columns:1fr; }
      .hero-strip { grid-template-columns:repeat(2, minmax(0, 1fr)); }
      .hero { align-items:start; flex-direction:column; }
      .mode-card { width:100%; text-align:left; }
    }
    @media (max-width: 720px) {
      body { margin:14px; }
      h1 { font-size:46px; }
      .feeds { grid-template-columns:1fr; }
      .hero-strip { grid-template-columns:1fr; }
      .mode-grid, .nn-meta { grid-template-columns:1fr; }
      .nn-row { grid-template-columns:96px 1fr 56px; }
      .mode-map-row { grid-template-columns:1fr; gap:6px; }
    }
    @keyframes pulse {
      0% { box-shadow:0 0 0 0 rgba(45,138,79,0.35); }
      70% { box-shadow:0 0 0 10px rgba(45,138,79,0); }
      100% { box-shadow:0 0 0 0 rgba(45,138,79,0); }
    }
  </style>
</head>
<body>
  <div class="page-shell">
  <div class="hero">
    <div>
      <h1>Ball Board Stabilizer</h1>
      <div class="hero-sub">Observer console with training guidance, neural telemetry, instant operator feedback, and a clearer separation between system state, controller state, and run state.</div>
    </div>
    <div id="mode" class="card mode-card"><span class="mode-kicker">System Mode</span><span class="mode-value">Connecting...</span></div>
  </div>
  <div class="hero-strip">
    <div class="headline-card">
      <span class="headline-label">Run State</span>
      <span id="headline-run-state" class="headline-value">Connecting...</span>
      <span id="headline-run-sub" class="headline-sub">Waiting for runtime telemetry.</span>
    </div>
    <div class="headline-card">
      <span class="headline-label">Controller Lane</span>
      <span id="headline-controller" class="headline-value">--</span>
      <span id="headline-controller-sub" class="headline-sub">Legacy and neural modes will appear here.</span>
    </div>
    <div class="headline-card">
      <span class="headline-label">Ball State</span>
      <span id="headline-ball" class="headline-value">--</span>
      <span id="headline-ball-sub" class="headline-sub">Tracking quality and edge state.</span>
    </div>
    <div class="headline-card">
      <span class="headline-label">Neural Status</span>
      <span id="headline-nn" class="headline-value">--</span>
      <span id="headline-nn-sub" class="headline-sub">Inference, fallback, and decision source.</span>
    </div>
  </div>
  <div class="layout">
    <div class="card">
      <div class="topline">
        <div>
          <h2 class="section-title">Live Feeds</h2>
          <div class="muted">Preview windows and direct runtime controls for fast iteration.</div>
        </div>
      </div>
      <div class="feeds">
        <div><div>Raw</div><img id="raw" /><div id="raw-note" class="muted"></div></div>
        <div><div>Mask</div><img id="mask" /><div id="mask-note" class="muted"></div></div>
      </div>
      <div class="buttons">
        <button id="btn-RUN" onclick="sendCommand('RUN')">Run</button>
        <button id="btn-PAUSE" onclick="sendCommand('PAUSE')">Pause</button>
        <button id="btn-STOP" onclick="sendCommand('STOP')">Stop</button>
        <button id="btn-BALL_FELL_OFF" onclick="sendCommand('BALL_FELL_OFF')">Ball Fell Off</button>
        <button id="btn-RECALIBRATE" onclick="sendCommand('RECALIBRATE')">Recalibrate</button>
      </div>
      <div class="buttons">
        <button id="mode-legacy" onclick="setControllerMode('legacy')">Legacy</button>
        <button id="mode-nn_shadow" onclick="setControllerMode('nn_shadow')">NN Shadow</button>
        <button id="mode-nn_assist" onclick="setControllerMode('nn_assist')">NN Assist</button>
        <button id="mode-nn_primary" onclick="setControllerMode('nn_primary')">NN Primary</button>
      </div>
      <div class="status-row">
        <div class="pill"><span id="runtime-pulse" class="pulse"></span><strong>Live Status</strong><span id="runtime-live-text">Connecting...</span></div>
        <div class="pill"><strong>Last Input</strong><span id="last-command">None yet</span></div>
      </div>
      <div id="command-log" class="command-log">Press a command to start collecting runs.</div>
    </div>
    <div class="panel-stack">
      <div class="card">
        <h2 class="section-title">Runtime Snapshot</h2>
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
        <h2 class="section-title">Mode Deck</h2>
        <div class="mode-grid">
          <div class="mode-chip">
            <span class="mode-chip-label">Runtime State</span>
            <span id="chip-runtime" class="mode-chip-value">--</span>
          </div>
          <div class="mode-chip">
            <span class="mode-chip-label">Controller Mode</span>
            <span id="chip-controller" class="mode-chip-value">--</span>
          </div>
          <div class="mode-chip">
            <span class="mode-chip-label">Ball Status</span>
            <span id="chip-ball-status" class="mode-chip-value">--</span>
          </div>
          <div class="mode-chip">
            <span class="mode-chip-label">NN State</span>
            <span id="chip-nn-state" class="mode-chip-value">--</span>
          </div>
        </div>
        <div class="surface-note">This separates system mode, controller mode, ball lifecycle, and NN lifecycle so it is obvious what changed when behavior shifts.</div>
      </div>
      <div class="card">
        <h2 class="section-title">Neural Activity</h2>
        <div class="nn-grid">
          <div class="nn-row">
            <div class="nn-row-label">Legacy X</div>
            <div class="bar"><div id="bar-legacy-x" class="bar-fill legacy"></div></div>
            <div id="bar-legacy-x-value">0.00</div>
          </div>
          <div class="nn-row">
            <div class="nn-row-label">Legacy Y</div>
            <div class="bar"><div id="bar-legacy-y" class="bar-fill legacy"></div></div>
            <div id="bar-legacy-y-value">0.00</div>
          </div>
          <div class="nn-row">
            <div class="nn-row-label">NN X</div>
            <div class="bar"><div id="bar-nn-x" class="bar-fill neural"></div></div>
            <div id="bar-nn-x-value">0.00</div>
          </div>
          <div class="nn-row">
            <div class="nn-row-label">NN Y</div>
            <div class="bar"><div id="bar-nn-y" class="bar-fill neural"></div></div>
            <div id="bar-nn-y-value">0.00</div>
          </div>
          <div class="nn-row">
            <div class="nn-row-label">Final X</div>
            <div class="bar"><div id="bar-final-x" class="bar-fill final"></div></div>
            <div id="bar-final-x-value">0.00</div>
          </div>
          <div class="nn-row">
            <div class="nn-row-label">Final Y</div>
            <div class="bar"><div id="bar-final-y" class="bar-fill final"></div></div>
            <div id="bar-final-y-value">0.00</div>
          </div>
        </div>
        <div class="nn-meta">
          <div class="meta-tile">
            <span class="meta-kicker">Disagreement</span>
            <span id="meta-disagreement" class="meta-value">0.00</span>
          </div>
          <div class="meta-tile">
            <span class="meta-kicker">Edge Risk</span>
            <span id="meta-edge-risk" class="meta-value">0.00</span>
          </div>
          <div class="meta-tile">
            <span class="meta-kicker">Inference</span>
            <span id="meta-inference" class="meta-value">0.00 ms</span>
          </div>
          <div class="meta-tile">
            <span class="meta-kicker">Decision Source</span>
            <span id="meta-source" class="meta-value">legacy</span>
          </div>
        </div>
        <div id="nn-explainer" class="surface-note">When the neural net is loaded, you can compare its suggested tilt against the legacy command here even in shadow mode.</div>
        <div id="nn-callout" class="nn-callout">This panel makes the model visible: legacy suggestion, neural suggestion, and final command can all diverge depending on mode and fallback state.</div>
      </div>
      <div class="card">
        <h2 class="section-title">Control Modes</h2>
        <div class="nn-stage-list">
          <div id="stage-legacy" class="nn-stage">
            <div class="nn-stage-title"><span>Legacy</span><span class="mode-pill legacy">Classical</span></div>
            <div class="nn-stage-desc">Pure deterministic controller. Best baseline for sanity checks and hardware verification.</div>
          </div>
          <div id="stage-nn_shadow" class="nn-stage">
            <div class="nn-stage-title"><span>NN Shadow</span><span class="mode-pill shadow">Observe</span></div>
            <div class="nn-stage-desc">The neural net thinks in real time, but the legacy controller still pilots the board. Best for collecting new runs safely.</div>
          </div>
          <div id="stage-nn_assist" class="nn-stage">
            <div class="nn-stage-title"><span>NN Assist</span><span class="mode-pill assist">Blend</span></div>
            <div class="nn-stage-desc">The neural net can help when the runtime trusts the state. Fallback rules still protect the board.</div>
          </div>
          <div id="stage-nn_primary" class="nn-stage">
            <div class="nn-stage-title"><span>NN Primary</span><span class="mode-pill primary">Pilot</span></div>
            <div class="nn-stage-desc">The neural controller becomes the main pilot while deterministic safety still stays armed behind it.</div>
          </div>
        </div>
        <div class="surface-note">The active mode is highlighted so it is always obvious whether we are collecting, assisting, or letting the NN truly fly.</div>
      </div>
      <div class="card">
        <h2 class="section-title">Mode Guide</h2>
        <div class="mode-map">
          <div class="mode-map-row">
            <div class="mode-map-name">System Mode</div>
            <div class="mode-map-desc">Overall lifecycle of the runtime: calibrating, ready, running, paused, fault, or ball lost.</div>
          </div>
          <div class="mode-map-row">
            <div class="mode-map-name">Controller Mode</div>
            <div class="mode-map-desc">Which control stack owns the decision logic right now: legacy, shadow, assist, or primary.</div>
          </div>
          <div class="mode-map-row">
            <div class="mode-map-name">Ball State</div>
            <div class="mode-map-desc">Whether the ball is being tracked cleanly, has touched the edge dead zone, or has fallen out of the run.</div>
          </div>
          <div class="mode-map-row">
            <div class="mode-map-name">NN State</div>
            <div class="mode-map-desc">Whether the NN is active, shadowing, or being held back by a fallback rule such as edge risk or missing ball.</div>
          </div>
        </div>
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
  </div>
  <script>
    function fmtPair(value, digits=3) {
      if (!value) return '--';
      return `(${Number(value[0]).toFixed(digits)}, ${Number(value[1]).toFixed(digits)})`;
    }

    function modeTitle(mode, ballLostWhileRunning) {
      if (ballLostWhileRunning) return 'BALL LOST';
      if (mode === 'CALIBRATING') return 'CALIBRATING';
      if (mode === 'RUNNING') return 'RUNNING';
      if (mode === 'STOPPED') return 'READY';
      if (mode === 'PAUSED') return 'PAUSED';
      if (mode === 'FAULT') return 'FAULT';
      return mode || '--';
    }

    function setBar(elementId, value, kind, active) {
      const element = document.getElementById(elementId);
      if (!element) return;
      const magnitude = Math.min(Math.abs(Number(value || 0)), 1.0) * 50;
      element.className = `bar-fill ${kind}${active ? ' active' : ''}`;
      element.style.left = Number(value || 0) >= 0 ? '50%' : `${50 - magnitude}%`;
      element.style.width = `${magnitude}%`;
    }

    function modeTone(mode) {
      if (mode === 'nn_shadow') return 'shadow';
      if (mode === 'nn_assist') return 'assist';
      if (mode === 'nn_primary') return 'primary';
      return 'legacy';
    }

    function ballHeadlineText(snap, ballLostWhileRunning) {
      if (ballLostWhileRunning) return ['Dead Run', 'Ball left the useful operating zone or hit the edge dead margin.'];
      if (snap.ball.found) {
        const edge = edgeDistance(snap.ball);
        if (edge < 0.08) return ['Near Edge', 'Useful high-risk training moment.'];
        return ['Tracked', 'Ball state is healthy enough for live decisions.'];
      }
      return ['Missing', 'Place the ball back on the board to continue.'];
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
    let pendingCommand = null;
    let pendingMode = null;
    let lastCommandAt = 0;

    function setPendingButton(buttonId, active) {
      const button = document.getElementById(buttonId);
      if (!button) return;
      button.classList.toggle('pending', active);
      button.disabled = active;
    }

    function markModeButtons(activeMode) {
      ['legacy', 'nn_shadow', 'nn_assist', 'nn_primary'].forEach(mode => {
        const button = document.getElementById(`mode-${mode}`);
        if (!button) return;
        button.classList.toggle('active-mode', mode === activeMode);
        button.classList.toggle('pending', pendingMode === mode);
        button.disabled = pendingMode === mode;
      });
      ['legacy', 'nn_shadow', 'nn_assist', 'nn_primary'].forEach(mode => {
        const stage = document.getElementById(`stage-${mode}`);
        if (!stage) return;
        stage.classList.toggle('active-stage', mode === activeMode);
      });
    }

    function updateCommandLog(text) {
      document.getElementById('command-log').textContent = text;
    }

    function scheduleRefresh(delayMs) {
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(refresh, delayMs);
    }

    async function sendCommand(command) {
      pendingCommand = command;
      lastCommandAt = Date.now();
      setPendingButton(`btn-${command}`, true);
      document.getElementById('last-command').textContent = command.replaceAll('_', ' ');
      updateCommandLog(`Sending ${command.replaceAll('_', ' ')}...`);
      try {
        const response = await fetch('/api/command', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({command})
        });
        const payload = await response.json();
        if (payload.ok) {
          updateCommandLog(`${command.replaceAll('_', ' ')} sent. Waiting for runtime acknowledgement...`);
        } else {
          updateCommandLog(`Command failed: ${payload.error || 'unknown error'}`);
          setPendingButton(`btn-${command}`, false);
          pendingCommand = null;
        }
      } catch (error) {
        updateCommandLog('Command failed to send. Check the runtime/server connection.');
        setPendingButton(`btn-${command}`, false);
        pendingCommand = null;
      }
      refresh();
    }

    async function setControllerMode(mode) {
      pendingMode = mode;
      lastCommandAt = Date.now();
      markModeButtons(mode);
      document.getElementById('last-command').textContent = `Mode: ${mode}`;
      updateCommandLog(`Switching controller to ${mode}...`);
      try {
        const response = await fetch('/api/controller-mode', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({mode})
        });
        const payload = await response.json();
        if (payload.ok) {
          updateCommandLog(`Controller mode request sent: ${mode}. Waiting for runtime acknowledgement...`);
        } else {
          updateCommandLog(`Mode switch failed: ${payload.error || 'unknown error'}`);
          pendingMode = null;
          markModeButtons(mode);
        }
      } catch (error) {
        updateCommandLog('Mode switch failed to send. Check the runtime/server connection.');
        pendingMode = null;
        markModeButtons(mode);
      }
      refresh();
    }

    async function refresh() {
      let payload;
      try {
        const response = await fetch('/api/state', {cache: 'no-store'});
        payload = await response.json();
      } catch (error) {
        document.getElementById('mode').textContent = 'Connecting...';
        document.getElementById('runtime-pulse').className = 'pulse warn';
        document.getElementById('runtime-live-text').textContent = 'Disconnected';
        scheduleRefresh(1000);
        return;
      }
      const snap = payload.snapshot;
      const ballLostWhileRunning = snap.mode === 'RUNNING' && !snap.ball.found;
      const visibleMode = modeTitle(snap.mode, ballLostWhileRunning);
      const controllerMode = snap.controller_mode || 'legacy';
      const [ballHeadline, ballHeadlineSub] = ballHeadlineText(snap, ballLostWhileRunning);
      const rawFallback = snap.neural.fallback_reason || '';
      const friendlyFallback = rawFallback === 'runtime not running' ? 'armed for live run' : rawFallback;
      const nnStatusText = snap.neural.active ? `active (${snap.neural.mode})` :
        (friendlyFallback ? `fallback: ${friendlyFallback}` : snap.neural.mode || 'legacy');
      const neuralHeadline = snap.neural.active ? 'Actively Steering' :
        (friendlyFallback ? 'Fallback Active' : 'Observing');
      const neuralHeadlineSub = snap.neural.active
        ? `Using ${snap.control.source || 'neural'} output right now.`
        : (friendlyFallback
          ? `Held back because ${friendlyFallback}.`
          : 'NN is loaded but not yet influencing the final command.');
      document.getElementById('mode').innerHTML = `<span class="mode-kicker">System Mode</span><span class="mode-value">${visibleMode}</span>`;
      document.getElementById('mode').className = ballLostWhileRunning ? 'card alert' : 'card';
      document.getElementById('headline-run-state').textContent = visibleMode;
      document.getElementById('headline-run-sub').textContent = ballLostWhileRunning
        ? 'The run is considered dead. Reset quickly and continue collecting.'
        : (snap.mode === 'RUNNING'
          ? 'Live control loop is active and updating.'
          : 'Runtime is ready for the next clean attempt.');
      document.getElementById('headline-controller').textContent = controllerMode.replace('nn_', 'nn ').toUpperCase();
      document.getElementById('headline-controller-sub').textContent = `Decision source: ${snap.control.source || controllerMode}.`;
      document.getElementById('headline-ball').textContent = ballHeadline;
      document.getElementById('headline-ball-sub').textContent = ballHeadlineSub;
      document.getElementById('headline-nn').textContent = neuralHeadline;
      document.getElementById('headline-nn-sub').textContent = neuralHeadlineSub;
      document.getElementById('runtime-state').textContent = visibleMode;
      document.getElementById('controller-mode').textContent = controllerMode;
      document.getElementById('runtime-pulse').className = ballLostWhileRunning ? 'pulse warn' : 'pulse live';
      document.getElementById('runtime-live-text').textContent = ballLostWhileRunning ? 'Ball lost' : `Receiving ${snap.mode.toLowerCase()} updates`;
      document.getElementById('ball-found').textContent = snap.ball.found ? 'Yes' : (ballLostWhileRunning ? 'Lost During Run' : 'No');
      document.getElementById('ball-pos').textContent = fmtPair(snap.ball.center_norm, 3);
      document.getElementById('ball-vel').textContent = fmtPair(snap.ball.velocity_norm, 2);
      document.getElementById('ball-conf').textContent = Number(snap.ball.confidence || 0).toFixed(2);
      document.getElementById('tilt').textContent = fmtPair([snap.control.tilt_x, snap.control.tilt_y], 2);
      document.getElementById('nn-status').textContent = nnStatusText;
      document.getElementById('nn-latency').textContent = `${Number(snap.neural.inference_ms || 0).toFixed(2)} ms`;
      document.getElementById('fps').textContent = Number(snap.fps || 0).toFixed(1);
      document.getElementById('calibration').textContent = `${Math.round((snap.board.progress || 0) * 100)}%`;
      document.getElementById('chip-runtime').textContent = visibleMode;
      document.getElementById('chip-controller').textContent = controllerMode;
      document.getElementById('chip-ball-status').textContent = snap.ball.found ? 'tracked' : (ballLostWhileRunning ? 'dead run' : 'missing');
      document.getElementById('chip-nn-state').textContent = snap.neural.active ? 'active' : (snap.neural.fallback_reason ? 'fallback' : snap.neural.mode || 'idle');
      document.getElementById('chip-runtime').parentElement.classList.toggle('active-chip', snap.mode === 'RUNNING' || ballLostWhileRunning);
      document.getElementById('chip-controller').parentElement.classList.toggle('active-chip', true);
      document.getElementById('chip-ball-status').parentElement.classList.toggle('active-chip', snap.ball.found || ballLostWhileRunning);
      document.getElementById('chip-nn-state').parentElement.classList.toggle('active-chip', snap.neural.active || Boolean(snap.neural.fallback_reason));
      setBar('bar-legacy-x', snap.control.legacy_tilt_x || 0, 'legacy', false);
      setBar('bar-legacy-y', snap.control.legacy_tilt_y || 0, 'legacy', false);
      setBar('bar-nn-x', snap.control.nn_tilt_x || 0, 'neural', snap.neural.active);
      setBar('bar-nn-y', snap.control.nn_tilt_y || 0, 'neural', snap.neural.active);
      setBar('bar-final-x', snap.control.tilt_x || 0, 'final', snap.neural.active || snap.control.source === 'neural');
      setBar('bar-final-y', snap.control.tilt_y || 0, 'final', snap.neural.active || snap.control.source === 'neural');
      document.getElementById('bar-legacy-x-value').textContent = Number(snap.control.legacy_tilt_x || 0).toFixed(2);
      document.getElementById('bar-legacy-y-value').textContent = Number(snap.control.legacy_tilt_y || 0).toFixed(2);
      document.getElementById('bar-nn-x-value').textContent = Number(snap.control.nn_tilt_x || 0).toFixed(2);
      document.getElementById('bar-nn-y-value').textContent = Number(snap.control.nn_tilt_y || 0).toFixed(2);
      document.getElementById('bar-final-x-value').textContent = Number(snap.control.tilt_x || 0).toFixed(2);
      document.getElementById('bar-final-y-value').textContent = Number(snap.control.tilt_y || 0).toFixed(2);
      document.getElementById('meta-disagreement').textContent = Number(snap.neural.disagreement || 0).toFixed(3);
      document.getElementById('meta-edge-risk').textContent = Number(snap.neural.edge_risk || 0).toFixed(2);
      document.getElementById('meta-inference').textContent = `${Number(snap.neural.inference_ms || 0).toFixed(2)} ms`;
      document.getElementById('meta-source').textContent = snap.control.source || 'legacy';
      document.getElementById('nn-explainer').textContent = snap.neural.active
        ? 'The NN is actively influencing the output right now.'
        : (friendlyFallback
          ? `The NN is not steering because: ${friendlyFallback}.`
          : 'The NN is loaded but currently shadowing the legacy controller.');
      document.getElementById('nn-callout').textContent = snap.neural.active
        ? `Neural command is live. Final output is currently coming from ${snap.control.source || 'the neural controller'}.`
        : (friendlyFallback
          ? `Fallback is protecting the run. Reason: ${friendlyFallback}. Legacy command still provides the safety baseline.`
          : `The network is thinking in ${controllerMode}. Compare NN bars to final bars to see how close it is to taking over.`);
      if (!snap.neural.active && rawFallback === 'predicted edge risk' && Number(snap.neural.disagreement || 0) >= 0.75) {
        document.getElementById('nn-callout').textContent = `Large legacy-vs-NN disagreement near the edge. This can mean either the NN is still immature or the legacy controller is the weaker pilot in this region, so these runs are especially valuable training data.`;
      }
      document.getElementById('raw').src = snap.raw_frame_b64 ? `data:image/jpeg;base64,${snap.raw_frame_b64}` : '';
      document.getElementById('mask').src = snap.mask_frame_b64 ? `data:image/jpeg;base64,${snap.mask_frame_b64}` : '';
      document.getElementById('raw-note').textContent = snap.raw_frame_b64 ? '' : (ballLostWhileRunning ? 'Ball lost. Press Ball Fell Off to reset quickly.' : (snap.mode === 'RUNNING' ? 'Preview disabled while RUNNING for performance.' : ''));
      document.getElementById('mask-note').textContent = snap.mask_frame_b64 ? '' : (ballLostWhileRunning ? 'Ball lost. Place the ball back and reset the run.' : (snap.mode === 'RUNNING' ? 'Preview disabled while RUNNING for performance.' : ''));
      markModeButtons(controllerMode);
      if (pendingCommand) {
        const acknowledged =
          (pendingCommand === 'RUN' && snap.mode === 'RUNNING') ||
          (pendingCommand === 'PAUSE' && snap.mode === 'PAUSED') ||
          (pendingCommand === 'STOP' && snap.mode === 'STOPPED') ||
          (pendingCommand === 'BALL_FELL_OFF' && snap.mode === 'STOPPED') ||
          (pendingCommand === 'RECALIBRATE' && snap.mode === 'CALIBRATING');
        if (acknowledged || (Date.now() - lastCommandAt) > 1500) {
          setPendingButton(`btn-${pendingCommand}`, false);
          if (acknowledged) {
            updateCommandLog(`${pendingCommand.replaceAll('_', ' ')} acknowledged by runtime.`);
          }
          pendingCommand = null;
        }
      }
      if (pendingMode && snap.controller_mode === pendingMode) {
        updateCommandLog(`Controller mode switched to ${pendingMode}.`);
        pendingMode = null;
        markModeButtons(snap.controller_mode || 'legacy');
      }
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
