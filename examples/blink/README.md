# blink — minimal Vivado + fpga-mcp example

A 4-LED blinker on a 100 MHz Artix-7 board. Fits every Arty/Basys/Nexys
class board. Use it to verify your `fpga-mcp` install end-to-end before
writing your own design.

Files:

| File | Purpose |
|---|---|
| [blink.v](blink.v) | The Verilog — a 32-bit counter + LED rotator. |
| [blink.xdc](blink.xdc) | Pin + clock constraints for Arty A7-35. |
| [blink_tb.sv](blink_tb.sv) | Testbench (Vivado XSim-compatible). |

## Run it

### 1. Start a Vivado Tcl TCP server

```bash
vivado -mode tcl -source ../../tcl/vivado_server.tcl
# You'll see:
#   fpga-mcp/vivado-server: ready, listening on 127.0.0.1:9999
```

### 2. Start the MCP server

In another terminal:

```bash
fpga-mcp run
```

Or wire it into Claude Desktop / Cursor first:

```bash
fpga-mcp setup --register
# then restart your editor
```

### 3. Ask the AI

In your editor, with the `examples/blink/` folder open:

> "Use fpga-mcp to create an Artix-7 project for xc7a35tcpg236-1 in
> `./out`, add blink.v and blink.xdc, run synthesis, run implementation,
> and report timing. Tell me the WNS."

The AI will (typically):

1. `set_backend("vivado")`
2. `create_project(name="blink", part="xc7a35tcpg236-1", directory="./out", top="blink")`
3. `add_sources(files=["blink.v"])`
4. `add_constraints(files=["blink.xdc"])`
5. `run_synthesis()`
6. `run_implementation()`
7. `report_timing(max_paths=10)` → reads WNS/TNS, flags failing paths
8. `generate_bitstream()`

### 4. Simulate first (optional but recommended)

> "Run an RTL simulation of `blink` for 10 ms and tell me when the first LED
> toggles."

The AI calls `run_simulation(top="blink_tb", kind="rtl", duration="10ms")`.

### 5. Program the board

> "Program the FPGA with the bitstream we just generated."

The AI calls `program_device(bitstream="./out/blink.runs/impl_1/blink.bit")`.

## What this teaches you

- All 5 high-level flow tools work: `create_project` → `add_sources` →
  `run_synthesis` → `run_implementation` → `generate_bitstream`.
- `report_timing` parses Vivado's timing report into a structured result
  (WNS/TNS/failing paths) the AI can reason about.
- `exec_tcl` is available if the AI needs anything beyond the typed surface
  (e.g. `report_clocks`, `get_clocks`).

## Switching boards

If you have a Basys3, Nexys A7 or any Artix-7 board, only `blink.xdc`
changes — update the `PACKAGE_PIN` assignments to match your board's
buttons/LEDs/clock. The Verilog is board-agnostic.
