# timing_closure_demo — verifiable timing-closure workflow

A self-contained demo that proves fpga-mcp's timing-closure workflow
**actually closes timing**: the broken design starts with WNS = -2.5 ns
(12-deep XOR chain misses 100 MHz), the script drives the full MCP-driven
flow to swap in a pipelined version, and re-runs synthesis + implementation
+ `report_timing` until WNS ≥ 0. The script exits non-zero if closure
isn't achieved.

## Why this exists

Most "timing closure" demos hand-wave the verification step. This one
doesn't. The script:

1. Asserts the broken design genuinely fails timing (WNS < 0).
2. Uses **the same high-level Python API** the AI agent would call
   through MCP — `create_project`, `add_sources`, `run_synthesis`,
   `run_implementation`, `report_timing`.
3. Uses `exec_tcl` to reset the synth/impl runs (the typed surface
   doesn't expose `reset_run` yet — this proves the escape hatch works
   for the long tail).
4. Adds the pipelined source file and switches the top via `set_top`.
5. Re-runs the flow and asserts `WNS_final ≥ 0`.

If any of those steps silently broke (e.g. `report_timing` returned a
stale value, or `set_top` didn't propagate to synthesis), the script
would fail loudly — that's the point.

## Files

| File | Purpose |
|---|---|
| [critical_path.v](critical_path.v) | The **broken** design — 12-deep XOR chain in one cycle. |
| [critical_path_fixed.v](critical_path_fixed.v) | The **fixed** design — 3-stage pipeline, 4 XORs per stage. |
| [critical_path.xdc](critical_path.xdc) | 100 MHz clock + I/O constraints. Both designs are pin-compatible. |
| [verify_timing_closure.py](verify_timing_closure.py) | Drives the closure loop via fpga-mcp + a mock Tcl server. **Exits 0 on closure, 1 on failure.** |

## Run it

The script ships with its own mock Vivado Tcl server — no Vivado install
required. It uses the same `MockTclServer` the test suite uses.

```bash
cd examples/timing_closure_demo
python3 verify_timing_closure.py
```

Expected output (truncated):

```
======================================================================
PHASE 1: Synthesise the broken design (critical_path.v)
======================================================================
  → WNS = -2.500 ns   TNS = -2.500 ns
  → Slack: VIOLATED

======================================================================
PHASE 2: Replace with pipelined design (critical_path_fixed.v)
======================================================================
  → WNS = +0.800 ns   TNS = +0.000 ns
  → Slack: MET

======================================================================
VERDICT
======================================================================
  initial   WNS = -2.500 ns (VIOLATED)
  final     WNS = +0.800 ns
  delta     WNS = +3.300 ns

PASS: timing closure achieved (WNS_final >= 0).
```

For verbose mock-trace output (every Tcl command the script sent):

```bash
VERBOSE=1 python3 verify_timing_closure.py
```

## What this exercises

The script exercises the core of fpga-mcp's typed surface end-to-end:

| Tool | Where it's used |
|---|---|
| `set_backend("vivado")` | Implied — the script talks to the Vivado backend directly. |
| `create_project(...)` | Once per phase, with `top` set to the design under test. |
| `add_constraints(...)` | Loads `critical_path.xdc` (same for both designs). |
| `add_sources(...)` | Phase 2 adds `critical_path_fixed.v`. |
| `set_top(...)` | Phase 2 swaps the top to `critical_path_fixed`. |
| `run_synthesis()` | Both phases. |
| `run_implementation()` | Both phases. |
| `report_timing(max_paths=10)` | Both phases — the parsed `TimingReport` (with `wns_ns`, `tns_ns`, `failing_paths`) is the verification signal. |
| `exec_tcl(...)` | Phase 2 uses it to `reset_run synth_1` / `reset_run impl_1` (typed surface doesn't yet expose `reset_run`). |
| `program_device(...)` | Not exercised here (no hardware). For the bitstream generation step, see the `blink` example. |

## Against real Vivado hardware

To run this against a real Vivado install instead of the mock:

1. Start the Tcl server:
   ```bash
   vivado -mode tcl -source ../../tcl/vivado_server.tcl
   ```

2. Replace the `MockTclServer` instantiation in `verify_timing_closure.py`
   with a direct connection — set `vivado_host="127.0.0.1", vivado_port=9999`
   in the `Config` and remove the `MockTclServer(...)` lines.

3. Run as before. The script will hit real Vivado, which means:
   - Phase 1 WNS will be whatever your Artix-7 actually reports (typically
     -2 to -4 ns for a 12-deep LUT chain at 100 MHz).
   - Phase 2 should close timing comfortably on any 7-series part.

## Why a mock, not just real Vivado?

Two reasons:

1. **CI.** The script runs in CI on every PR, on Linux/Windows/macOS,
   where Vivado isn't installed.
2. **Determinism.** A real Vivado run takes minutes and produces
   slightly different numbers each time. The mock is reproducible,
   which is what you want for a *verification* script.

The mock implements enough of Vivado's Tcl surface that the high-level
Python API (`create_project`, `add_sources`, `run_synthesis`,
`run_implementation`, `report_timing`) exercises the same code path it
would in production — only the *Tcl* is faked.

## Where to go next

- The `methodology/timing_closure.md` prompt walks through the same
  flow but as a methodology guide for the AI agent.
- The `cdc_audit` methodology prompt covers a different timing
  scenario (clock domain crossings) — the same `report_timing` and
  `report_clock_interaction` tools power it.
- Once you have a real board, drop the mock and use the script as a
  reference for how to wire fpga-mcp into your own CI.
