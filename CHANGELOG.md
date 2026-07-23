# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public release of `fpga-mcp`.
- Multi-vendor EDA backend abstraction: Xilinx Vivado, Intel Quartus, Anlogic.
- Vivado backend driven by a bundled Tcl TCP server (port 9999), similar in
  spirit to SynthPilot but reimplemented from scratch and MIT-licensed.
- Quartus backend driven by `quartus_sh -t` over a Tcl session.
- Anlogic backend driven by the TangDynasty / TD CLI flow.
- MCP server exposing project / synth / impl / IP / sim / bitstream / reports
  tool groups, all parameterized by the active backend.
- **689 declarative MCP tools** (vs. the original 22 hand-written tools):
  - 22 high-level vendor-agnostic tools (`create_project`, `run_synthesis`,
    `report_timing`, `exec_tcl`, …) routed to backend Python methods.
  - 343 Vivado tools (`viv_*`) covering project/fileset, synth/impl runs,
    IP/BD, constraints, timing reports, utilization/DRC, simulation,
    hardware manager, debug cores, netlist queries and parts.
  - 167 Quartus tools (`q_*`) covering project/flow, SDC/STA timing,
    reports, IP/Qsys, power and EDA.
  - 157 Anlogic TangDynasty tools (`a_*`) covering project/files, synth/impl,
    IP, constraints, reports, netlist, simulation and programming.
- Declarative `ToolSpec` catalogue + factory pattern: adding a tool = one
  line in the right `tool_defs/<vendor>.py`. The factory builds the runtime
  callable automatically, validates required args, and dispatches to either
  a Python handler or a rendered Tcl command.
- Methodology layer (`methodology/*.md`) exposing named expert workflows as
  MCP prompts: full-flow, timing-closure, cdc-audit, resource-budgeting,
  soc-bringup, sim-signoff, bitstream-handoff.
- CLI: `fpga-mcp setup`, `fpga-mcp doctor [--fix]`, `fpga-mcp run`,
  `fpga-mcp backends`, `fpga-mcp tcl-server-path <backend>`,
  `fpga-mcp version`.
- `pyproject.toml` packaging with `fpga-mcp` / `fpga` console scripts.
- 69-test suite covering: Tcl helpers, config + env overrides, package
  surface, FastMCP server (tool count ≥ 500, vendor coverage, prompt list,
  non-empty descriptions), tool factory (spec parsing, arg inference,
  template rendering, handler dispatch, catalogue invariants), all three
  backends via in-process mock Tcl servers, and the CLI.

### Changed
- Renamed the project from `omni-fpga-mcp` to `fpga-mcp`. Package name,
  import path, console scripts, env vars (`FPGA_MCP_*`), config paths and
  CI all use the new name.
- Switched the server from the hand-written `fpga_mcp.tools` module (8
  domain modules, 22 functions) to the declarative
  `fpga_mcp.tool_defs` factory. The old `tools/` directory has been
  removed; the 22 high-level tools remain available via
  `tool_defs/common.py` + `_handlers.py` with identical behaviour.

### Removed
- `fpga_mcp/tools/` — superseded by `fpga_mcp/tool_defs/` + `_handlers.py`.
