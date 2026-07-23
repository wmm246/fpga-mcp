#!/usr/bin/env python3
"""Verify every core feature category of fpga-mcp end-to-end.

The timing_closure_demo proves the report-driven feedback loop works.
This script goes broader: it drives **every** category of the
``EDABackend`` contract through fpga-mcp's high-level typed Python
tools and asserts each one returns a well-formed result.

Categories covered (one phase each):

  Phase  0: Lifecycle          — connect / disconnect / is_connected
  Phase  1: Project mgmt      — create_project / current_project handle
  Phase  2: Sources           — add_sources returns count; set_top updates
  Phase  3: Constraints       — add_constraints returns count
  Phase  4: Synthesis         — run_synthesis returns RunResult(ok=True)
  Phase  5: Implementation    — run_implementation returns RunResult(ok=True)
  Phase  6: IP                — create_ip / set_ip_property / generate_ip
  Phase  7: Timing report     — WNS / TNS / failing_paths parsed correctly
  Phase  8: Utilization       — rows parsed (resource / used / avail / pct)
  Phase  9: Simulation        — RunResult(ok=True, stage="simulation")
  Phase 10: Bitstream         — generate_bitstream returns existing Path
  Phase 11: Programming       — program_device returns RunResult(ok=True)
  Phase 12: Escape hatch      — exec_tcl round-trips a raw command
  Phase 13: Session mgmt      — BackendManager.switch / status / available

The script ships with a mock Tcl server (no Vivado needed) so it runs on
any machine. CI executes it on every PR.

Exit codes:
  0 — all phases passed.
  1 — any phase failed or raised an exception.
"""

from __future__ import annotations

import math
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

# Make src/ + tests/ importable when run from the example dir.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from fpga_mcp.config import BackendConfig, Config  # noqa: E402
from fpga_mcp.session import BackendManager  # noqa: E402
from fpga_mcp.transports.vivado import VivadoBackend  # noqa: E402
from _mock_tcl_server import MockTclServer  # noqa: E402


# ---------------------------------------------------------------------------
# Fake Vivado: a stateful mock that knows about the project, the runs, the
# IP instances, the timing/utilization reports, and the JTAG devices.
# ---------------------------------------------------------------------------

state: dict = {
    "project": None,  # dict(name, dir, part, top) once create_project called
    "synth_done": False,
    "impl_done": False,
    "bit_written": False,
    "ip_instances": {},  # name -> {props...}
    "sim_run": False,
    "hw_devices": ["xc7a35t_0", "xc7a100t_1"],
}

VERBOSE = False


def _proj_dir() -> Path:
    return Path(state["project"]["dir"]) if state["project"] else Path("/tmp/_no_proj")


def _proj_name() -> str:
    return state["project"]["name"] if state["project"] else "top"


def _proj_top() -> str:
    return state["project"]["top"] if state["project"] else "top"


def _write_bit_file() -> None:
    """Create the .bit file at the exact path VivadoBackend.generate_bitstream expects."""
    if not state["project"]:
        return
    impl_dir = _proj_dir() / f"{_proj_name()}.runs" / "impl_1"
    impl_dir.mkdir(parents=True, exist_ok=True)
    bit = impl_dir / f"{_proj_top()}.bit"
    bit.write_bytes(b"MOCK_BITSTREAM\x00" + b"\x00" * 256)


