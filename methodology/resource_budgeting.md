# Resource budgeting

You are helping the user stay within the resource budget for their target
part. Synthesis must have run for this audit to be useful.

## Procedure

1. `report_utilization()` — get the current usage.

2. Ask the user for the budget (if not provided): typical numbers are
   "LUT ≤ 70%", "FF ≤ 70%", "BRAM ≤ 80%", "DSP ≤ 80%". The 70% rule of
   thumb keeps headroom for routing congestion and future additions.

3. For each resource in the report, compute:
   - `pct_used = used / available`
   - `headroom = available - used`
   - Status: `OK` (< budget), `TIGHT` (within 10% of budget),
     `OVER` (over budget).

4. For each `OVER` or `TIGHT` resource, propose a targeted optimization:

   | Resource        | Optimization                                              |
   |-----------------|----------------------------------------------------------|
   | LUT             | Pack FSMs into block RAM; check for inferred logic vs DSP. |
   | FF              | Look for unpipelined data paths; check for redundant registers. |
   | BRAM            | Replace small BRAMs with distributed RAM (Vivado: `RAM_PIPELINED`). |
   | DSP             | Enable DSP packer; check for missed multiply-accumulate. |
   | I/O             | Recheck pin assignments; consolidate LVDS pairs. |

5. If user approves a change, apply it (RTL edit via the user or via
   `exec_tcl` if it's a property/attribute), then re-run synth and
   `report_utilization()`.

## Output

```
Resource report (budget: LUT 70%, FF 70%, BRAM 80%, DSP 80%):

  LUT       18342 /  41600   44.1%   OK
  FF        21058 /  83200   25.3%   OK
  BRAM         28 /    100   28.0%   OK
  DSP          18 /    180   10.0%   OK

No resources over budget.
```

If anything is OVER:

```
  DSP   165 / 180  91.7%  OVER (budget 80%)

Recommendations:
  1. Enable DSP packer on `mult_acc_x4` (saves ~12 DSPs).
     exec_tcl(command="set_property USE_DSP48 yes [get_cells mult_acc_x4_inst/*]")
  2. Replace `coef_rom` (4096×8) with a BRAM (saves 8 DSPs).
```

## Safety rails

- Never report OVER without showing the exact % and headroom.
- Never modify RTL properties without user approval.
- If the design simply doesn't fit, say so clearly: recommend a larger
  part with specific upgrade suggestions (e.g. xc7a35 → xc7a50, or
  EP4CE6 → EP4CE10).
