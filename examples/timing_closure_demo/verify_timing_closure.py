#!/usr/bin/env python3
"""Verify the timing-closure workflow of fpga-mcp end-to-end.

This script demonstrates the full timing-closure loop that an AI agent
would drive through fpga-mcp, and asserts that the workflow actually
closes timing (WNS >= 0).

It uses fpga-mcp's own mock Tcl server to fake a Vivado backend whose
behaviour matches the demo design:

  Phase 1 (broken): synth + impl of `critical_path.v` returns WNS = -2.5 ns
                    (the 12-deep XOR chain misses 100 MHz).
  Phase 2 (fixed):  after `set_property` + re-synth of `critical_path_fixed.v`
                    returns WNS = +0.8 ns (3-stage pipeline closes timing).

What this proves:
  - The `report_timing` tool parses Vivado's timing report correctly and
    surfaces a structured `TimingReport` the caller can branch on.
  - The `set_top` / `add_sources` / `run_synthesis` / `run_implementation`
    high-level Python tools work through the same code path an AI agent
    would use.
  - `exec_tcl` reaches the underlying Vivado flow when the typed surface
    doesn't expose what we need (here, swapping the source file).
  - The whole loop terminates with a binary PASS/FAIL verdict the user
    can hang verification on (`assert wns_final >= 0`).

Exit codes:
  0 — timing closure achieved (WNS_final >= 0).
  1 — closure failed, or any tool call raised an exception.

Usage:
    python3 verify_timing_closure.py
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Make src/ + tests/ importable when run from the example dir.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from fpga_mcp.config import BackendConfig, Config  # noqa: E402
from fpga_mcp.transports.vivado import VivadoBackend  # noqa: E402
from _mock_tcl_server import MockTclServer  # noqa: E402


# ---------------------------------------------------------------------------
# Fake Vivado: tracks which source file is "in the project" so the same
# backend can return a failing timing report in phase 1 and a passing one
# in phase 2.
# ---------------------------------------------------------------------------

state: dict = {
    "current_top": "critical_path",  # default = broken design
    "sources": ["critical_path.v"],
    "synth_done": False,
    "impl_done": False,
}

# Flip to True for verbose mock-trace output.
VERBOSE = False


def _set_top(new_top: str, why: str) -> None:
    if new_top != state["current_top"]:
        if VERBOSE:
            print(f"  [mock] current_top: {state['current_top']!r} → {new_top!r}  ({why})")
        state["current_top"] = new_top


def vivado_handler(cmd: str) -> str:
    cmd = cmd.strip()

    # --- project + source management -------------------------------------
    if "create_project" in cmd:
        state["synth_done"] = False
        state["impl_done"] = False
        if VERBOSE:
            print(f"  [mock] create_project → current_top={state['current_top']}")
        return ""

    if VERBOSE:
        print(f"  [mock] {cmd!r}")
    if "add_files" in cmd or "import_files" in cmd or "read_verilog" in cmd:
        # Track which source file got added so we know which design to time.
        # ONLY switch on HDL sources (.v / .sv / .vhd), not constraints
        # (.xdc / .sdc) — the constraint file shares the design's basename.
        if "critical_path_fixed" in cmd and (".v " in cmd or '.v"' in cmd or cmd.endswith(".v")):
            _set_top("critical_path_fixed", "add_files fixed HDL")
            state["sources"].append("critical_path_fixed.v")
        elif "critical_path.v" in cmd:
            _set_top("critical_path", "add_files broken HDL")
            state["sources"].append("critical_path.v")
        return ""
    if "set_property top" in cmd:
        # set_property top critical_path_fixed [current_fileset]
        if "critical_path_fixed" in cmd:
            _set_top("critical_path_fixed", "set_property top")
        elif "critical_path" in cmd:
            _set_top("critical_path", "set_property top")
        return ""
    if "current_project" in cmd and "catch" not in cmd:
        return "timing_closure_demo"
    if "get_part" in cmd and "set_property" not in cmd:
        return "xc7a35tcpg236-1"
    if "get_top" in cmd:
        return state["current_top"]

    # --- synthesis + implementation runs --------------------------------
    if "launch_runs" in cmd and "synth" in cmd:
        state["synth_done"] = True
        return ""
    if "launch_runs" in cmd and "impl" in cmd:
        state["impl_done"] = True
        return ""
    if "wait_on_run" in cmd:
        return ""
    if "reset_run" in cmd:
        if "synth" in cmd:
            state["synth_done"] = False
        if "impl" in cmd:
            state["impl_done"] = False
        return ""

    # --- timing reports -------------------------------------------------
    if "report_timing_summary" in cmd:
        if VERBOSE:
            print(
                f"  [mock] report_timing_summary: current_top={state['current_top']} "
                f"synth_done={state['synth_done']} impl_done={state['impl_done']}"
            )
        if not state["impl_done"]:
            return "Timing not available: implementation not run"
        if state["current_top"] == "critical_path":
            # Broken design: WNS = -2.5 ns.
            return (
                "Design Timing Summary\n"
                "| Clock | WNS(ns) | TNS(ns) | TNS Failing Endpoints | WHS(ns) |\n"
                "|---|---|---|---|---|\n"
                "| clk_in | -2.500 | -2.500 | 1 | 0.000 |\n"
            )
        # Fixed design: WNS = +0.8 ns.
        return (
            "Design Timing Summary\n"
            "| Clock | WNS(ns) | TNS(ns) | TNS Failing Endpoints | WHS(ns) |\n"
            "|---|---|---|---|---|\n"
            "| clk_in | 0.800 | 0.000 | 0 | 0.000 |\n"
        )
    if "report_timing" in cmd and "report_timing_summary" not in cmd:
        # Detailed report_timing (-return_string). Mirror the summary.
        if not state["impl_done"]:
            return "Timing not available: implementation not run"
        if state["current_top"] == "critical_path":
            return (
                "Slack (VIOLATED) : -2.500ns (required time - arrival time)\n"
                "  Source: data_in[0]/(DFF_IN)\n"
                "  Destination: data_out_reg[0]/REG\n"
                "  Path Group: clk_in\n"
                "  Data Path Delay: 12.500ns\n"
                "  Logic Levels: 12 (LUT2 LUT2 LUT2 LUT2 LUT2 LUT2 "
                "LUT2 LUT2 LUT2 LUT2 LUT2 LUT2)\n"
            )
        return (
            "Slack (MET) : 0.800ns (required time - arrival time)\n"
            "  Source: stage1_reg[0]/REG\n"
            "  Destination: data_out_reg[0]/REG\n"
            "  Path Group: clk_in\n"
            "  Data Path Delay: 2.200ns\n"
            "  Logic Levels: 4 (LUT2 LUT2 LUT2 LUT2)\n"
        )
    if "report_clocks" in cmd:
        return "clk_in 10.000ns 100.000MHz\n"
    if "get_clocks" in cmd:
        return "clk_in"

    # --- design-open helpers used by report_timing ----------------------
    # `_open_a_run` calls these to figure out which run to open.
    if "catch {current_design}" in cmd:
        # Returning "0" means `current_design` succeeded and a design IS open.
        # We want to force the backend to open the right run, so return "1"
        # (i.e. no design currently open) — that triggers the open_run branch.
        return "1"
    if "current_design" in cmd:
        # After open_run, current_design should return something. Return
        # the current top so the backend sees an open design.
        return state["current_top"]
    if "get_property STATUS" in cmd and "get_runs" in cmd:
        if state["impl_done"]:
            return "write_bitstream Complete!"  # → backend will open impl_1
        if state["synth_done"]:
            return "synth_design Complete!"  # → backend falls back to synth_1
        return "Not started"
    if "open_run" in cmd:
        # Opening the run puts the design in memory — no output expected.
        return ""

    # --- fallback -------------------------------------------------------
    return ""


# ---------------------------------------------------------------------------
# Drive the timing-closure workflow.
# ---------------------------------------------------------------------------


def run_closure_loop(backend: VivadoBackend) -> tuple[float, float]:
    """Drive one synth → impl → report loop, return (wns, tns).

    Uses fpga-mcp's high-level typed Python tools, the same path the MCP
    `run_synthesis` / `run_implementation` / `report_timing` tools expose
    to AI agents.
    """
    backend.create_project(
        name="timing_closure_demo",
        directory=Path("/tmp/tc_demo"),
        part="xc7a35tcpg236-1",
        top=state["current_top"],
    )
    # Add the constraints (XDC).
    backend.add_constraints([Path(__file__).parent / "critical_path.xdc"])
    backend.run_synthesis()
    backend.run_implementation()
    r = backend.report_timing(max_paths=10)
    if r.wns_ns is None:
        raise RuntimeError("report_timing did not return a WNS value")
    return r.wns_ns, r.tns_ns


def main() -> int:
    server = MockTclServer(vivado_handler, port=0, banner_name="tc-demo/vivado")
    server.start()
    try:
        cfg = Config(
            active_backend="vivado",
            backends=BackendConfig(vivado_host="127.0.0.1", vivado_port=server.port),
        )
        backend = VivadoBackend(cfg)
        backend.connect()

        # ----- Phase 1: synth the broken design ----------------------------
        print("=" * 70)
        print("PHASE 1: Synthesise the broken design (critical_path.v)")
        print("=" * 70)
        wns_broken, tns_broken = run_closure_loop(backend)
        print(f"  → WNS = {wns_broken:+.3f} ns   TNS = {tns_broken:+.3f} ns")
        print(f"  → Slack: {'VIOLATED' if wns_broken < 0 else 'MET'}")
        assert wns_broken < 0, f"Phase 1 should fail timing, got WNS={wns_broken}"

        # ----- Phase 2: swap in the fixed design, re-run -------------------
        print()
        print("=" * 70)
        print("PHASE 2: Replace with pipelined design (critical_path_fixed.v)")
        print("=" * 70)
        # Reset the synth + impl runs (so launch_runs re-runs cleanly).
        backend.exec_tcl("reset_run synth_1")
        backend.exec_tcl("reset_run impl_1")
        # Drop the broken source, add the fixed one, switch top.
        backend.add_sources([Path(__file__).parent / "critical_path_fixed.v"])
        backend.set_top("critical_path_fixed")
        wns_fixed, tns_fixed = run_closure_loop(backend)
        print(f"  → WNS = {wns_fixed:+.3f} ns   TNS = {tns_fixed:+.3f} ns")
        print(f"  → Slack: {'VIOLATED' if wns_fixed < 0 else 'MET'}")

        # ----- Verdict ----------------------------------------------------
        print()
        print("=" * 70)
        print("VERDICT")
        print("=" * 70)
        print(f"  initial   WNS = {wns_broken:+.3f} ns (VIOLATED)")
        print(f"  final     WNS = {wns_fixed:+.3f} ns")
        print(f"  delta     WNS = {wns_fixed - wns_broken:+.3f} ns")

        if wns_fixed >= 0:
            print()
            print("PASS: timing closure achieved (WNS_final >= 0).")
            print("The fpga-mcp timing-closure workflow correctly identified the")
            print("failing path, let us swap in the fixed RTL, and re-verified.")
            return 0
        print()
        print("FAIL: timing closure NOT achieved.")
        return 1
    except Exception:
        print()
        print("ERROR: workflow raised an exception.")
        traceback.print_exc()
        return 1
    finally:
        server.stop()


if __name__ == "__main__":
    sys.exit(main())
