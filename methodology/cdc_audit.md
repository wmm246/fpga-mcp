# CDC (Clock Domain Crossing) audit

You are auditing a design for unsafe clock domain crossings. The goal is to
identify every CDC path, classify it as safe or unsafe, and propose
constraint + RTL fixes where needed. This is an audit, not a build —
synthesis must have run first.

## Procedure

1. Confirm the project is open and a design is synthesized:

   ```
   current_project()
   report_timing(max_paths=20)
   ```

2. Enumerate the clocks in the design and their relationships:

   ```
   exec_tcl(command="get_clocks -quiet")
   ```

   For Vivado: also run
   `report_clock_interaction -return_string` to get the CDC matrix.
   For Quartus: use `report_clock_transfers -return_string`.
   For Anlogic: parse `report_timing -return_string` per group.

3. Classify each crossing into:
   - **Safe**: 2-FF synchronizer present + correct constraints
     (`set_false_path` or `set_max_delay -datapath_only` on the synchronizer
     input).
   - **CDC — missing constraint**: 2-FF synchronizer present but no
     constraint. FIX: add the constraint.
   - **CDC — missing synchronizer**: combinational logic crosses domains
     directly. FIX: insert 2-FF synchronizer in the RTL (user approval
     needed — may change behavior).
   - **CDC — multi-bit signal**: a bus crossing without Gray-code or
     handshake. FIX: convert to handshake (`req`/`ack`) or Gray code
     (user approval needed — changes logic + latency).

4. For each **Safe** crossing: report it as safe. No action.
5. For each fixable **missing constraint**: apply via `exec_tcl` and
   re-run `report_timing` to confirm.

## Output

Produce a table:

```
| # | Source clock | Dest clock | # paths | Status       | Action |
|---|--------------|------------|---------|--------------|--------|
| 1 | clk_core     | clk_uart   |   12    | Safe         | -      |
| 2 | clk_core     | clk_spi    |    3    | No constraint | added  |
| 3 | clk_a        | clk_b      |    1    | Missing sync | WARN   |
```

End with a summary:

```
CDC audit complete:
  crossings:     16
  safe:          12
  fixed:          3
  need_user_fix:  1
  total paths:   31
```

## Safety rails

- Never modify the user's RTL without explicit approval.
- Never delete or override an existing constraint without surfacing the
  conflict.
- An unsafe crossing that you cannot fix must be flagged `WARN` — do not
  silently let timing "pass" with the constraint removed.
