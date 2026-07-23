# Simulation sign-off

You are running a simulation-based sign-off on the user's design before they
commit to a bitstream. This catches functional bugs early — when they are
cheap to fix.

## Prerequisites

Ask the user for:

1. The testbench top module name (must match a file already added to the
   project, otherwise `add_sources(files=[...])` first).
2. The simulation duration (e.g. `"1000ns"`, `"10us"`).
3. The simulation type: `rtl` (functional, default) — recommended first.

## Procedure

### 1. RTL simulation

```
run_simulation(top="<tb_name>", kind="rtl", duration="<dur>")
```

For Quartus / Anlogic, this generates the simulation netlist. Tell the user
the launch command to open ModelSim/Questa. For Vivado, XSim runs in-place.

### 2. Functional checks

For each signal/protocol the testbench is supposed to verify:

- Inspect the waveform or `$display` output.
- For each assertion failure, classify as:
  - **Real bug** — RTL is wrong; flag to the user with the failing assertion
    and the responsible module.
  - **TB bug** — testbench expected wrong value; flag and propose a fix.
  - **Race condition** — fix the TB by adding `#1` delays or `<=`
    non-blocking assignments.

### 3. Post-synthesis simulation (recommended)

After RTL sim passes, re-run with gate-level netlist:

```
run_simulation(top="<tb_name>", kind="post_syn", duration="<dur>")
```

Compare results to RTL sim. Any divergence is a real concern — usually
uninitialized state or inferred-latch bugs. Flag to the user; do not
proceed to bitstream until resolved.

### 4. Post-implementation simulation (optional, slow)

For tight timing designs, run timing simulation:

```
run_simulation(top="<tb_name>", kind="post_impl", duration="<dur>")
```

## Output

```
Simulation sign-off:
  TB:        <tb_name>
  Duration:  <dur>

RTL sim:        PASS  (0 assertions failed)
Post-synth sim: PASS  (matches RTL)
Post-impl sim:  SKIPPED (not requested)

Sign-off: YES — safe to proceed to bitstream generation.
```

OR if anything fails:

```
RTL sim: FAIL
  - assertion #3 (tb_alu.v line 47): expected 0x4A, got 0x00
  - module under test: alu (alu.v lines 32-40)
Sign-off: NO — fix RTL before bitstream.
```

## Safety rails

- Never proceed to `generate_bitstream` while any sim reports FAIL.
- Never declare "matches RTL" without actually comparing — if the user has
  not provided expected vectors, ask them.
- For Quartus/Anlogic, be explicit that the user must launch the simulator
  themselves; we only generate the netlist here.
