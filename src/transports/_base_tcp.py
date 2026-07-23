"""Common scaffolding for the TCP-backed EDA drivers.

Vivado, Quartus and Anlogic all speak the same JSON-over-TCP protocol
(see ``tcl/_omni_protocol.tcl``). Their lifecycle (connect / disconnect /
is_connected / exec_tcl) is identical; only the Tcl commands they emit
differ. This base captures the common plumbing so each concrete backend
stays focused on vendor-specific Tcl.
"""

from __future__ import annotations

from fpga_mcp.config import Config
from fpga_mcp.transports._tcl_client import TclClient, TclClientError
from fpga_mcp.transports.base import (
    BackendError,
    BackendNotConnectedError,
    ProjectHandle,
)


class BaseTcpBackend:
    """Holds a :class:`TclClient` and implements the common lifecycle."""

    #: Backend identifier; subclasses set this.
    name: str = "base"
    #: Default port used when the config does not specify one.
    default_port: int = 9999

    def __init__(self, config: Config):
        self._config = config
        b = config.backends
        host, port = self._pick_host_port(b)
        self._client = TclClient(host=host, port=port, connect_timeout=5.0, default_timeout=14400.0)
        self._current: ProjectHandle | None = None

    # --- subclasses customise this --------------------------------------

    def _pick_host_port(self, b):
        """Return ``(host, port)`` from the per-backend config block."""
        return b.vivado_host, b.vivado_port

    def _start_hint(self) -> str:
        return (
            "  See the matching tcl/<vendor>_server.tcl script for how to start the Tcl TCP server."
        )

    # --- common lifecycle ----------------------------------------------

    def connect(self) -> None:
        try:
            self._client.connect()
        except (TclClientError, OSError) as exc:
            raise BackendNotConnectedError(
                self.name,
                hint=(
                    f"Could not reach Tcl server at "
                    f"{self._client._host}:{self._client._port}. "
                    f"{self._start_hint()}\nOriginal error: {exc}"
                ),
            ) from exc

    def disconnect(self) -> None:
        self._client.disconnect()
        self._current = None

    def is_connected(self) -> bool:
        return self._client.is_connected()

    # --- common Tcl plumbing -------------------------------------------

    def _tcl(self, command: str, *, timeout: float | None = None) -> str:
        if not self.is_connected():
            try:
                self.connect()
            except BackendError:
                raise
        return self._client.request(command, timeout=timeout)

    def _safe_tcl(self, command: str, default: str = "") -> str:
        from fpga_mcp.transports._tcl_helpers import tcl_quote

        wrapped = (
            "if {[catch {" + command + "} rc]} {set rc " + tcl_quote(default) + "}; return $rc"
        )
        try:
            return self._tcl(wrapped).strip()
        except TclClientError:
            return default

    def _require_project(self) -> None:
        if self.current_project() is None:
            raise BackendError(
                f"no active {self.name} project — call create_project or open_project first"
            )

    # --- escape hatch (shared) -----------------------------------------

    def exec_tcl(self, command: str, *, timeout: float | None = None) -> str:
        return self._tcl(command, timeout=timeout)
