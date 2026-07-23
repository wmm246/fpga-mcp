"""Tiny in-process Tcl TCP server stub for tests.

Speaks the exact fpga-mcp wire protocol (newline-delimited JSON) so we
can exercise the Python client + a real backend end-to-end without Vivado /
Quartus / Anlogic installed.
"""

from __future__ import annotations

import json
import socket
import threading
from typing import Callable


class MockTclServer:
    """One-connection-per-thread mock of the fpga-mcp Tcl server.

    Pass a ``handler`` callable that receives the Tcl command string and
    returns the result string. Raise inside the handler to produce an error
    response.
    """

    def __init__(self, handler: Callable[[str], str], *, port: int = 0, banner_name: str = "mock"):
        self._handler = handler
        self._port = port
        self._banner = f"READY {banner_name} 1.0"
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def port(self) -> int:
        if self._sock is None:
            raise RuntimeError("server not started")
        return self._sock.getsockname()[1]

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", self._port))
        self._sock.listen(4)
        self._sock.settimeout(0.2)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)

    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(target=self._handle, args=(conn,), daemon=True)
            t.start()

    def _handle(self, conn: socket.socket) -> None:
        conn.settimeout(2.0)
        # Send banner.
        conn.sendall((self._banner + "\n").encode("utf-8"))
        buf = b""
        while not self._stop.is_set():
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    envelope = json.loads(line)
                    cmd = envelope.get("cmd", "")
                    rid = envelope.get("id", 0)
                    try:
                        result = self._handler(cmd)
                        resp = {"id": rid, "ok": True, "result": str(result), "error": ""}
                    except Exception as exc:
                        resp = {"id": rid, "ok": False, "result": "", "error": str(exc)}
                except json.JSONDecodeError as exc:
                    resp = {"id": 0, "ok": False, "result": "", "error": f"bad json: {exc}"}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
        try:
            conn.close()
        except OSError:
            pass
