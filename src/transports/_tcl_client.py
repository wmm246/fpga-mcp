"""Tcl clients shared by the EDA backends.

Two transports are provided:

* :class:`TclClient` — connects to a running Tcl TCP server (e.g.
  ``tcl/vivado_server.tcl`` sourced inside a Vivado GUI instance).
  Fastest, but requires the user to start Vivado manually.

* :class:`SubprocessTclClient` — launches ``vivado -mode tcl`` as a
  persistent subprocess and communicates via stdin/stdout pipes using
  ``tcl/vivado_stdio_bridge.tcl``.  This transport does NOT rely on
  Vivado's socket event loop (which does not process ``socket -server``
  callbacks) and is the recommended default.

Both speak the same newline-delimited JSON protocol, so backends can
switch between them transparently.
"""

from __future__ import annotations

import json
import logging
import socket
import subprocess
from dataclasses import dataclass

log = logging.getLogger("fpga_mcp.tcl_client")


@dataclass
class TclResponse:
    id: int
    ok: bool
    result: str
    error: str


class TclClientError(RuntimeError):
    pass


class TclClientTimeout(TclClientError):
    pass


class TclClient:
    """Synchronous client for the fpga-mcp Tcl server protocol.

    One persistent socket; ``request`` is reentrant-safe at the protocol level
    (the request id increments on every call) but only one request may be in
    flight at a time on a single socket.
    """

    BANNER_PREFIX = b"READY"

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9999,
        *,
        connect_timeout: float = 5.0,
        default_timeout: float = 600.0,
    ):
        self._host = host
        self._port = port
        self._connect_timeout = connect_timeout
        self._default_timeout = default_timeout
        self._sock: socket.socket | None = None
        self._next_id = 1
        # When True, use plain-text Tcl protocol (synthpilot-compatible)
        # instead of JSON-over-TCP (fpga-mcp native protocol).
        self._plain_text_mode: bool = False

    # --- connection management ----------------------------------------

    def connect(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection((self._host, self._port), timeout=self._connect_timeout)
        # Try to read the READY banner with a short timeout. Some Tcl servers
        # (e.g. synthpilot's) don't send a banner — they just wait for the
        # client to send a command. In that case we switch to plain-text
        # Tcl protocol mode for compatibility.
        sock.settimeout(0.5)
        try:
            banner = self._recv_line(sock)
            if not banner.startswith(self.BANNER_PREFIX):
                sock.close()
                raise TclClientError(
                    f"unexpected banner from server: {banner!r} (expected b'READY ...')"
                )
        except (socket.timeout, TimeoutError):
            # No banner received within 0.5s — switch to plain-text mode.
            self._plain_text_mode = True
        except Exception as exc:
            sock.close()
            raise TclClientError(f"no banner from {self._host}:{self._port}: {exc}") from exc
        sock.settimeout(None)  # per-request timeout applied in request()
        self._sock = sock

    def disconnect(self) -> None:
        if self._sock is not None:
            if not self._plain_text_mode:
                try:
                    self._send_raw({"id": 0, "cmd": "omni_stop", "timeout": 0})
                except OSError:
                    pass
            try:
                self._sock.close()
            finally:
                self._sock = None

    def is_connected(self) -> bool:
        if self._sock is None:
            return False
        # Cheap liveness probe: peek into the recv buffer without blocking.
        try:
            self._sock.setblocking(False)
            try:
                data = self._sock.recv(1, socket.MSG_PEEK)
                if data == b"":
                    return False  # peer closed
                return True
            finally:
                self._sock.setblocking(True)
        except BlockingIOError:
            return True
        except OSError:
            return False

    # --- protocol ----------------------------------------------------

    def request(self, cmd: str, *, timeout: float | None = None) -> str:
        """Send ``cmd`` and return the result string. Raise on error."""
        if self._sock is None:
            raise TclClientError("not connected — call connect() first")
        timeout = timeout if timeout is not None else self._default_timeout
        self._sock.settimeout(timeout)

        if self._plain_text_mode:
            return self._request_plain_text(cmd, timeout)
        return self._request_json(cmd, timeout)

    def _request_json(self, cmd: str, timeout: float) -> str:
        """JSON-over-TCP protocol (fpga-mcp native)."""
        rid = self._next_id
        self._next_id += 1
        self._send_raw({"id": rid, "cmd": cmd, "timeout": timeout})
        line = self._recv_line(self._sock)
        try:
            obj = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise TclClientError(f"malformed response: {line!r}") from exc
        resp = TclResponse(
            id=int(obj.get("id", -1)),
            ok=bool(obj.get("ok", False)),
            result=str(obj.get("result", "")),
            error=str(obj.get("error", "")),
        )
        if not resp.ok:
            if "timeout" in resp.error.lower():
                raise TclClientTimeout(resp.error)
            raise TclClientError(resp.error or "tcl command failed")
        return resp.result

    def _request_plain_text(self, cmd: str, timeout: float) -> str:
        """Plain-text Tcl protocol (synthpilot-compatible).

        Protocol:
          Request:  cmd\n
          Response: result_text\r\n<<<END>>>\r\n

        Errors are prefixed with 'ERROR: '.
        Commands with no output return 'OK'.
        """
        assert self._sock is not None
        data = (cmd + "\n").encode("utf-8")
        self._sock.sendall(data)
        raw = self._recv_until_delimiter(self._sock)
        text = raw.decode("utf-8", errors="replace")
        # Strip trailing whitespace/newlines
        text = text.rstrip("\r\n")
        # Check for errors
        if text.startswith("ERROR:"):
            err_msg = text[len("ERROR:"):].strip()
            if "timeout" in err_msg.lower():
                raise TclClientTimeout(err_msg)
            raise TclClientError(err_msg or "tcl command failed")
        # 'OK' means success with no output
        if text == "OK":
            return ""
        return text

    # --- internals ---------------------------------------------------

    def _send_raw(self, payload: dict) -> None:
        assert self._sock is not None
        data = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        self._sock.sendall(data)

    @staticmethod
    def _recv_line(sock: socket.socket, *, max_bytes: int = 64 * 1024 * 1024) -> bytes:
        # Buffer until we see a newline. Single-line JSON responses; large
        # outputs (timing summaries) can be tens of KB but never multiline.
        chunks: list[bytes] = []
        total = 0
        while total < max_bytes:
            ch = sock.recv(1)
            if not ch:
                raise TclClientError("connection closed by peer mid-response")
            if ch == b"\n":
                break
            chunks.append(ch)
            total += 1
        else:
            raise TclClientError(f"response exceeded {max_bytes} bytes")
        return b"".join(chunks)

    @staticmethod
    def _recv_until_delimiter(
        sock: socket.socket,
        delimiter: bytes = b"<<<END>>>",
        *,
        max_bytes: int = 64 * 1024 * 1024,
    ) -> bytes:
        """Read from socket until the delimiter is found.

        Returns everything *before* the delimiter (the delimiter itself is
        consumed and discarded). Used by the plain-text protocol mode.
        """
        chunks: list[bytes] = []
        total = 0
        delim_len = len(delimiter)
        while total < max_bytes:
            ch = sock.recv(1)
            if not ch:
                raise TclClientError("connection closed by peer mid-response")
            chunks.append(ch)
            total += 1
            # Check if we just completed the delimiter
            if total >= delim_len:
                tail = b"".join(chunks[-delim_len:])
                if tail == delimiter:
                    # Consume trailing CRLF after delimiter
                    try:
                        sock.recv(2)
                    except OSError:
                        pass
                    return b"".join(chunks[:-delim_len])
        raise TclClientError(f"response exceeded {max_bytes} bytes without delimiter")

    # --- convenience -------------------------------------------------

    def eval(self, tcl: str, *, timeout: float | None = None) -> str:
        """Alias for ``request``. Read a Tcl expression."""
        return self.request(tcl, timeout=timeout)

    def ping(self) -> bool:
        try:
            self.request("return -code ok connected", timeout=2.0)
            return True
        except (TclClientError, OSError):
            return False

    def __enter__(self) -> "TclClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()


class SubprocessTclClient:
    """Drive Vivado via stdin/stdout pipes (no TCP server needed).

    Launches ``vivado -mode tcl -source tcl/vivado_stdio_bridge.tcl`` as a
    persistent subprocess.  Commands are sent as newline-delimited JSON on
    stdin; responses are read as newline-delimited JSON from stdout.

    This transport exists because Vivado's Tcl event loop does not process
    ``socket -server`` accept callbacks, making the TCP server approach
    unreliable (the ``omni_accept`` callback never fires, so clients never
    receive the READY banner).

    The wire format is identical to the TCP protocol, so ``VivadoBackend``
    can switch between ``TclClient`` and ``SubprocessTclClient`` transparently.
    """

    BANNER_PREFIX = "READY"

    def __init__(
        self,
        vivado_path: str,
        bridge_script: str,
        *,
        connect_timeout: float = 60.0,
        default_timeout: float = 7200.0,
    ):
        self._vivado_path = vivado_path
        self._bridge_script = bridge_script
        self._connect_timeout = connect_timeout
        self._default_timeout = default_timeout
        self._proc: subprocess.Popen | None = None
        self._next_id = 1
        self._stderr_lines: list[str] = []

    # --- connection management ----------------------------------------

    def connect(self) -> None:
        if self._proc is not None:
            return
        cmd = [
            self._vivado_path,
            "-mode", "tcl",
            "-source", self._bridge_script,
        ]
        log.debug("SubprocessTclClient: launching %s", " ".join(cmd))
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # line-buffered
        )
        # Start a daemon thread to drain stderr (prevents pipe deadlock).
        import threading
        def _drain_stderr():
            assert self._proc is not None
            assert self._proc.stderr is not None
            for line in self._proc.stderr:
                self._stderr_lines.append(line)
                if len(self._stderr_lines) > 500:
                    self._stderr_lines.pop(0)
        t = threading.Thread(target=_drain_stderr, daemon=True)
        t.start()
        # Wait for READY banner (Vivado takes 10-40s to start).
        # Skip Vivado's startup output and Tcl script echo lines until
        # we find the READY line from our bridge script.
        banner = self._read_until_ready(timeout=self._connect_timeout)
        if not banner:
            self._kill()
            raise TclClientError(
                "No READY banner from Vivado subprocess within "
                f"{self._connect_timeout}s. "
                f"stderr tail: {''.join(self._stderr_lines[-20:])}"
            )
        log.debug("SubprocessTclClient: got banner %r", banner)

    def disconnect(self) -> None:
        if self._proc is None:
            return
        try:
            self._send_raw({"id": 0, "cmd": "omni_stop", "timeout": 0})
        except OSError:
            pass
        self._kill()

    def _kill(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
                self._proc.wait(timeout=5)
            except Exception:
                pass
        self._proc = None

    def is_connected(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # --- protocol ----------------------------------------------------

    def request(self, cmd: str, *, timeout: float | None = None) -> str:
        if self._proc is None:
            raise TclClientError("not connected — call connect() first")
        timeout = timeout if timeout is not None else self._default_timeout
        rid = self._next_id
        self._next_id += 1
        self._send_raw({"id": rid, "cmd": cmd, "timeout": timeout})
        # Read lines until we get a valid JSON response. Vivado's Tcl
        # interactive mode may echo script lines (prefixed with #) or
        # print info messages to stdout — skip those.
        import time as _time
        deadline = _time.monotonic() + timeout
        while True:
            remaining = deadline - _time.monotonic()
            if remaining <= 0:
                raise TclClientTimeout(
                    f"timed out after {timeout}s waiting for response. "
                    f"stderr tail: {''.join(self._stderr_lines[-20:])}"
                )
            line = self._read_line(timeout=remaining).strip()
            if not line or not line.startswith("{"):
                log.debug("SubprocessTclClient: skipping non-JSON line: %r", line[:80])
                continue
            try:
                obj = json.loads(line)
                break
            except json.JSONDecodeError:
                log.debug("SubprocessTclClient: bad JSON line: %r", line[:80])
                continue
        resp = TclResponse(
            id=int(obj.get("id", -1)),
            ok=bool(obj.get("ok", False)),
            result=str(obj.get("result", "")),
            error=str(obj.get("error", "")),
        )
        if not resp.ok:
            if "timeout" in resp.error.lower():
                raise TclClientTimeout(resp.error)
            raise TclClientError(resp.error or "tcl command failed")
        return resp.result

    # --- internals ---------------------------------------------------

    def _send_raw(self, payload: dict) -> None:
        assert self._proc is not None
        assert self._proc.stdin is not None
        # text=True mode: stdin is a text stream, write strings directly.
        data = json.dumps(payload, separators=(",", ":")) + "\n"
        self._proc.stdin.write(data)
        self._proc.stdin.flush()

    def _read_line(self, *, timeout: float = 60.0) -> str:
        """Read one line from stdout with a timeout via threading."""
        assert self._proc is not None
        assert self._proc.stdout is not None
        import queue
        import threading
        q: queue.Queue[str | None] = queue.Queue()
        def _reader():
            try:
                line = self._proc.stdout.readline()  # type: ignore[union-attr]
                q.put(line if line else None)
            except Exception:
                q.put(None)
        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        try:
            result = q.get(timeout=timeout)
        except Exception:
            raise TclClientTimeout(
                f"timed out after {timeout}s waiting for Vivado response. "
                f"stderr tail: {''.join(self._stderr_lines[-20:])}"
            )
        if result is None:
            raise TclClientError(
                "Vivado subprocess closed stdout. "
                f"stderr tail: {''.join(self._stderr_lines[-20:])}"
            )
        return result.rstrip("\r\n")

    def _read_until_ready(self, *, timeout: float = 120.0) -> str:
        """Read lines from stdout until we find the READY banner.

        Vivado's Tcl shell echoes the sourced script lines (prefixed with
        ``#``) and prints its own startup banner before our bridge script
        runs.  We skip all of those and return the first line starting
        with ``READY``.
        """
        import time as _time
        deadline = _time.monotonic() + timeout
        while True:
            remaining = deadline - _time.monotonic()
            if remaining <= 0:
                return ""
            line = self._read_line(timeout=remaining)
            if line.startswith(self.BANNER_PREFIX):
                return line
            # Skip non-READY lines (Vivado banner, script echoes, etc.)
            log.debug("SubprocessTclClient: skipping line: %r", line)

    # --- convenience -------------------------------------------------

    def eval(self, tcl: str, *, timeout: float | None = None) -> str:
        return self.request(tcl, timeout=timeout)

    def ping(self) -> bool:
        try:
            self.request("return -code ok connected", timeout=5.0)
            return True
        except (TclClientError, OSError):
            return False

    def __enter__(self) -> "SubprocessTclClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()
