from __future__ import annotations

import json
import socketserver
import threading
from queue import Empty, Queue
from typing import Any

from .models import RuntimeSnapshot


class RuntimeCommandQueue:
    def __init__(self) -> None:
        self._queue: Queue[dict[str, Any]] = Queue()

    def put(self, command: dict[str, Any]) -> None:
        self._queue.put(command)

    def drain(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except Empty:
                return items


class RuntimeSnapshotStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot = RuntimeSnapshot()

    def set(self, snapshot: RuntimeSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot

    def get(self) -> RuntimeSnapshot:
        with self._lock:
            return self._snapshot


class _Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline()
        if not line:
            return
        payload = json.loads(line.decode("utf-8"))
        action = payload.get("action", "")

        if action in {"RUN", "PAUSE", "STOP", "RECALIBRATE", "BALL_FELL_OFF"}:
            self.server.command_queue.put({"action": action})  # type: ignore[attr-defined]
            response = {"ok": True, "accepted": action}
        elif action == "SET_CONTROLLER_MODE":
            mode = payload.get("mode", "")
            self.server.command_queue.put({"action": action, "mode": mode})  # type: ignore[attr-defined]
            response = {"ok": True, "accepted": action, "mode": mode}
        elif action == "GET_STATE":
            response = {"ok": True, "snapshot": self.server.snapshot_store.get().to_dict()}  # type: ignore[attr-defined]
        elif action == "PING":
            response = {"ok": True, "pong": True}
        else:
            response = {"ok": False, "error": f"unknown action: {action}"}

        self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, address, handler, snapshot_store: RuntimeSnapshotStore, command_queue: RuntimeCommandQueue):
        super().__init__(address, handler)
        self.snapshot_store = snapshot_store
        self.command_queue = command_queue


class RuntimeIpcServer:
    def __init__(self, host: str, port: int, snapshot_store: RuntimeSnapshotStore, command_queue: RuntimeCommandQueue) -> None:
        self.server = _Server((host, port), _Handler, snapshot_store, command_queue)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
