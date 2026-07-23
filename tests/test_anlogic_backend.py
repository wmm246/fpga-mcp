"""End-to-end test: spin up a mock Tcl TCP server and drive the Anlogic
TangDynasty backend against it.

Same pattern as the Vivado / Quartus tests. Proves the Anlogic backend's
command construction actually parses server-side responses.

Note: the Anlogic backend uses ``_safe_tcl`` (not raw ``_tcl``) for many
queries, which wraps the command in ``if {[catch {CMD} rc]} ...; return $rc``.
The mock handlers therefore use substring (``in``) checks rather than
``startswith`` so they match both the wrapped and unwrapped forms.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fpga_mcp.config import BackendConfig, Config
from fpga_mcp.transports.anlogic import AnlogicBackend

from tests._mock_tcl_server import MockTclServer


@pytest.fixture
def mock_server():
    state: dict = {"project_open": False, "current_name": None}

    def handler(cmd: str) -> str:
        cmd = cmd.strip()
        if "create_project -name" in cmd:
            state["project_open"] = True
            state["current_name"] = "blink"
            return ""
        if "open_project" in cmd and "create_project" not in cmd:
            state["project_open"] = True
            return ""
        if "close_project" in cmd:
            state["project_open"] = False
            return ""
        if "catch {current_project}" in cmd:
            return "0" if state["project_open"] else "1"
        # current_project (raw) — but careful not to match catch {current_project}
        if "current_project" in cmd and "catch" not in cmd:
            return state["current_name"] or ""
        if "get_part" in cmd:
            return "EG4S20BG256"
        if "get_top" in cmd:
            return "blink_top"
        if "get_project_dir" in cmd:
            return "/tmp"
        if "add_file" in cmd or "add_constraint" in cmd:
            return ""
        if "add_include_dir" in cmd:
            return ""
        if "set_top" in cmd:
            return ""
        if "run_syn" in cmd:
            return ""
        if "run_pnr" in cmd:
            return ""
        if "report_timing" in cmd:
            return "WNS: 1.500ns\nTNS: 0.000ns\n"
        if "report_utilization" in cmd:
            return "LUTs : 100/1000 (10.0%)\nFFs : 50/2000 (2.5%)\n"
        if "generate_bitstream" in cmd:
            return ""
        if "export_simulation" in cmd:
            return ""
        return ""

    server = MockTclServer(handler, port=0, banner_name="fpga-mcp/anlogic-server")
    server.start()
    yield server
    server.stop()


@pytest.fixture
def anlogic_backend(mock_server) -> AnlogicBackend:
    cfg = Config(
        active_backend="anlogic",
        backends=BackendConfig(
            anlogic_host="127.0.0.1",
            anlogic_port=mock_server.port,
        ),
    )
    b = AnlogicBackend(cfg)
    b.connect()
    yield b
    b.disconnect()


def test_anlogic_backend_creates_project(anlogic_backend):
    h = anlogic_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="EG4S20BG256",
        top="blink_top",
    )
    assert h.name == "blink"
    assert h.part == "EG4S20BG256"
    assert h.top == "blink_top"
    assert h.backend == "anlogic"


def test_anlogic_backend_adds_sources(anlogic_backend):
    f = Path("/tmp/test_anlogic_src.v")
    f.write_text("module foo; endmodule", encoding="utf-8")
    n = anlogic_backend.add_sources([f])
    assert n == 1


def test_anlogic_backend_reports_timing(anlogic_backend):
    anlogic_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="EG4S20BG256",
    )
    r = anlogic_backend.report_timing(max_paths=5)
    assert r.wns_ns == pytest.approx(1.500, abs=0.001)


def test_anlogic_backend_reports_utilization(anlogic_backend):
    anlogic_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="EG4S20BG256",
    )
    r = anlogic_backend.report_utilization()
    rows = {row.resource.lower(): row for row in r.rows}
    assert "luts" in rows
    assert rows["luts"].used == 100
    assert rows["luts"].available == 1000


def test_anlogic_backend_runs_synthesis(anlogic_backend):
    anlogic_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="EG4S20BG256",
    )
    r = anlogic_backend.run_synthesis()
    assert r.ok is True
    assert r.stage == "synthesis"


def test_anlogic_backend_exec_tcl(anlogic_backend):
    anlogic_backend.create_project(
        name="blink",
        directory=Path("/tmp"),
        part="EG4S20BG256",
    )
    out = anlogic_backend.exec_tcl("get_part")
    assert out.strip() == "EG4S20BG256"


def test_anlogic_disconnect_is_idempotent(anlogic_backend):
    anlogic_backend.disconnect()
    anlogic_backend.disconnect()
