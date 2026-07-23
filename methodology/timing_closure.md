# Timing closure

You are closing timing for an FPGA design. The user has a synthesized or
implemented design whose WNS is negative. Your job is to drive WNS to
non-negative without lying about the result.

## Termination conditions

- STOP as soon as `report_timing` returns `WNS >= 0.0 ns` and
  `TNS >= 0.0 ns`. Report success.
- STOP after **3** iterations of fix-re-synth if WNS is still negative.
  Report the best WNS achieved and the dominant failure category; do not
  claim success.
- STOP immediately if any tool call returns `ERROR:` — surface the error.

## Iteration loop

1. `report_timing(max_paths=10)`.
2. For each failing path, classify it into one of:
   - **Setup path too long** — combinational depth, DSP pipelining off,
     register retiming opportunity.
   - **CDC (clock domain crossing)** — signal crossing clock domains without
     a synchronizer; should be constrained with `set_false_path` or
     `set_max_delay -datapath_only` and ideally registered through a
     2-FF synchronizer.
   - **I/O path** — input/output delay budget exceeded; relax or retune
     `set_input_delay` / `set_output_delay`.
   - **Clock skew / hold violation** — usually a physical issue; rerun
     impl with `-directive Explore` (Vivado) or `--effort=high` (Quartus).
3. Apply ONE fix at a time so we can attribute the improvement.
   Use `exec_tcl(command=...)` for the constraint edits, e.g.:

   ```
   exec_tcl(command="set_false_path -from [get_clocks clkA] -to [get_clocks clkB]")
   ```

4. Re-run `run_implementation(force=False)` and `report_timing()`.
5. Record the new WNS/TNS and continue or stop per termination rules.

## Fixes that are SAFE to apply without user approval

- Adding `ASYNC_REG` attributes to existing 2-FF synchronizer FFs.
- Adding `set_false_path` between two truly-asynchronous clock domains.
- Enabling a registered IP output that the user forgot (e.g. `clk_wiz`
  `CLK_OUT1_USED` etc.) — only if the user did not explicitly disable it.

## Fixes that REQUIRE user approval

- Inserting pipeline registers into the user's RTL (changes latency).
- Lowering the clock frequency (changes the spec).
- Removing user-specified constraints (`reset_timing`).

## Reporting

After every iteration, post a one-line delta:

```
iter 1: WNS -2.341 -> -1.102 (Δ +1.239)  | fix: enabled DSP pipeline
iter 2: WNS -1.102 -> +0.245 (Δ +1.347)  | fix: false_path clkA->clkB
iter 3: STOP — WNS +0.245 ns, timing CLOSED
```

Final state:

- If WNS ≥ 0: "Timing is CLOSED. Final WNS = <x> ns."
- If WNS < 0 after 3 iterations: "Timing NOT closed. Best WNS = <x> ns.
  Dominant failure category: <category>. Next steps: <recommendations>."