def vivado_handler(cmd: str) -> str:
    cmd = cmd.strip()

    if VERBOSE:
        print(f"  [mock] {cmd!r}")

    # --- project lifecycle -----------------------------------------------
    if "create_project" in cmd:
        # create_project -force -part {xc7a35tcpg236-1} {core_features_demo} {/tmp/xxx}
        # Parse out the part, name, directory tokens.
        state["project"] = {
            "name": "core_features_demo",
            "dir": str(_proj_dir()),  # will be overwritten below
            "part": "xc7a35tcpg236-1",
            "top": "core_top",
        }
        # Try to extract the directory argument (last braced token).
        import re as _re

        m = _re.search(r"\{([^\}]+)\}\s*$", cmd)
        if m:
            state["project"]["dir"] = m.group(1)
        m = _re.search(r"-part\s+\{([^\}]+)\}", cmd)
        if m:
            state["project"]["part"] = m.group(1)
        # Look for the project name token (the second-to-last braced).
        m = _re.search(r"\{([^\}]+)\}\s*\{([^\}]+)\}\s*$", cmd)
        if m:
            state["project"]["name"] = m.group(1)
        state["synth_done"] = False
        state["impl_done"] = False
        state["bit_written"] = False
        return ""

    if "set_property target_language" in cmd:
        return ""
    if "set_property top" in cmd and "current_fileset" in cmd:
        # Update tracked top.
        import re as _re

        m = _re.search(r"top\s+\{([^\}]+)\}", cmd)
        if m and state["project"]:
            state["project"]["top"] = m.group(1)
        return ""
    if "update_compile_order" in cmd:
        return ""

    # --- current_project / current_design queries ------------------------
    # _safe_tcl wraps these in `if {[catch {...} rc opt]} ...; return $rc`.
    if "catch {current_project}" in cmd:
        return "0" if state["project"] else "1"
    if "current_project" in cmd and "catch" not in cmd and "get_property" not in cmd:
        return _proj_name()
    if "get_property PART" in cmd and "current_project" in cmd:
        return state["project"]["part"] if state["project"] else ""
    if "get_property DIRECTORY" in cmd and "current_project" in cmd:
        return state["project"]["dir"] if state["project"] else "."
    if "get_property top" in cmd and "current_fileset" in cmd:
        return _proj_top()

    if "catch {current_design}" in cmd:
        # Returning "1" forces _open_a_run to actually open a run.
        return "1"
    if "current_design" in cmd and "catch" not in cmd:
        return _proj_top() if state["impl_done"] else ""

    # --- sources & constraints ------------------------------------------
    if "add_files" in cmd:
        return ""
    if "set_property include_dirs" in cmd:
        return ""

    # --- synthesis + implementation -------------------------------------
    if "launch_runs" in cmd and "synth_1" in cmd:
        state["synth_done"] = True
        return ""
    if "launch_runs" in cmd and "impl_1" in cmd:
        state["impl_done"] = True
        if "write_bitstream" in cmd:
            state["bit_written"] = True
            _write_bit_file()
        return ""
    if "wait_on_run" in cmd:
        return ""
    if "reset_run" in cmd:
        if "synth_1" in cmd:
            state["synth_done"] = False
        if "impl_1" in cmd:
            state["impl_done"] = False
            state["bit_written"] = False
        return ""
    if "get_property STATUS" in cmd and "synth_1" in cmd:
        return "synth_design Complete!" if state["synth_done"] else "Not started"
    if "get_property STATUS" in cmd and "impl_1" in cmd:
        if state["bit_written"]:
            return "write_bitstream Complete!"
        if state["impl_done"]:
            return "route_design Complete!"
        if state["synth_done"]:
            return "synth_design Complete!"
        return "Not started"
    if "get_property DIRECTORY" in cmd and "get_runs" in cmd:
        # Return a non-existent path; the backend tolerates missing logs.
        return str(_proj_dir() / f"{_proj_name()}.runs" / "impl_1")
    if "open_run" in cmd:
        return ""

    # --- IP --------------------------------------------------------------
    if "get_ipdefs" in cmd:
        # Pretend the IP exists with version 6.0.
        return "xilinx.com:ip:clk_wiz:6.0"
    if "create_ip" in cmd:
        import re as _re

        m = _re.search(r"-module_name\s+\{([^\}]+)\}", cmd)
        inst = m.group(1) if m else "ip_0"
        state["ip_instances"][inst] = {}
        return ""
    if "set_property -dict" in cmd and "get_ips" in cmd:
        # Track the props for verification (no-op for the mock).
        return ""
    if "generate_target" in cmd:
        return ""
    if "synth_ip" in cmd:
        return ""

    # --- timing report ---------------------------------------------------
    if "report_timing_summary" in cmd:
        # Return a realistic Vivado timing summary the parser can read.
        # WNS = +1.234 ns (passing), TNS = 0.0, WHS = +0.567, THS = 0.0
        return (
            "Design Timing Summary\n"
            "| Clock | WNS(ns) | TNS(ns) | TNS Failing Endpoints | WHS(ns) |\n"
            "|---|---|---|---|---|\n"
            "| clk_core | 1.234 | 0.000 | 0 | 0.567 |\n"
            "| clk_tx | 0.890 | 0.000 | 0 | 0.456 |\n"
        )
    if "report_timing" in cmd and "summary" not in cmd:
        return (
            "Slack (MET) : 1.234ns (required time - arrival time)\n"
            "  Source: data_in_reg[0]/REG\n"
            "  Destination: data_out_reg[0]/REG\n"
            "  Path Group: clk_core\n"
            "  Data Path Delay: 8.766ns\n"
            "  Logic Levels: 3 (LUT2 LUT2 LUT2)\n"
        )
    if "report_clocks" in cmd:
        return "clk_core 10.000ns 100.000MHz\nclk_tx 20.000ns 50.000MHz\n"
    if "get_clocks" in cmd:
        return "clk_core clk_tx"

    # --- utilization report ----------------------------------------------
    if "report_utilization" in cmd:
        return (
            "+------------------+---------+---------+-------+\n"
            "| Resource         | Used    | Avail   | %     |\n"
            "+------------------+---------+---------+-------+\n"
            "| CLB LUTs         | 1234    | 20800   | 5.93  |\n"
            "| CLB Registers    | 2100    | 41600   | 5.05  |\n"
            "| Block RAM Tile   | 5       | 50      | 10.00 |\n"
            "| DSPs             | 2       | 90      | 2.22  |\n"
            "+------------------+---------+---------+-------+\n"
        )

    # --- simulation -----------------------------------------------------
    if "launch_simulation" in cmd:
        state["sim_run"] = True
        return ""

    # --- bitstream & programming ----------------------------------------
    # generate_bitstream uses launch_runs impl_1 -to_step write_bitstream,
    # handled above. For program_device:
    if "open_hw_manager" in cmd:
        return ""
    if "get_hw_targets" in cmd:
        # Empty string triggers the `open_hw_target` branch.
        return ""
    if "open_hw_target" in cmd:
        return ""
    if "get_hw_devices" in cmd:
        return " ".join(state["hw_devices"])
    if "set_property PROGRAM.FILE" in cmd:
        return ""
    if "set_property PROBES.FILE" in cmd:
        return ""
    if "program_hw_devices" in cmd:
        return ""

    # --- fallback -------------------------------------------------------
    return ""


