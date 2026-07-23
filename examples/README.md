# Examples

Three runnable demos that show how to drive `fpga-mcp` end-to-end. Pick
the one that matches what you're trying to do:

| Example | What it shows | Needs Vivado? |
|---|---|---|
| [blink/](blink/) | Minimal LED blinker. The "5-minute from-zero-to-bitstream" hello world. | Yes (or your own board) |
| [timing_closure_demo/](timing_closure_demo/) | Verifiable timing-closure workflow: broken design → identify failing path → fix → re-verify WNS ≥ 0. **Exits 0 on success, 1 on failure.** | No — ships with a mock Tcl server |
| [core_features_demo/](core_features_demo/) | Verifies **all 14 core feature categories** of the `EDABackend` contract (lifecycle, project, sources, synth, impl, IP, timing, utilization, simulation, bitstream, programming, exec_tcl, session). **Exits 0 on success, 1 on failure.** | No — ships with a mock Tcl server |

## Quick start

### blink — against a real board

```bash
cd blink
vivado -mode tcl -source ../../tcl/vivado_server.tcl   # terminal 1
fpga-mcp run                                            # terminal 2
# Then ask your AI assistant (Claude / Cursor / Codex):
#   "Use fpga-mcp to build the blink example for xc7a35tcpg236-1."
```

### timing_closure_demo — fully self-contained, no Vivado

```bash
cd timing_closure_demo
python3 verify_timing_closure.py
# Exits 0 when timing closure is achieved.
```

This is the example CI runs on every PR. It uses fpga-mcp's mock Tcl
server so it works on any machine — Linux, Windows or macOS — without
any EDA tool installed.

### core_features_demo — fully self-contained, no Vivado

```bash
cd core_features_demo
python3 verify_core_features.py
# Exits 0 when all 14 phases pass.
```

CI runs this on every PR alongside `timing_closure_demo`. Where the
timing-closure demo exercises the **report-driven feedback loop**,
this one exercises **every typed verb** on the `EDABackend`
Protocol, so a regression in `report_utilization`, `generate_ip`,
`program_device`, the multi-backend session layer, etc. is caught
before it ships.

## Why these examples exist

The README's architecture and tool index show **what** fpga-mcp is.
These examples show **how to actually use it** — and prove the
typed tool surface really works, not just on paper.

- `blink` walks through the 5 high-level verbs (`create_project` →
  `add_sources` → `run_synthesis` → `run_implementation` →
  `generate_bitstream`) and the `program_device` step.
- `timing_closure_demo` exercises the report-driven feedback loop:
  synthesize → report → diagnose → fix → re-synthesize → re-report →
  assert closure. The verification assertion at the end is what makes
  this example more than a tutorial.
- `core_features_demo` is the **typed-surface canary**. It drives all
  14 categories of the `EDABackend` contract through the high-level
  Python tools and asserts each one returns a well-formed result.
  It already caught one real bug: `VivadoBackend.create_ip(**props)`
  used to call `set_ip_property(inst, list(props.items()))` with 2
  args instead of 3.

## Adding your own example

If you build something with fpga-mcp that demonstrates a feature not
covered here (e.g. CDC audit, IP integration, board bring-up), please
contribute it. See [../CONTRIBUTING.md](../CONTRIBUTING.md) for the
process — drop a folder under `examples/` with a `README.md`, the
design files, and a runnable script if applicable.

Suggested templates:

- A `*_tb.sv` testbench if the design is simulatable.
- A `verify_*.py` script (modeled on
  [timing_closure_demo/verify_timing_closure.py](timing_closure_demo/verify_timing_closure.py)
  or
  [core_features_demo/verify_core_features.py](core_features_demo/verify_core_features.py))
  that drives the workflow with a mock Tcl server, so CI can run it
  without requiring a specific FPGA toolchain.
