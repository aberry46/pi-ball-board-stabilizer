from __future__ import annotations

import json
import socket


class RuntimeIpcClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port

    def request(self, payload: dict) -> dict:
        with socket.create_connection((self.host, self.port), timeout=1.0) as sock:
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            data = b""
            while not data.endswith(b"\n"):
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        if not data:
            return {"ok": False, "error": "no response from runtime"}
        return json.loads(data.decode("utf-8"))