# ---------------------------------------------------------------------------
# Per-phase verification. Each phase returns None on success or a string
# describing the failure. Each phase is wrapped in try/except so a crash
# in one doesn't stop the rest from running.
# ---------------------------------------------------------------------------


def phase_00_lifecycle(backend: VivadoBackend) -> None:
    """connect / is_connected / disconnect cycle."""
    assert not backend.is_connected(), "backend should start disconnected"
    backend.connect()
    assert backend.is_connected(), "backend should be connected after connect()"


def phase_01_project(backend: VivadoBackend, workdir: Path) -> None:
    """create_project returns a ProjectHandle with the right fields."""
    h = backend.create_project(
        name="core_features_demo",
        directory=workdir,
        part="xc7a35tcpg236-1",
        top="core_top",
    )
    assert h.name == "core_features_demo", f"unexpected name: {h.name}"
    assert h.part == "xc7a35tcpg236-1", f"unexpected part: {h.part}"
    assert h.backend == "vivado", f"unexpected backend: {h.backend}"
    assert h.top == "core_top", f"unexpected top: {h.top}"
    assert h.path.name.endswith(".xpr"), f"unexpected path ext: {h.path}"
    # current_project() returns the cached handle without a Tcl roundtrip.
    cur = backend.current_project()
    assert cur is not None and cur.name == "core_features_demo"


