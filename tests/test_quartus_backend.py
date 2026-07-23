"""End-to-end test: spin up a mock Tcl TCP server and drive the Quartus
backend against it.

Same pattern as ``test_vivado_backend.py`` but with Quartus commands/responses.
Proves the Quartus backend's command construction actually parses server-side
responses.

Note: the Quartus backend uses ``_safe_tcl`` (not raw ``_tcl``) for many
queries, which wraps the command in ``if {[catch {CMD} rc]} ...; return $rc``.
The mock handlers therefore use substring (``in``) checks rather than
``startswith`` so they match both the wrapped and unwrapped forms.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fpga_mcp.config import BackendConfig, Config
from fpga_mcp.transports.quartus import QuartusBackend

from tests._mock_tcl_server import MockTclServer


@pytest.fixture
def mock_server():
    state: dict = {"project_open": False, "current_name": None}

    def handler(cmd: str) -> str:
        cmd = cmd.strip()
        # project_new / set_global_assignment / project_open
        if "project_new" in cmd:
            state["project_open"] = True
            state["current_name"] = "blink"
            return ""
        if "set_global_assignment" in cmd:
            return ""
        if "project_open" in cmd and "project_new" not in cmd:
            state["project_open"] = True
            return ""
        if "project_close" in cmd:
            state["project_open"] = False
            return ""
        if "is_project_open" in cmd:
            return "1" if state["project_open"] else "0"
        if "get_current_revision" in cmd:
            return "blink"
        if "get_global_assignment" in cmd:
            if "DEVICE" in cmd:
                return "5CGXFC5C6F23C7"
            if "FAMILY" in cmd:
                return "Cyclone V"
            if "TOP_LEVEL_ENTITY" in cmd:
                return "blink_top"
            return ""
        if cmd.startswith("cd "):
            return ""
        if "add_file" in cmd or "add_constraint" in cmd:
            return ""
        if "set_top" in cmd:
            return ""
        if "execute_module" in cmd:
            # The Quartus backend treats execute_module as the synth/fit/asm
            # stage trigger — return success (empty string) so _run_module
            # marks the stage ok.
            return ""
        if "report_timing" in cmd:
            return "Worst-case Slack 1.234\nTotal Negative Slack 0.000\n"
        if "report_resource" in cmd:
            return "LUTs : 100/1000\nFFs : 50/2000\n"
        if "create_timing_netlist" in cmd or "read_sdc" in cmd or "update_timing_netlist" in cmd:
            return ""
        return ""

    server = MockTclServer(handler, port=0, banner_name="fpga-mcp/quartus-server")
    server.start()
    yield server
    server.stop()


@pytest.fixture
def quartus_backend(mock_server) -> QuartusBackend:
    cfg = Config(
        active_backend="quartus",
        backends=BackendConfig(
            quartus_host="127.0.0.1",
            quartus_port=mock_server.port,
        ),
    )
    b = QuartusBackend(cfg)
    b.connect()
    yield b
    b.disconnect()


def test_quartus_backend_creates_project(quartus_backend):
    h = quartus_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="5CGXFC5C6F23C7",
        top="blink_top",
    )
    assert h.name == "blink"
    assert h.part == "5CGXFC5C6F23C7"
    assert h.top == "blink_top"
    assert h.backend == "quartus"
    assert h.meta.get("family") == "Cyclone V"


def test_quartus_backend_adds_sources(quartus_backend):
    f = Path("/tmp/test_quartus_src.v")
    f.write_text("module foo; endmodule", encoding="utf-8")
    n = quartus_backend.add_sources([f])
    assert n == 1


def test_quartus_backend_reports_timing(quartus_backend):
    quartus_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="5CGXFC5C6F23C7",
    )
    r = quartus_backend.report_timing(max_paths=5)
    assert r.wns_ns == pytest.approx(1.234, abs=0.001)


def test_quartus_backend_runs_synthesis(quartus_backend):
    quartus_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="5CGXFC5C6F23C7",
    )
    r = quartus_backend.run_synthesis()
    assert r.ok is True
    assert r.stage == "synthesis"


def test_quartus_backend_exec_tcl(quartus_backend):
    quartus_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="5CGXFC5C6F23C7",
    )
    # Ask for the revision (mock returns "blink").
    out = quartus_backend.exec_tcl("get_current_revision")
    assert out.strip() == "blink"


def test_quartus_disconnect_is_idempotent(quartus_backend):
    quartus_backend.disconnect()
    quartus_backend.disconnect()
