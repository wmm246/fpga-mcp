# SoC bring-up (PS + PL)

You are bringing up a Zynq-style or Cyclone V SoC design that combines a
hard processor system (PS) with FPGA fabric (PL). This is a multi-step flow;
be patient and methodical.

## Supported parts

- Xilinx Zynq-7000 (e.g. `xc7z010clg400-1`)
- Xilinx Zynq UltraScale+ (e.g. `xczu3eg-sfvc784-1-e`)
- Intel Cyclone V SoC (e.g. `5CSEMA5F31C6`)

This workflow assumes `set_backend(name="vivado")` for Zynq and
`set_backend(name="quartus")` for Cyclone V SoC. The Anlogic EG4 family has
no hard PS — skip this workflow for those parts.

## Procedure

### 1. Configure the PS / HPS

For Zynq:

```
create_ip(ip_name="processing_system7", name="ps7_0",
          properties={"preset": "ZC702" or user-supplied})
set_ip_property(ip_name="ps7_0", prop="PCW_USE_M_AXI_GP0", value="1")
set_ip_property(ip_name="ps7_0", prop="PCW_USE_S_AXI_HP0", value="1")
generate_ip(ip_name="ps7_0")
```

For Zynq UltraScale+ use the `zynq_ultra_ps_e` IP. For Cyclone V SoC,
configure the HPS via Qsys (`create_ip(ip_name="hps_bridge", ...)`).

Ask the user explicitly:
- Which preset / board file to use?
- Which peripherals (UART, Ethernet, USB, SD)?
- How many AXI ports between PS and PL?

### 2. Build the Block Design

For Vivado: drive the BD via Tcl (`exec_tcl(command=...)`):

```
create_bd_design "soc_top"
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7_0
apply_bd_automation -rule "..."  # let Vivado autoconnect
validate_bd_design
make_wrapper -files [get_files soc_top.v] -top
```

For Quartus: build the Qsys system similarly.

### 3. Integrate the user's PL RTL

```
add_sources(files=["pl_core.v", "axi_regs.v", ...])
set_top(top="soc_top_wrapper")  # BD wrapper generated above
add_constraints(files=["pin_constraints.xdc"])
```

### 4. Synthesize and verify

```
run_synthesis(force=False)
report_utilization()
report_timing(max_paths=10)
```

For SoC designs, expect BRAM/DSP usage to be elevated by the PS-side IP. Pay
attention to **PL clock domains** — they must come from the PS FCLK pins or
the design will have undefined clock sources.

### 5. Generate the boot files

After impl + bitstream:

```
generate_bitstream(include_ltx=False)
```

For Zynq, the bitstream is wrapped into a `BOOT.bin` via the
`bootgen` tool — call this via `exec_tcl` if available, otherwise instruct
the user to run:

```
bootgen -image boot.bif -arch zynqmp -o BOOT.bin
```

### 6. Handoff to software

Provide:
- The bitstream / BOOT.bin path.
- The register map (offset, width, R/W) for every AXI slave the user added.
- The expected boot log line ("U-Boot 2020.01 ...").

## Safety rails

- Never attempt to flash an SoC board without the user confirming the SD
  card / QSPI is wired the way the bitstream expects.
- The PL clock source MUST be configured before timing analysis. If
  `report_timing` shows a clock with `Period = 0`, stop — the BD's
  `FCLK_CLK0` is not wired up.
- If `make_wrapper` fails, do not attempt to override the top — fix the
  BD instead.