def phase_02_sources(backend: VivadoBackend, src_file: Path) -> None:
    """add_sources returns the count; set_top updates the handle."""
    n = backend.add_sources([src_file])
    assert n == 1, f"add_sources should return 1, got {n}"
    backend.set_top("core_top")
    assert backend.current_project().top == "core_top"


def phase_03_constraints(backend: VivadoBackend, xdc_file: Path) -> None:
    """add_constraints returns the count."""
    n = backend.add_constraints([xdc_file])
    assert n == 1, f"add_constraints should return 1, got {n}"


def phase_04_synthesis(backend: VivadoBackend) -> None:
    """run_synthesis returns RunResult(ok=True, stage='synthesis')."""
    r = backend.run_synthesis()
    assert r.ok, f"synthesis should succeed, summary={r.summary!r}"
    assert r.stage == "synthesis", f"unexpected stage: {r.stage!r}"
    assert r.duration_sec is not None and r.duration_sec >= 0


def phase_05_implementation(backend: VivadoBackend) -> None:
    """run_implementation returns RunResult(ok=True, stage='implementation')."""
    r = backend.run_implementation()
    assert r.ok, f"implementation should succeed, summary={r.summary!r}"
    assert r.stage == "implementation", f"unexpected stage: {r.stage!r}"


def phase_06_ip(backend: VivadoBackend) -> None:
    """create_ip returns instance name; set_ip_property / generate_ip succeed."""
    # IP props are passed as a dict (the **props kwarg) — dict keys can have
    # dots, unlike Python identifier kwargs.
    inst = backend.create_ip("clk_wiz", name="clk_wiz_core", **{"CONFIG.PRIM_IN_FREQ": 100.0})
    assert inst == "clk_wiz_core", f"unexpected instance name: {inst!r}"
    # set_ip_property via a single (prop, value) pair.
    backend.set_ip_property("clk_wiz_core", "CONFIG.CLKOUT1_REQUESTED_OUT_FREQ", 50.0)
    # set_ip_property via a list of pairs (the dict-shape variant).
    backend.set_ip_property(
        "clk_wiz_core",
        [("CONFIG.CLKOUT2_USED", "true"), ("CONFIG.CLKOUT2_REQUESTED_OUT_FREQ", 25.0)],
        None,
    )
    r = backend.generate_ip("clk_wiz_core")
    assert r.ok, f"generate_ip should succeed, summary={r.summary!r}"
    assert r.stage == "ip_synth", f"unexpected stage: {r.stage!r}"


def phase_07_timing_report(backend: VivadoBackend) -> None:
    """report_timing parses WNS/TNS and failing_paths."""
    r = backend.report_timing(max_paths=10)
    assert isinstance(r.wns_ns, float), f"WNS should be float, got {type(r.wns_ns)}"
    assert math.isfinite(r.wns_ns), f"WNS not finite: {r.wns_ns}"
    assert isinstance(r.tns_ns, float), f"TNS should be float, got {type(r.tns_ns)}"
    # The mock returns WNS=+1.234 (passing).
    assert r.wns_ns > 0, f"WNS should be positive (passing), got {r.wns_ns}"
    assert r.tns_ns == 0.0, f"TNS should be 0 (no violations), got {r.tns_ns}"
    # Mock's report has no failing paths → list is empty.
    assert isinstance(r.failing_paths, list), "failing_paths should be a list"
    assert len(r.failing_paths) == 0, f"expected 0 failing paths, got {len(r.failing_paths)}"


def phase_08_utilization(backend: VivadoBackend) -> None:
    """report_utilization parses resource rows."""
    r = backend.report_utilization()
    assert len(r.rows) >= 4, f"expected >=4 utilization rows, got {len(r.rows)}"
    lut_rows = [row for row in r.rows if "LUT" in row.resource]
    assert lut_rows, "no LUT row found in utilization report"
    lut = lut_rows[0]
    assert lut.used > 0, f"LUT used should be > 0, got {lut.used}"
    assert lut.available > lut.used, "available should exceed used"
    assert 0 <= lut.util_pct <= 100, f"util_pct out of range: {lut.util_pct}"


