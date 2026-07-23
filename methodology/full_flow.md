# Full end-to-end flow

You are running a full FPGA build for the user. Use the fpga-mcp tools
to take the design from sources to a programmed bitstream, verifying each
step before moving on.

## Inputs you need from the user

Ask explicitly if any are missing — do not invent values:

1. **Backend** — `vivado`, `quartus`, or `anlogic`. Default to the active
   backend reported by `status()`. Switch with `set_backend(name=...)`.
2. **Part number** — e.g. `xc7a35tcpg236-1` (Vivado), `5CGXFC5C6F23C7`
   (Quartus), `EG4S20BG256` (Anlogic).
3. **Project name and directory**.
4. **Source files** — list of `.v/.sv/.vhd` paths.
5. **Constraints** — `.xdc` (Vivado), `.sdc` (Quartus/Anlogic), `.qsf`
   (Quartus), `.fdc` (Anlogic).
6. **Top module** — required for synth.
7. (Optional) **Program after bitstream** — yes / no.

## Procedure

Run these steps in order. After each step, inspect the returned text. If the
result starts with `ERROR:` or shows `ok=False`, stop and explain the failure
to the user; do NOT continue to the next step.

1. `ping_backend()` — verify the EDA tool's Tcl server is reachable. If not,
   tell the user exactly how to start it (see the matching
   `tcl/<vendor>_server.tcl` script).
2. `create_project(name=..., part=..., directory=..., top=..., hdl=...)`.
3. `add_sources(files=[...])`.
4. `add_constraints(files=[...])` — if any were provided.
5. `set_top(top=...)` — belt-and-suspenders even if `create_project` set it.
6. `run_synthesis(force=False)`.
7. `report_utilization()` — sanity-check LUT/FF/RAM/DSP usage.
8. `report_timing(max_paths=10)` — record WNS/TNS. If WNS < 0, flag the
   failing paths but DO NOT pretend timing is closed; switch to the
   `timing_closure` workflow.
9. `run_implementation(force=False)`.
10. `report_timing(max_paths=10)` again — post-route numbers are what counts.
11. `generate_bitstream(include_ltx=True)`.
12. If the user opted to program: `program_device(bitstream=<path>,
    device_index=0)`.

## Safety rails

- Never claim `pass` on a path with negative slack. Always surface the
  failing endpoints.
- If a step's log mentions `ERROR: [...]` lines, include the first 5 in your
  summary and stop.
- After bitstream generation, always report the exact `.bit` / `.sof` path so
  the user can program it manually later if needed.

## Output to the user

When done, give a concise report:

```
Backend:    <name>
Project:    <path>
Part:       <part>
Synth:      ok (WNS=<ns>, TNS=<ns>)
Impl:       ok (WNS=<ns>, TNS=<ns>)
Bitstream:  <path>
Programmed: yes/no
```
