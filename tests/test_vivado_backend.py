"""End-to-end test: spin up a mock Tcl TCP server and drive the Vivado
backend against it. Proves the wire protocol is correct and that the
backend's Tcl construction actually parses server-side responses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fpga_mcp.config import BackendConfig, Config
from fpga_mcp.transports._tcl_client import TclClient
from fpga_mcp.transports.vivado import VivadoBackend

from tests._mock_tcl_server import MockTclServer


@pytest.fixture
def mock_server():
    """A mock Tcl server that simulates Vivado responses."""
    state: dict = {"project_open": False, "current_name": None}

    def handler(cmd: str) -> str:
        cmd = cmd.strip()
        # Map common Vivado commands to canned responses.
        if cmd == "return -code ok connected":
            return "connected"
        if cmd.startswith("create_project"):
            state["project_open"] = True
            state["current_name"] = "blink"
            return ""
        if cmd.startswith("set_property target_language"):
            return ""
        if cmd.startswith("set_property top"):
            return ""
        if cmd.startswith("update_compile_order"):
            return ""
        if cmd.startswith("open_project"):
            state["project_open"] = True
            return ""
        if cmd.startswith("current_project"):
            return "blink" if state["project_open"] else ""
        if cmd.startswith("get_property PART"):
            return "xc7a35tcpg236-1"
        if cmd.startswith("get_property top"):
            return "blink_top"
        if cmd.startswith("get_property DIRECTORY"):
            return "/tmp"
        if cmd.startswith("get_property STATUS"):
            return "synth_design Complete!"
        if cmd.startswith("launch_runs") or cmd.startswith("wait_on_run"):
            return ""
        if cmd.startswith("add_files"):
            return ""
        if cmd.startswith("report_timing_summary"):
            # Return a realistic-looking timing summary.
            return """
+-------------------------+
| Design Timing Summary   |
+-------------------------+
| Clock        | WNS(ns) | TNS(ns) |
|--------------|---------|---------|
| clk_in       |  +2.341 |   0.000 |
"""
        if cmd.startswith("report_utilization"):
            return """
+----------------+--------+--------+----+
| Resource       | Used   | Avail  | %  |
|----------------|--------|--------|----|
| Slice LUTs     |  1000  |  20000 | 5  |
| Slice Regs     |   500  |  40000 | 1  |
| Block RAM Tile |     2  |    100 | 2  |
"""
        if cmd.startswith("close_project"):
            state["project_open"] = False
            return ""
        # Generic fallback: empty string.
        return ""

    server = MockTclServer(handler, port=0, banner_name="fpga-mcp/vivado-server")
    server.start()
    yield server
    server.stop()


@pytest.fixture
def vivado_backend(mock_server) -> VivadoBackend:
    cfg = Config(
        active_backend="vivado",
        backends=BackendConfig(
            vivado_host="127.0.0.1",
            vivado_port=mock_server.port,
        ),
    )
    b = VivadoBackend(cfg)
    b.connect()
    yield b
    b.disconnect()


def test_client_banner_handshake(mock_server):
    client = TclClient(host="127.0.0.1", port=mock_server.port, connect_timeout=2.0)
    client.connect()
    assert client.is_connected()
    result = client.request("return -code ok connected")
    assert result == "connected"
    client.disconnect()


def test_vivado_backend_creates_project(vivado_backend):
    h = vivado_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="xc7a35tcpg236-1",
        top="blink_top",
    )
    assert h.name == "blink"
    assert h.part == "xc7a35tcpg236-1"
    assert h.top == "blink_top"
    assert h.backend == "vivado"


def test_vivado_backend_adds_sources(vivado_backend):
    # Use existing files on disk so Path().resolve() doesn't choke.
    f = Path("/tmp/test_src.v")
    f.write_text("module foo; endmodule", encoding="utf-8")
    n = vivado_backend.add_sources([f])
    assert n == 1


def test_vivado_backend_reports_timing(vivado_backend):
    vivado_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="xc7a35tcpg236-1",
    )
    r = vivado_backend.report_timing(max_paths=5)
    assert r.wns_ns == pytest.approx(2.341, abs=0.001)
    assert r.tns_ns == pytest.approx(0.0, abs=0.001)
    # No failing paths in the canned report.
    assert r.failing_paths == []


def test_vivado_backend_reports_utilization(vivado_backend):
    vivado_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="xc7a35tcpg236-1",
    )
    r = vivado_backend.report_utilization()
    assert any(row.resource.lower().startswith("slice lut") for row in r.rows)
    # Find the LUT row and check the values.
    lut = next(row for row in r.rows if "lut" in row.resource.lower())
    assert lut.used == 1000
    assert lut.available == 20000


def test_exec_tcl_escape_hatch(vivado_backend):
    # Create a project first so current_project has a value to return.
    vivado_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="xc7a35tcpg236-1",
    )
    out = vivado_backend.exec_tcl("current_project")
    assert out == "blink"


def test_disconnect_is_idempotent(vivado_backend):
    vivado_backend.disconnect()
    vivado_backend.disconnect()  # should not raise