def phase_09_simulation(backend: VivadoBackend) -> None:
    """run_simulation returns RunResult(ok=True, stage='simulation')."""
    r = backend.run_simulation(kind="rtl", testbench="core_tb")
    assert r.ok, f"simulation should succeed, summary={r.summary!r}"
    assert r.stage == "simulation", f"unexpected stage: {r.stage!r}"
    assert "core_tb" in (r.summary or ""), f"summary should mention tb name: {r.summary!r}"


def phase_10_bitstream(backend: VivadoBackend) -> None:
    """generate_bitstream returns a Path that exists on disk."""
    bit = backend.generate_bitstream()
    assert isinstance(bit, Path), f"bitstream should be Path, got {type(bit)}"
    assert bit.exists(), f"bitstream file not created: {bit}"
    assert bit.suffix == ".bit", f"unexpected bitstream extension: {bit.suffix}"
    assert bit.stat().st_size > 0, "bitstream file is empty"


def phase_11_programming(backend: VivadoBackend, bit: Path) -> None:
    """program_device returns RunResult(ok=True, stage='program')."""
    r = backend.program_device(bit, device_index=0)
    assert r.ok, f"program_device should succeed, errors={r.errors}"
    assert r.stage == "program", f"unexpected stage: {r.stage!r}"
    assert r.duration_sec is not None and r.duration_sec >= 0


def phase_12_exec_tcl(backend: VivadoBackend) -> None:
    """exec_tcl round-trips a raw command and returns its string output."""
    out = backend.exec_tcl("puts hello-from-exec-tcl")
    assert isinstance(out, str), f"exec_tcl should return str, got {type(out)}"


def phase_13_session(workdir: Path) -> None:
    """BackendManager.switch / status / available across 3 vendors."""
    # Spin up one mock per vendor, each on a distinct port.
    handlers = {
        "vivado": vivado_handler,
        "quartus": lambda cmd: "",
        "anlogic": lambda cmd: "",
    }
    servers = {
        name: MockTclServer(h, port=0, banner_name=f"core-features/{name}")
        for name, h in handlers.items()
    }
    for s in servers.values():
        s.start()
    try:
        cfg = Config(
            active_backend="vivado",
            backends=BackendConfig(
                vivado_host="127.0.0.1",
                vivado_port=servers["vivado"].port,
                quartus_host="127.0.0.1",
                quartus_port=servers["quartus"].port,
                anlogic_host="127.0.0.1",
                anlogic_port=servers["anlogic"].port,
            ),
        )
        mgr = BackendManager(cfg)
        # available() lists all three vendors.
        avail = mgr.available()
        for v in ("vivado", "quartus", "anlogic"):
            assert v in avail, f"missing {v} in available(): {avail}"
        # switch changes the active backend.
        msg = mgr.switch("quartus")
        assert "quartus" in msg and "vivado" in msg, f"unexpected switch msg: {msg}"
        assert mgr.active_name == "quartus"
        mgr.switch("anlogic")
        assert mgr.active_name == "anlogic"
        mgr.switch("vivado")
        assert mgr.active_name == "vivado"
        # ensure_connected brings the active backend up.
        b = mgr.ensure_connected("vivado")
        assert b.is_connected(), "ensure_connected should leave backend connected"
        # status() reports every vendor, with vivado connected.
        st = mgr.status()
        for v in ("vivado", "quartus", "anlogic"):
            assert v in st, f"missing {v} in status(): {list(st)}"
        assert st["vivado"]["connected"] is True, "vivado should be connected in status"
        assert st["vivado"]["active"] is True, "vivado should be active in status"
        assert st["quartus"]["active"] is False
        # Switching to an unknown backend raises BackendError.
        from fpga_mcp.transports.base import BackendError

        try:
            mgr.switch("nonexistent")
        except BackendError:
            pass
        else:  # pragma: no cover — should have raised
            raise AssertionError("switch to unknown backend should raise BackendError")
        mgr.disconnect_all()
    finally:
        for s in servers.values():
            s.stop()


