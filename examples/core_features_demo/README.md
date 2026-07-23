# core_features_demo

> **One script, every core feature, one binary verdict.**

`verify_core_features.py` drives each category of the `EDABackend`
contract through fpga-mcp's high-level typed Python tools and asserts
that each one returns a well-formed result. Like
[`timing_closure_demo`](../timing_closure_demo/), it ships with a mock
Tcl TCP server so it runs on any machine without Vivado / Quartus /
Anlogic installed. CI runs it on every PR.

## What it verifies

| Phase | Category | Key assertion |
|---|---|---|
| 00 | Lifecycle | `connect` → `is_connected() == True`; `disconnect` → `False` |
| 01 | Project mgmt | `create_project` returns `ProjectHandle` with name/part/backend/top |
| 02 | Sources | `add_sources` returns file count; `set_top` updates the handle |
| 03 | Constraints | `add_constraints` returns file count |
| 04 | Synthesis | `run_synthesis` returns `RunResult(ok=True, stage="synthesis")` |
| 05 | Implementation | `run_implementation` returns `RunResult(ok=True, stage="implementation")` |
| 06 | IP | `create_ip` returns instance name; `set_ip_property` (single + dict shape); `generate_ip` succeeds |
| 07 | Timing report | `report_timing` parses finite `wns_ns`/`tns_ns`; `failing_paths` is a list |
| 08 | Utilization | `report_utilization` returns ≥4 rows; each row has used/available/pct |
| 09 | Simulation | `run_simulation` returns `RunResult(ok=True, stage="simulation")` |
| 10 | Bitstream | `generate_bitstream` returns an existing `Path` ending in `.bit` |
| 11 | Programming | `program_device` returns `RunResult(ok=True, stage="program")` |
| 12 | Escape hatch | `exec_tcl` round-trips a raw command and returns a `str` |
| 13 | Session mgmt | `BackendManager.available()` lists all 3 vendors; `switch`/`status`/`ensure_connected` work; `switch` to unknown raises `BackendError` |

Each phase is wrapped in try/except so a failure in one category doesn't
hide the result of the others — the script always runs all 14 and
prints a per-phase PASS/FAIL table at the end.

## Why this exists

`timing_closure_demo` proves the *report-driven feedback loop* works
end-to-end (broken → diagnose → fix → re-verify). But it only exercises
~5 of the 14 backend verbs. A regression in `report_utilization`,
`generate_ip`, `program_device`, or the multi-backend session layer
could ship undetected.

This demo closes that gap. It's the canary for the **typed surface**
itself: if a refactor breaks the `RunResult`/`TimingReport`/
`UtilizationReport`/`ProjectHandle` contracts, or a backend's
implementation drifts from the `EDABackend` Protocol, this script
catches it on the next PR.

It has already caught one: `VivadoBackend.create_ip(**props)` used to
call `set_ip_property(inst_name, list(props.items()))` with only 2
positional args, even though `set_ip_property(ip_name, prop, value)`
requires 3. The bug was invisible to the existing test suite because
no test ever called `create_ip` with keyword properties — phase 06 of
this script does, and now the call site is fixed.

## Run it

```bash
python3 verify_core_features.py
# Exits 0 when all 14 phases pass.
```

No EDA tool required. The mock Tcl server is started in-process on a
random port and torn down at exit.

## How it's structured

- `vivado_handler(cmd)` — the mock Tcl server's command handler. It's
  stateful: it tracks the project, the synth/impl/bit runs, the IP
  instances, and the JTAG devices, returning realistic Vivado-shaped
  output for every command the backend emits. It also writes a fake
  `.bit` file to disk when `launch_runs impl_1 -to_step write_bitstream`
  arrives so the `generate_bitstream` / `program_device` round-trip has
  a real artifact to point at.
- `phase_NN_<name>(backend)` — one function per phase, each asserting
  the key invariant for that category. Phases that need fixtures
  (a source file, a constraint file, a bitstream) take them as args.
- `phase_13_session(workdir)` — stands up **three** mock Tcl servers
  (one per vendor on distinct ports) and drives `BackendManager`
  across all of them, so the multi-vendor session layer is exercised
  too.
- `main()` — runs each phase in turn, captures PASS/FAIL, prints a
  verdict table, and returns `0` only if all 14 pass.

## Adding a phase

When a new core verb lands on the `EDABackend` Protocol (e.g.
`run_power_analysis`), add a phase here so it stays covered:

1. Append `("Phase NN: <category>", "phase_NN_<name>")` to `PHASES`.
2. Implement `phase_NN_<name>(backend)` — call the verb, assert the
   key invariant, raise on mismatch.
3. Extend `vivado_handler` to return realistic output for any new Tcl
   commands the backend emits for that verb.
4. Re-run the script — it should print `PASS` for the new phase.
