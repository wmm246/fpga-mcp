#!/usr/bin/env python3
"""End-to-end smoke test for fpga-mcp.

Spins up the mock Tcl server three times (once per vendor), drives each
backend through a minimal flow, and asserts the round-trip works. Exits
non-zero on any failure.

This script is what the CI `smoke` job runs. It complements (but does not
replace) the pytest suite — pytest tests cover the per-method details,
this script is a "did the whole stack wire up correctly on this OS / Python
combo" canary.

Usage:
    python3 scripts/smoke_e2e.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Make src/ importable when run from a CI checkout (no install needed).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from fpga_mcp.config import BackendConfig, Config  # noqa: E402
from fpga_mcp.transports.anlogic import AnlogicBackend  # noqa: E402
from fpga_mcp.transports.quartus import QuartusBackend  # noqa: E402
from fpga_mcp.transports.vivado import VivadoBackend  # noqa: E402

# Reuse the test-suite mock server.
sys.path.insert(0, str(ROOT / "tests"))
from _mock_tcl_server import MockTclServer  # noqa: E402


# ---------------------------------------------------------------------------
# Vivado
# ---------------------------------------------------------------------------


def smoke_vivado() -> None:
    def handler(cmd: str) -> str:
        cmd = cmd.strip()
        if "create_project" in cmd:
            return ""
        if "get_part" in cmd and "set_property" not in cmd:
            return "xc7a35tcpg236-1"
        if "current_project" in cmd and "catch" not in cmd:
            return "blink"
        if "add_files" in cmd or "import_files" in cmd:
            return ""
        if "set_property top" in cmd:
            return ""
        if "launch_runs" in cmd:
            return ""
        if "wait_on_run" in cmd:
            return ""
        if "report_timing_summary" in cmd:
            return "WNS(ns): 1.234\nTNS(ns): 0.000\n"
        if "report_utilization" in cmd:
            return "Slice LUTs: 100/1000\n"
        if "open_hw_target" in cmd or "close_hw_target" in cmd:
            return ""
        if "program_hw_devices" in cmd:
            return ""
        return ""

    server = MockTclServer(handler, port=0, banner_name="smoke/vivado")
    server.start()
    try:
        cfg = Config(
            active_backend="vivado",
            backends=BackendConfig(vivado_host="127.0.0.1", vivado_port=server.port),
        )
        b = VivadoBackend(cfg)
        b.connect()
        h = b.create_project(
            name="blink", directory=Path("/tmp"), part="xc7a35tcpg236-1", top="blink_top"
        )
        assert h.name == "blink", f"vivado project name wrong: {h.name}"
        r = b.report_timing(max_paths=5)
        assert r.wns_ns is not None, "vivado timing report missing WNS"
        b.disconnect()
        b.disconnect()  # idempotent
        print(f"[vivado]    OK  (port {server.port}, WNS={r.wns_ns}ns)")
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Quartus
# ---------------------------------------------------------------------------


def smoke_quartus() -> None:
    def handler(cmd: str) -> str:
        cmd = cmd.strip()
        if "project_new" in cmd:
            return ""
        if "set_global_assignment" in cmd:
            return ""
        if "is_project_open" in cmd:
            return "1"
        if "get_global_assignment" in cmd:
            if "DEVICE" in cmd:
                return "5CGXFC5C6F23C7"
            if "FAMILY" in cmd:
                return "Cyclone V"
            if "TOP_LEVEL_ENTITY" in cmd:
                return "blink_top"
            return ""
        if "execute_module" in cmd:
            return ""
        if "report_timing" in cmd:
            return "Worst-case Slack 2.500\nTotal Negative Slack 0.000\n"
        if "report_resource" in cmd:
            return "LUTs : 50/1000\n"
        return ""

    server = MockTclServer(handler, port=0, banner_name="smoke/quartus")
    server.start()
    try:
        cfg = Config(
            active_backend="quartus",
            backends=BackendConfig(quartus_host="127.0.0.1", quartus_port=server.port),
        )
        b = QuartusBackend(cfg)
        b.connect()
        h = b.create_project(
            name="blink", directory=Path("/tmp"), part="5CGXFC5C6F23C7", top="blink_top"
        )
        assert h.name == "blink", f"quartus project name wrong: {h.name}"
        assert h.part == "5CGXFC5C6F23C7"
        r = b.report_timing(max_paths=5)
        assert r.wns_ns == 2.5, f"quartus WNS wrong: {r.wns_ns}"
        synth = b.run_synthesis()
        assert synth.ok, "quartus synth failed"
        b.disconnect()
        print(f"[quartus]   OK  (port {server.port}, WNS={r.wns_ns}ns)")
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Anlogic
# ---------------------------------------------------------------------------


def smoke_anlogic() -> None:
    def handler(cmd: str) -> str:
        cmd = cmd.strip()
        if "create_project -name" in cmd:
            return ""
        if "catch {current_project}" in cmd:
            return "0"
        if "get_part" in cmd:
            return "EG4S20BG256"
        if "get_top" in cmd:
            return "blink_top"
        if "add_file" in cmd or "set_top" in cmd:
            return ""
        if "run_syn" in cmd or "run_pnr" in cmd:
            return ""
        if "report_timing" in cmd:
            return "WNS: 3.500ns\nTNS: 0.000ns\n"
        if "report_utilization" in cmd:
            return "LUTs : 100/1000 (10.0%)\n"
        return ""

    server = MockTclServer(handler, port=0, banner_name="smoke/anlogic")
    server.start()
    try:
        cfg = Config(
            active_backend="anlogic",
            backends=BackendConfig(anlogic_host="127.0.0.1", anlogic_port=server.port),
        )
        b = AnlogicBackend(cfg)
        b.connect()
        h = b.create_project(
            name="blink", directory=Path("/tmp"), part="EG4S20BG256", top="blink_top"
        )
        assert h.name == "blink", f"anlogic project name wrong: {h.name}"
        assert h.part == "EG4S20BG256"
        r = b.report_timing(max_paths=5)
        assert r.wns_ns == 3.5, f"anlogic WNS wrong: {r.wns_ns}"
        synth = b.run_synthesis()
        assert synth.ok, "anlogic synth failed"
        b.disconnect()
        print(f"[anlogic]   OK  (port {server.port}, WNS={r.wns_ns}ns)")
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def main() -> int:
    failures: list[str] = []

    for name, fn in [
        ("vivado", smoke_vivado),
        ("quartus", smoke_quartus),
        ("anlogic", smoke_anlogic),
    ]:
        try:
            fn()
        except Exception:
            failures.append(name)
            print(f"[{name}]    FAIL")
            traceback.print_exc()

    print()
    if failures:
        print(f"FAILED vendors: {', '.join(failures)}")
        return 1
    print("All three vendors smoke-tested OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