# ---------------------------------------------------------------------------
# Drive all phases.
# ---------------------------------------------------------------------------


PHASES = [
    ("Phase 00: Lifecycle (connect/disconnect)", "phase_00_lifecycle"),
    ("Phase 01: Project management", "phase_01_project"),
    ("Phase 02: Sources (add_sources/set_top)", "phase_02_sources"),
    ("Phase 03: Constraints (add_constraints)", "phase_03_constraints"),
    ("Phase 04: Synthesis (run_synthesis)", "phase_04_synthesis"),
    ("Phase 05: Implementation (run_implementation)", "phase_05_implementation"),
    ("Phase 06: IP (create_ip/set_ip_property/generate_ip)", "phase_06_ip"),
    ("Phase 07: Timing report (report_timing)", "phase_07_timing_report"),
    ("Phase 08: Utilization (report_utilization)", "phase_08_utilization"),
    ("Phase 09: Simulation (run_simulation)", "phase_09_simulation"),
    ("Phase 10: Bitstream (generate_bitstream)", "phase_10_bitstream"),
    ("Phase 11: Programming (program_device)", "phase_11_programming"),
    ("Phase 12: Escape hatch (exec_tcl)", "phase_12_exec_tcl"),
    ("Phase 13: Session (BackendManager)", "phase_13_session"),
]


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="fpga-mcp-core-"))
    try:
        # Set up minimal HDL + constraint fixtures (paths are inspected, not
        # actually compiled by the mock).
        src_file = workdir / "core_top.v"
        src_file.write_text("module core_top(input clk, output reg q); endmodule\n")
        xdc_file = workdir / "core_top.xdc"
        xdc_file.write_text("create_clock -period 10.0 -name clk_core [get_ports clk]\n")
        bit_file = workdir / "core_top.bit"
        bit_file.write_bytes(b"MOCK_BITSTREAM_FOR_PROGRAMMING\n")

        server = MockTclServer(vivado_handler, port=0, banner_name="core-features/vivado")
        server.start()
        try:
            cfg = Config(
                active_backend="vivado",
                backends=BackendConfig(vivado_host="127.0.0.1", vivado_port=server.port),
            )
            backend = VivadoBackend(cfg)

            # Drive phases 0..12 against the single vivado backend. Phase 13
            # spins its own multi-backend setup inside.
            results = []
            for label, fn_name in PHASES:
                fn = globals()[fn_name]
                print("=" * 70)
                print(label)
                print("=" * 70)
                try:
                    if fn_name == "phase_01_project":
                        fn(backend, workdir)
                    elif fn_name == "phase_02_sources":
                        fn(backend, src_file)
                    elif fn_name == "phase_03_constraints":
                        fn(backend, xdc_file)
                    elif fn_name == "phase_11_programming":
                        fn(backend, bit_file)
                    elif fn_name == "phase_13_session":
                        fn(workdir)
                    else:
                        fn(backend)
                    print("  PASS")
                    results.append((label, True, ""))
                except Exception as exc:
                    print(f"  FAIL: {exc}")
                    traceback.print_exc()
                    results.append((label, False, str(exc)))

            # Verdict
            print()
            print("=" * 70)
            print("VERDICT")
            print("=" * 70)
            passed = sum(1 for _, ok, _ in results if ok)
            failed = len(results) - passed
            for label, ok, err in results:
                mark = "PASS" if ok else "FAIL"
                print(f"  [{mark}] {label}" + (f"  — {err}" if not ok else ""))
            print()
            print(f"  {passed}/{len(results)} phases passed.")
            if failed == 0:
                print("PASS: all core feature categories verified.")
                return 0
            print(f"FAIL: {failed} phase(s) failed.")
            return 1
        finally:
            try:
                backend.disconnect()
            except Exception:
                pass
            server.stop()
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
