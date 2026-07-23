<div align="center">

# fpga-mcp

**One MCP, three FPGA vendors. Drive Vivado, Quartus and Anlogic from your AI assistant.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://pypi.org/project/fpga-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey)](#)
[![Tests](https://img.shields.io/badge/tests-69%20passing-brightgreen)](#)
[![Tools](https://img.shields.io/badge/tools-689%20across%203%20vendors-blue)](#)

</div>

> **English** | [简体中文](#简体中文)

`fpga-mcp` is an open-source [MCP](https://modelcontextprotocol.io)
server that lets your AI assistant (Claude, Cursor, Cline, Codex, …) drive
**Xilinx Vivado**, **Intel Quartus** and **Anlogic TangDynasty** for FPGA
development — create projects, write & lint RTL, run synthesis /
implementation, close timing, configure IP, run simulations and program
hardware — all by **describing what you want**, in plain language.

It runs **locally**: your RTL never leaves your machine. **689 typed tools**
cover the whole FPGA flow with vendor-specific depth — 343 Vivado, 167
Quartus, 157 Anlogic, plus 22 high-level vendor-agnostic verbs — and a free
**methodology layer** turns them into one-sentence outcomes via 7 expert
workflows.

Inspired by [SynthPilot](https://github.com/LNC0831/SynthPilot) (Vivado-only,
proprietary) and its companion [oh-my-fpga](https://github.com/LNC0831/oh-my-fpga)
skill pack. fpga-mcp is the **open, multi-vendor** rewrite: MIT-licensed,
one repo, three vendors, ~500+ tools just like SynthPilot — but with no
edition gating and no closed-source tier.

## Why this exists

| | SynthPilot + oh-my-fpga | **fpga-mcp** |
|---|---|---|
| Vendors | Xilinx Vivado only | Vivado + Quartus + Anlogic |
| License | Proprietary + MIT skills | **MIT everywhere** |
| Methodology layer | Separate repo | Same repo, same release |
| Edition gating | Free/Pro/Max tiers | No tiers, no gating |
| Tool count | ~500 (atomic) | **689** (22 high-level + 667 atomic) |
| Tool implementation | 500 hand-written functions | Declarative `ToolSpec` catalogue + factory |

The catalogue approach scales: every tool is a 5-tuple
`(name, tcl_template, summary, category, vendor)` and the factory builds the
runtime callable automatically. Adding a tool = adding one line to the right
`tool_defs/<vendor>.py` — no boilerplate.

## How it works

```
 AI editor (Claude / Cursor / Cline / …)
        │   MCP (stdio)
        ▼
   fpga-mcp  ──TCP:9999──▶  Vivado  (Tcl server)
                  ──TCP:9998──▶  Quartus (Tcl server)
                  ──TCP:9997──▶  Anlogic (Tcl server)
```

The AI calls MCP tools; fpga-mcp routes them to the right vendor backend
over a local socket. Structured results (timing metrics, utilization, error
summaries, …) come back to the AI as text it can reason about.

Each vendor's TCP server is a small Tcl script (`tcl/<vendor>_server.tcl`)
that you `source` once inside the running EDA tool. The protocol is identical
across vendors — only the Tcl commands differ.

## Quick start

```bash
# Install (Python 3.10+)
pip install fpga-mcp
# or: uv tool install fpga-mcp

# Detect installed EDA tools, write config, register in AI clients
fpga-mcp setup

# Start one Tcl server (matches the tool you want to drive)
vivado -mode tcl -source tcl/vivado_server.tcl            # Xilinx
quartus_sh -t tcl/quartus_server.tcl                       # Intel
td -tcl   # then inside:  source tcl/anlogic_server.tcl    # Anlogic
```

That's it. Your AI editor's MCP menu now lists `fpga-mcp` as a server with
689 tools and 7 methodology prompts.

Want to wire the MCP client up by hand?

```jsonc
{ "mcpServers": { "fpga-mcp": { "command": "fpga-mcp", "args": ["run"] } } }
```

Something off later? `fpga-mcp doctor` diagnoses it and `fpga-mcp doctor
--fix` self-heals.

## An example

> **You**: *"Create an Artix-7 project, add this counter, run synthesis, and
> show me the timing."*
>
> **The AI**: `set_backend("vivado")` → `create_project(...)` →
> `add_sources([...])` → `run_synthesis()` → `report_timing(max_paths=10)`
> → reports WNS/TNS and flags any failing paths — no Tcl, no wizard clicking.

## Tool surface (689)

The catalogue is split into a high-level vendor-agnostic layer plus deep
vendor-specific layers:

| Layer | Count | Examples |
|---|---|---|
| Common (vendor-agnostic) | 22 | `list_backends`, `set_backend`, `create_project`, `run_synthesis`, `report_timing`, `exec_tcl` |
| Vivado (`viv_*`) | 343 | `viv_get_clocks`, `viv_create_bd`, `viv_report_timing_summary`, `viv_open_hw_target` |
| Quartus (`q_*`) | 167 | `q_create_clock`, `q_run_sta`, `q_execute_flow_to`, `q_get_failing_paths` |
| Anlogic (`a_*`) | 157 | `a_create_project`, `a_run_pnr`, `a_report_timing`, `a_enable_pipelining` |
| **Total** | **689** | |

Each vendor-prefixed tool is a thin wrapper that renders a Tcl template and
sends it to the matching backend's Tcl TCP server. The 22 common tools route
to backend Python methods (e.g. `create_project` calls `backend.create_project()`),
so they read the same across vendors.

`exec_tcl` is the universal escape hatch — anything missing from the typed
surface can be done via raw vendor Tcl.

## Methodology prompts (7)

Named, opinionated workflows shipped as markdown and exposed as MCP prompts.
Pick one from your client's `/` menu:

| Prompt | What it does |
|---|---|
| `full_flow` | End-to-end: create → synth → impl → bitstream → (optional) program. |
| `timing_closure` | Iterate timing fixes until WNS ≥ 0, with safety rails (never fake-pass). |
| `cdc_audit` | Audit clock-domain crossings, classify safe/unsafe, propose fixes. |
| `resource_budgeting` | Compare utilization against a budget; suggest targeted optimizations. |
| `sim_signoff` | RTL + post-synth + (optional) timing simulation; gate bitstream on pass. |
| `bitstream_handoff` | Generate, checksum, program, verify. Hands off to hardware. |
| `soc_bringup` | Bring up Zynq / Cyclone V SoC: PS config, BD, PL integration, boot files. |

Each prompt is a plain markdown file under [`methodology/`](methodology/) —
edit them, add your own, drop a new `.md` in and it shows up at next start.

## Configuration

Default config lives at `~/.config/fpga-mcp/config.json` (Linux),
`%APPDATA%\fpga-mcp\config.json` (Windows). Every value can be
overridden by an environment variable:

| Variable | Default | Purpose |
|---|---|---|
| `FPGA_MCP_BACKEND` | `vivado` | Active backend. |
| `FPGA_MCP_LOG_LEVEL` | `INFO` | Logging verbosity. |
| `FPGA_MCP_WORKSPACE` | cwd | Default project root. |
| `FPGA_MCP_VIVADO_HOST` / `_PORT` / `_PATH` | `127.0.0.1` / `9999` / auto | Vivado server. |
| `FPGA_MCP_QUARTUS_HOST` / `_PORT` / `_PATH` | `127.0.0.1` / `9998` / auto | Quartus server. |
| `FPGA_MCP_ANLOGIC_HOST` / `_PORT` / `_TD_PATH` | `127.0.0.1` / `9997` / auto | Anlogic server. |

## Architecture

```
src/fpga_mcp/
├── server.py           # FastMCP entry point
├── cli.py              # `fpga-mcp setup / doctor / run / version`
├── session.py          # BackendManager (multi-vendor switching)
├── config.py           # Config + env overrides
├── detect.py           # Detect Vivado/Quartus/Anlogic binaries
├── prompts.py          # Register methodology/*.md as MCP prompts
├── _client_registry.py # Auto-register in Claude/Cursor/etc.
├── transports/
│   ├── base.py         # EDABackend protocol (vendor-agnostic contract)
│   ├── _base_tcp.py    # Common TCP/Tcl plumbing
│   ├── _tcl_client.py  # Wire-format client (JSON over TCP)
│   ├── _tcl_helpers.py # Tcl string/list quoting
│   ├── vivado.py       # Xilinx Vivado backend
│   ├── quartus.py      # Intel Quartus backend
│   └── anlogic.py      # Anlogic TangDynasty backend
└── tool_defs/          # 689 declarative tool specs + factory
    ├── __init__.py     # ToolSpec / ArgSpec / register_all / factory
    ├── _handlers.py    # Python handlers for the 22 common tools
    ├── common.py       # 22 high-level vendor-agnostic specs
    ├── vivado.py       # 343 Vivado specs
    ├── quartus.py      # 167 Quartus specs
    └── anlogic.py      # 157 Anlogic specs

tcl/                    # Tcl TCP server scripts (sourced inside each EDA tool)
├── _omni_protocol.tcl  # Shared JSON-over-TCP RPC
├── vivado_server.tcl   # vivado -mode tcl -source ...
├── quartus_server.tcl  # quartus_sh -t ...
└── anlogic_server.tcl  # td -tcl, then `source ...`

methodology/            # Plain-markdown workflow prompts
├── full_flow.md
├── timing_closure.md
├── cdc_audit.md
├── resource_budgeting.md
├── sim_signoff.md
├── bitstream_handoff.md
└── soc_bringup.md

tests/                  # 69 tests, incl. end-to-end mocks of all 3 vendors
```

Adding a new vendor tool = one `ToolSpec(...)` line in the right
`tool_defs/<vendor>.py`. Adding a new vendor = implementing the
`EDABackend` protocol once in `transports/<vendor>.py` plus a
`tcl/<vendor>_server.tcl` wrapper, then dropping a new `tool_defs/<vendor>.py`
catalogue. The MCP server picks up everything automatically.

## Development

```bash
git clone https://github.com/wmm246/fpga-mcp
cd fpga-mcp
pip install -e '.[dev]'   # editable install
pytest                    # 69 tests should pass
fpga-mcp version
```

The repo has no compiled artifacts; the only system dependency is one of
the supported EDA tools (Vivado / Quartus / TangDynasty) when you actually
want to drive hardware. The test suite ships with an in-process mock of the
Tcl protocol for all three vendors, so CI runs without any FPGA tool installed.

### Examples

Three runnable examples live under [`examples/`](examples/):

- [`examples/blink/`](examples/blink/) — minimal LED blinker, walks through
  the 5 high-level verbs (`create_project` → `add_sources` → `run_synthesis`
  → `run_implementation` → `generate_bitstream`). Needs a real Vivado +
  Artix-7 board.
- [`examples/timing_closure_demo/`](examples/timing_closure_demo/) — a
  verifiable timing-closure workflow: starts with a deliberately broken
  design (WNS = -2.5 ns), drives the full closure loop via fpga-mcp, swaps
  in a pipelined version, and asserts `WNS_final ≥ 0`. **No Vivado needed**
  — ships with a mock Tcl server so it runs on any machine. CI runs it on
  every PR.
- [`examples/core_features_demo/`](examples/core_features_demo/) — drives
  **all 14 core feature categories** of the `EDABackend` contract
  (lifecycle, project, sources, constraints, synth, impl, IP, timing,
  utilization, simulation, bitstream, programming, `exec_tcl`, multi-backend
  session) through fpga-mcp's typed Python tools and asserts each one
  returns a well-formed result. **No Vivado needed** — ships with its own
  mock Tcl server. CI runs it on every PR. Catches regressions in verbs
  that `timing_closure_demo` doesn't touch.

```bash
# Run the verifiable demos (no Vivado required):
python examples/timing_closure_demo/verify_timing_closure.py
python examples/core_features_demo/verify_core_features.py
```

### Docker

A multi-stage `Dockerfile` builds a slim runtime image (~80 MB) that
ships just the MCP server, no EDA tools. Use it when you want a
reproducible environment without polluting your system Python.

```bash
docker build -t fpga-mcp .
docker run --rm fpga-mcp version
docker run --rm fpga-mcp doctor

# Stdio MCP server (for Claude Desktop / Cursor to attach):
docker run --rm -i fpga-mcp

# Reach a Tcl server running on the host (Linux):
docker run --rm --network=host \
  -e FPGA_MCP_VIVADO_HOST=127.0.0.1 \
  -e FPGA_MCP_VIVADO_PORT=9999 \
  -i fpga-mcp
```

A [`docker-compose.yml`](docker-compose.yml) is included with stdio +
tunnel + cli profiles. See the file's header comment for Claude Desktop /
Cursor config snippets.

CI builds the image on every push to validate the Dockerfile doesn't
bit-rot. Pushing to a registry is **not** automatic — wire up
`docker/login-action` + `docker/build-push-action` with `push: true` when
you're ready to publish.

## License

MIT — see [LICENSE](LICENSE). The Tcl server scripts, methodology markdown
and Python code are all MIT. No proprietary edition, no gating — take it,
fork it, ship it.

---

<a name="简体中文"></a>
## 简体中文

**一个 MCP,三家 FPGA 厂商。让 AI 替你开 Vivado / Quartus / 安路 TangDynasty。**

`fpga-mcp` 是一个开源 [MCP](https://modelcontextprotocol.io) 服务器,
让你的 AI 助手(Claude、Cursor、Cline、Codex…)用**自然语言**控制 Xilinx
Vivado、Intel Quartus、安路 TangDynasty 做 FPGA 开发——建项目、写/查 RTL、跑
综合与实现、收敛时序、配置 IP、跑仿真、烧录硬件。**全程本地运行,RTL 不出本机。**

**689 个类型化工具**覆盖完整 FPGA 流程,按厂商拆分深度——343 个 Vivado、167 个
Quartus、157 个 Anlogic,加上 22 个高层跨厂商动词——7 个方法论 prompts 把它们
变成一句话的结果。

灵感来自 [SynthPilot](https://github.com/LNC0831/SynthPilot)(仅 Vivado、专有)
与配套的 [oh-my-fpga](https://github.com/LNC0831/oh-my-fpga) 技能包。
fpga-mcp 是它们的**开源、多厂商**重写:MIT 协议,一个仓库,三家厂商,工具数与
SynthPilot 持平 ~500+,但无版本门槛、无闭源分级。

### 快速开始

```bash
pip install fpga-mcp
fpga-mcp setup                 # 一条命令,引导式上手
vivado -mode tcl -source tcl/vivado_server.tcl   # 启动 Vivado Tcl 服务器
```

### 与原项目对比

| | SynthPilot + oh-my-fpga | **fpga-mcp** |
|---|---|---|
| 厂商 | 仅 Xilinx Vivado | Vivado + Quartus + 安路 |
| 授权 | 专有 + MIT skills | **全 MIT** |
| 方法论层 | 独立仓库 | 同仓库、同发布 |
| 版本门槛 | Free/Pro/Max | 无门槛 |
| 工具数 | ~500 原子 | **689**(22 高层 + 667 原子)|
| 工具实现 | 500 个手写函数 | 声明式 `ToolSpec` 目录 + 工厂 |

### 工作原理

```
 AI 编辑器 (Claude / Cursor / Cline / …)
        │   MCP (stdio)
        ▼
   fpga-mcp  ──TCP:9999──▶  Vivado  (Tcl server)
                  ──TCP:9998──▶  Quartus (Tcl server)
                  ──TCP:9997──▶  Anlogic (Tcl server)
```

AI 调用 MCP 工具,fpga-mcp 通过本地 socket 路由到对应厂商的后端,把结构化
结果(时序、资源、错误摘要…)返回给 AI。

每个厂商的 Tcl 服务器是一个小脚本(`tcl/<厂商>_server.tcl`),在对应 EDA 工具
里 `source` 一次即可。三个厂商的协议完全一致,只是 Tcl 命令不同。

### 例子

> **你**:*"建一个 Artix-7 工程,加入这个计数器,跑综合,把时序给我看看。"*
>
> **AI**:`set_backend("vivado")` → `create_project(...)` →
> `add_sources([...])` → `run_synthesis()` → `report_timing(max_paths=10)`
> → 报告 WNS/TNS 并标出违例路径——不写 Tcl,不点向导。

详见 [English section above](#english)。

### 授权

MIT —— 见 [LICENSE](LICENSE)。Tcl 服务器脚本、方法论 markdown、Python 代码全部 MIT。
没有专有版、没有版本门槛——拿走、fork、自用随意。

<!-- BEGIN TOOL INDEX -->
## Tool index

Auto-generated by `scripts/gen_tool_index.py` from the live catalogue. Do not edit by hand — re-run the script after adding tools.

**Total: 816 tools** (51 common, 441 vivado, 167 quartus, 157 anlogic)

### Common (vendor-agnostic) (51)

<details><summary><code>constraints</code> (5)</summary>

| Name | Summary |
|---|---|
| `create_clock_constraint` | Define a primary clock. |
| `create_io_constraint` | Pin assignment + I/O standard. |
| `get_all_clocks` | List all defined clocks. |
| `get_clock_info` | Get clock period, waveform, sources. |
| `save_constraints` | Write constraints to XDC file. |

</details>

<details><summary><code>files</code> (6)</summary>

| Name | Summary |
|---|---|
| `append_to_file` | Append content to file. |
| `create_constraint_file` | Create new XDC file. |
| `create_source_file` | Create new Verilog/VHDL file with template. |
| `list_all_files` | List project files. |
| `read_file` | Read file contents. |
| `read_file_lines` | Read specific line range. |

</details>

<details><summary><code>flow</code> (7)</summary>

| Name | Summary |
|---|---|
| `export_hardware` | Export hardware definition (.xsa) for embedded development. |
| `generate_bitstream` | Generate the bitstream for the active project. |
| `get_run_status` | Check run status (synth/impl). |
| `program_device` | Program an FPGA with the given bitstream via JTAG. |
| `run_implementation` | Run implementation (place & route) on the active backend. |
| `run_simulation` | Run a simulation on the active backend. |
| `run_synthesis` | Run synthesis on the active backend. |

</details>

<details><summary><code>hardware</code> (6)</summary>

| Name | Summary |
|---|---|
| `connect_hardware_server` | Connect to hw_server. |
| `disconnect_hardware` | Disconnect from hardware. |
| `list_hardware_devices` | List devices on target. |
| `list_hardware_targets` | List JTAG targets. |
| `open_hardware_manager` | Open Hardware Manager. |
| `open_hardware_target` | Open target. |

</details>

<details><summary><code>ip</code> (3)</summary>

| Name | Summary |
|---|---|
| `create_ip` | Instantiate a vendor IP core. |
| `generate_ip` | Generate the IP's synthesis targets / output products. |
| `set_ip_property` | Set a single property on an existing IP instance. |

</details>

<details><summary><code>project</code> (14)</summary>

| Name | Summary |
|---|---|
| `add_constraint_file` | Add a single constraint file. |
| `add_constraints` | Add constraint files (.xdc/.sdc/.qsf/.fdc) to the project. |
| `add_source_file` | Add a single Verilog/VHDL/SystemVerilog source file. |
| `add_sources` | Add HDL source files to the active project. |
| `close_project` | Close the active backend's currently-open project (if any). |
| `create_project` | Create a new FPGA project on the active backend. |
| `current_project` | Return info about the currently-open project on the active backend. |
| `get_project_info` | Get project name, part, directory, top module, status. |
| `list_constraint_files` | List all constraint files. |
| `list_source_files` | List all source files in the project. |
| `open_project` | Open an existing FPGA project. |
| `remove_file` | Remove a file from the project. |
| `set_top` | Set the top-level module / entity for the active project. |
| `set_top_module` | Set the top-level module. |

</details>

<details><summary><code>reports</code> (5)</summary>

| Name | Summary |
|---|---|
| `get_synthesis_report` | Get synthesis utilization summary. |
| `report_drc` | Design Rule Check violations. |
| `report_timing` | Report timing on the active project (WNS/TNS/failing paths). |
| `report_timing_summary` | Overall timing: WNS, TNS, WHS, THS. |
| `report_utilization` | Report resource utilization on the active project. |

</details>

<details><summary><code>session</code> (5)</summary>

| Name | Summary |
|---|---|
| `exec_tcl` | Run an arbitrary backend-native Tcl command (escape hatch). |
| `list_backends` | List the EDA backends this MCP server can drive. |
| `ping_backend` | Check whether the named (or active) backend's Tcl server is reachable. |
| `set_backend` | Switch the active EDA backend (vivado/quartus/anlogic). |
| `status` | Snapshot of every backend's connection + project state. |

</details>

### Vivado (441)

<details><summary><code>block_design</code> (24)</summary>

| Name | Summary |
|---|---|
| `viv_add_bd_cell` | Add an IP cell to the BD. |
| `viv_add_bd_cell_block` | Add a block (sub-BD) cell. |
| `viv_apply_bd_automation` | Run BD automation rule. |
| `viv_close_bd` | Close the current block design. |
| `viv_connect_bd_intf_net` | Connect two BD interface nets. |
| `viv_connect_bd_net` | Connect two BD nets. |
| `viv_create_bd` | Create a block design. |
| `viv_create_bd_intf_port` | Create a BD external interface port. |
| `viv_create_bd_port` | Create a BD external port. |
| `viv_current_bd` | Return the current BD handle. |
| `viv_delete_bd_cell` | Delete a BD cell. |
| `viv_get_bd_cell_property` | Get a property on a BD cell. |
| `viv_get_bd_cells` | List all BD cells. |
| `viv_get_bd_intf_pins` | List all BD interface pins. |
| `viv_get_bd_nets` | List all BD nets. |
| `viv_get_bd_pins` | List all BD pins. |
| `viv_get_bd_ports` | List BD external ports. |
| `viv_make_wrapper` | Generate the BD HDL wrapper as the new top. |
| `viv_open_bd` | Open a block design. |
| `viv_save_bd` | Save the current block design. |
| `viv_set_bd_automation_target` | Set BD automation target. |
| `viv_set_bd_cell_config` | Set a CONFIG.* on a BD cell. |
| `viv_set_bd_cell_property` | Set a property on a BD cell. |
| `viv_validate_bd` | Validate the BD (run consistency checks). |

</details>

<details><summary><code>constraints</code> (38)</summary>

| Name | Summary |
|---|---|
| `viv_all_clocks` | Return all clocks (alias). |
| `viv_all_dsps` | Return all DSPs. |
| `viv_all_ffs` | Return all flip-flops. |
| `viv_all_inputs` | Return all input ports. |
| `viv_all_latches` | Return all latches. |
| `viv_all_outputs` | Return all output ports. |
| `viv_all_rams` | Return all RAMs. |
| `viv_all_registers` | Return all registers. |
| `viv_create_clock` | Define a primary clock. |
| `viv_create_clock_waveform` | Create a virtual clock (no source). |
| `viv_create_generated_clock` | Define a generated (derived) clock. |
| `viv_get_clocks` | List all clocks. |
| `viv_get_clocks_pattern` | List clocks matching PATTERN. |
| `viv_get_generated_clocks` | List all generated clocks. |
| `viv_get_xdc_files` | List XDC files attached to constrs_1. |
| `viv_reset_timing` | Reset all timing constraints. |
| `viv_set_case_analysis` | Apply case analysis to a pin. |
| `viv_set_clock_groups` | Declare two clock groups as asynchronous. |
| `viv_set_clock_groups_phys_exclusive` | Declare two clock groups physically exclusive. |
| `viv_set_clock_latency` | Set clock latency. |
| `viv_set_clock_uncertainty` | Set clock uncertainty (setup). |
| `viv_set_disable_timing` | Disable timing arcs on a pin. |
| `viv_set_drive` | Set external drive strength. |
| `viv_set_false_path` | Mark a clock crossing as a false path. |
| `viv_set_false_path_through` | Set a false path through a pin. |
| `viv_set_input_delay` | Set input delay (max). |
| `viv_set_input_delay_min` | Set input delay (min, hold). |
| `viv_set_load` | Set external load on a port. |
| `viv_set_max_delay` | Set max delay for a CDC path. |
| `viv_set_min_delay` | Set min delay. |
| `viv_set_multicycle_path` | Set a multicycle path (setup). |
| `viv_set_output_delay` | Set output delay (max). |
| `viv_set_output_delay_min` | Set output delay (min, hold). |
| `viv_set_property_early_order` | Mark an XDC as processed early. |
| `viv_set_property_late_order` | Mark an XDC as processed late. |
| `viv_set_property_target` | Set the constraint file target (constrs_1 only). |
| `viv_set_property_used_in_impl` | Mark an XDC as used in impl. |
| `viv_set_property_used_in_synth` | Mark an XDC as used in synth. |

</details>

<details><summary><code>debug</code> (16)</summary>

| Name | Summary |
|---|---|
| `viv_connect_debug_port` | Connect a debug port to a net. |
| `viv_create_debug_core` | Create a debug core. |
| `viv_create_ila_ip` | Create an ILA IP instance. |
| `viv_create_vio_ip` | Create a VIO IP instance. |
| `viv_disconnect_debug_port` | Disconnect a debug port. |
| `viv_get_debug_cores` | List debug cores in the design. |
| `viv_get_debug_ports` | List all debug ports. |
| `viv_implement_debug_core` | Run the debug core implementation step. |
| `viv_save_debug_core` | Save a debug core config. |
| `viv_set_capture_mode` | Set ILA capture mode (BASIC/ADVANCED). |
| `viv_set_debug_core_property` | Set a debug core property. |
| `viv_set_debug_port_property` | Set a debug port property. |
| `viv_set_debug_port_width` | Set the width of a debug port. |
| `viv_set_probe_clk` | Set input pipeline stages on a probe. |
| `viv_set_trigger_compare_value` | Set a probe trigger compare value. |
| `viv_set_trigger_position` | Set the ILA trigger position (samples before trigger). |

</details>

<details><summary><code>fileset</code> (18)</summary>

| Name | Summary |
|---|---|
| `viv_add_constraints` | Add constraint files to constrs_1. |
| `viv_add_files` | Add files to the current fileset. |
| `viv_add_files_recursive` | Add all files under a directory. |
| `viv_create_fileset` | Create a new fileset. |
| `viv_current_fileset` | Return the current fileset handle. |
| `viv_delete_fileset` | Delete a fileset. |
| `viv_get_file_property` | Get a property of a source file. |
| `viv_get_files` | List all source files in the project. |
| `viv_get_files_of_type` | List files matching a pattern in a fileset. |
| `viv_get_filesets` | List all filesets. |
| `viv_import_files` | Import (copy) files into the project. |
| `viv_make_library` | Create a new user library. |
| `viv_remove_files` | Remove files from the current fileset. |
| `viv_set_constraint_global` | Enable a constraint file globally. |
| `viv_set_constraint_used_in` | Mark a constraint file as used in synthesis. |
| `viv_set_file_property` | Set a property on a source file. |
| `viv_set_top_module` | Set the top-level module of the current fileset. |
| `viv_update_compile_order` | Recompute compile order for the current fileset. |

</details>

<details><summary><code>flash</code> (8)</summary>

| Name | Summary |
|---|---|
| `viv_add_flash_config` | Add flash memory configuration to hardware device. |
| `viv_erase_flash` | Erase the configuration flash memory. |
| `viv_generate_mcs` | Generate an MCS flash configuration file. |
| `viv_list_flash_parts` | List supported flash memory parts. |
| `viv_program_flash` | Program the configuration flash memory. |
| `viv_readback_flash` | Read back flash contents to a file. |
| `viv_set_flash_property` | Set flash programming address range. |
| `viv_verify_flash` | Verify flash contents against expected data. |

</details>

<details><summary><code>hardware</code> (28)</summary>

| Name | Summary |
|---|---|
| `viv_close_hw_manager` | Close the hardware manager. |
| `viv_close_hw_target` | Close the open JTAG target. |
| `viv_connect_hw_server` | Connect to a remote hw_server. |
| `viv_create_hw_probe` | Create a hw probe. |
| `viv_disconnect_hw_server` | Disconnect from the hw_server. |
| `viv_get_hw_device_property` | Get a property of a hardware device. |
| `viv_get_hw_devices` | List devices on the open target. |
| `viv_get_hw_ila_property` | Get an ILA property. |
| `viv_get_hw_ilas` | List ILA cores in the programmed device. |
| `viv_get_hw_probes` | List hw probes on a device. |
| `viv_get_hw_targets` | List available JTAG targets. |
| `viv_get_hw_vio_input` | Read a VIO input probe value. |
| `viv_get_hw_vios` | List VIO cores in the programmed device. |
| `viv_open_hw_manager` | Open the hardware manager. |
| `viv_open_hw_target` | Open the first available JTAG target. |
| `viv_open_hw_target_named` | Open a specific JTAG target. |
| `viv_program_hw_device` | Program the named device. |
| `viv_refresh_hw_device` | Refresh (re-read) the device state. |
| `viv_report_hw_devices` | Report all hardware devices. |
| `viv_report_hw_target` | Report the JTAG target info. |
| `viv_run_hw_ila_capture` | Force-capture an ILA immediately. |
| `viv_run_hw_ila_trigger` | Arm and run an ILA trigger. |
| `viv_set_hw_device_probes_file` | Set the probes (.ltx) file. |
| `viv_set_hw_device_program_file` | Set the bitstream file to program. |
| `viv_set_hw_ila_property` | Set an ILA property (e.g. trigger position). |
| `viv_set_hw_ila_trigger` | Set ILA trigger condition. |
| `viv_set_hw_vio_output` | Set a VIO output probe value. |
| `viv_write_hw_ila_data` | Export ILA capture data to a file. |

</details>

<details><summary><code>impl</code> (27)</summary>

| Name | Summary |
|---|---|
| `viv_close_design` | Close the currently-open design. |
| `viv_create_run` | Create a new impl run. |
| `viv_current_design` | Return the current design handle. |
| `viv_delete_run` | Delete a run. |
| `viv_get_impl_progress` | Get impl_1 progress %. |
| `viv_get_impl_status` | Get impl_1 status string. |
| `viv_get_run_property` | Get a run property. |
| `viv_get_runs` | List all runs. |
| `viv_launch_impl` | Launch impl_1. |
| `viv_launch_impl_from_step` | Launch impl_1 from STEP onward. |
| `viv_launch_impl_to_step` | Launch impl_1 stopping at STEP. |
| `viv_link_design` | Link the design's sources. |
| `viv_open_checkpoint` | Open a .dcp file. |
| `viv_open_run` | Open a synthesized/implemented run as a design. |
| `viv_phys_opt_design` | Run phys_opt (post-route optimization). |
| `viv_place_design` | Run place_design on the open design. |
| `viv_reset_impl_run` | Reset the impl_1 run. |
| `viv_route_design` | Run route_design on the open design. |
| `viv_set_impl_step_directive` | Set a directive on a specific impl step. |
| `viv_set_impl_strategy` | Set impl_1 strategy. |
| `viv_set_run_property` | Set a run property. |
| `viv_wait_on_impl` | Block until impl_1 completes. |
| `viv_write_bitstream` | Write the bitstream to a file. |
| `viv_write_bitstream_with_ltx` | Write bitstream + probe file for a partial reconfiguration cell. |
| `viv_write_checkpoint` | Save the design checkpoint (.dcp). |
| `viv_write_edif` | Write an EDIF netlist. |
| `viv_write_verilog_netlist` | Write a Verilog stub netlist. |

</details>

<details><summary><code>ip</code> (21)</summary>

| Name | Summary |
|---|---|
| `viv_create_ip` | Create an IP instance by name. |
| `viv_create_ip_repo` | Register a custom IP repo path. |
| `viv_create_ip_run` | Create an OOC IP run. |
| `viv_create_ip_versioned` | Create an IP instance pinned to a version. |
| `viv_delete_ip_run` | Delete an OOC IP run. |
| `viv_generate_ip_target` | Generate output products for an IP. |
| `viv_get_ip_cell` | Get an IP cell by name. |
| `viv_get_ip_property` | Get a CONFIG.* property on an IP. |
| `viv_get_ip_supported_props` | List supported CONFIG.* properties. |
| `viv_get_ipdefs` | List IP definitions matching PATTERN. |
| `viv_get_ips` | List all IP instances. |
| `viv_list_ip_catalog` | List the entire IP catalog. |
| `viv_lock_ip` | Lock an IP against edits. |
| `viv_report_ip` | Report all properties of an IP. |
| `viv_reset_ip_run` | Reset an IP's OOC run. |
| `viv_set_ip_properties` | Set multiple CONFIG.* properties (props is a Tcl list of key-value pairs). |
| `viv_set_ip_property` | Set a single CONFIG.* property on an IP. |
| `viv_synth_ip` | Synthesize an IP instance. |
| `viv_unlock_ip` | Unlock an IP. |
| `viv_update_ip_catalog` | Refresh the IP catalog. |
| `viv_upgrade_ip` | Upgrade an out-of-date IP. |

</details>

<details><summary><code>lint</code> (30)</summary>

| Name | Summary |
|---|---|
| `viv_lint_bus_skew` | Report bus skew analysis. |
| `viv_lint_case_analysis` | Report case analysis settings. |
| `viv_lint_cdc` | Run Clock Domain Crossing (CDC) analysis. |
| `viv_lint_clock_interaction` | Report clock domain interactions and CDC paths. |
| `viv_lint_clock_networks` | Report clock network analysis. |
| `viv_lint_clock_utilization` | Report clock resource utilization. |
| `viv_lint_config_drc` | Configure DRC rule severity. |
| `viv_lint_config_methodology` | Configure methodology check severity. |
| `viv_lint_config_timing` | Configure timing analysis severity and message limits. |
| `viv_lint_data_check` | Report data check analysis. |
| `viv_lint_design_analysis` | Report design complexity and resource analysis. |
| `viv_lint_disable_timing` | Report disabled timing paths. |
| `viv_lint_drc` | Run Design Rule Check (DRC). |
| `viv_lint_exceptions` | Report timing exceptions (false path, multicycle, etc.). |
| `viv_lint_high_fanout_nets` | Report high fanout nets. |
| `viv_lint_incremental_reuse` | Report incremental implementation reuse statistics. |
| `viv_lint_io` | Report I/O planning and constraints. |
| `viv_lint_methodology` | Run methodology checks (UltraFast design methodology). |
| `viv_lint_noise` | Run Simultaneous Switching Noise (SSN) analysis. |
| `viv_lint_power` | Report power estimation and analysis. |
| `viv_lint_primitives` | Report primitive usage in the design. |
| `viv_lint_pulse_width` | Check minimum pulse width requirements. |
| `viv_lint_qor_suggestions` | Report QoR suggestions for timing closure. |
| `viv_lint_ram_utilization` | Report RAM/BRAM utilization details. |
| `viv_lint_route_status` | Report routing status and congestion. |
| `viv_lint_slr_utilization` | Report SLR (Super Logic Region) utilization (SSI devices). |
| `viv_lint_synchronizer` | Report synchronizer usage for CDC. |
| `viv_lint_syntax` | Check HDL syntax for all source files. |
| `viv_lint_waiver_add` | Add a lint/DRC/methodology waiver. |
| `viv_lint_waiver_list` | List all active waivers. |

</details>

<details><summary><code>netlist</code> (31)</summary>

| Name | Summary |
|---|---|
| `viv_add_cells_to_pblock` | Add cells to a pblock. |
| `viv_create_pblock` | Create a pblock. |
| `viv_delete_pblock` | Delete a pblock. |
| `viv_get_bels` | List bels (placed design only). |
| `viv_get_bels_of_cell` | List bels of a placed cell. |
| `viv_get_cell_property` | Get a property of a cell. |
| `viv_get_cells` | List all cells in the open design. |
| `viv_get_cells_of_ref` | List cells of a specific ref (e.g. LUT6). |
| `viv_get_cells_pattern` | List cells matching PATTERN. |
| `viv_get_lib_cell_pins` | List lib cells of a lib. |
| `viv_get_lib_cells` | List all library cells. |
| `viv_get_libs` | List all libraries. |
| `viv_get_libs_pattern` | List libs matching PATTERN. |
| `viv_get_net_property` | Get a property of a net. |
| `viv_get_nets` | List all nets. |
| `viv_get_nets_pattern` | List nets matching PATTERN. |
| `viv_get_pblocks` | List all pblocks. |
| `viv_get_pin_property` | Get a property of a pin. |
| `viv_get_pins` | List all pins. |
| `viv_get_pins_of_cell` | List pins of a cell. |
| `viv_get_port_property` | Get a property of a port. |
| `viv_get_ports` | List all ports. |
| `viv_get_ports_pattern` | List ports matching PATTERN. |
| `viv_get_site_property` | Get a property of a site. |
| `viv_get_sites` | List all sites on the device. |
| `viv_resize_pblock` | Add sites to a pblock. |
| `viv_set_cell_property` | Set a property of a cell. |
| `viv_set_net_property` | Set a property of a net. |
| `viv_set_property_async_reg` | Mark a register as async (CDC) — important for 2-FF synchronizers. |
| `viv_set_property_dont_touch` | Prevent optimization on a cell. |
| `viv_set_property_use_dsp48` | Hint that a multiply should use DSP48. |

</details>

<details><summary><code>parts</code> (19)</summary>

| Name | Summary |
|---|---|
| `viv_get_board_part` | Get the part of a board. |
| `viv_get_board_property` | Get a property of a board. |
| `viv_get_boards` | List known board files. |
| `viv_get_boards_pattern` | List boards matching PATTERN. |
| `viv_get_families` | List FPGA families. |
| `viv_get_iobanks` | List all I/O banks on the part. |
| `viv_get_iobanks_of_port` | Get I/O bank of a port. |
| `viv_get_package_pin_property` | Get a property of a package pin. |
| `viv_get_package_pins` | Get package pins of a port. |
| `viv_get_part_packages` | Get the package pin count for a part. |
| `viv_get_part_property` | Get a property of a part. |
| `viv_get_parts` | List all available parts. |
| `viv_get_parts_pattern` | List parts matching PATTERN. |
| `viv_set_property_drive` | Set drive strength (mA). |
| `viv_set_property_io_standard` | Set IOSTANDARD for a port. |
| `viv_set_property_package_pin` | Assign a package pin to a port. |
| `viv_set_property_pulldown` | Enable pull-down resistor. |
| `viv_set_property_pullup` | Enable pull-up resistor. |
| `viv_set_property_slew` | Set slew rate. |

</details>

<details><summary><code>project</code> (19)</summary>

| Name | Summary |
|---|---|
| `viv_archive_project` | Archive the project to a .xpr.zip file. |
| `viv_close_project` | Close the current project. |
| `viv_create_project` | Create a Vivado project. |
| `viv_create_project_in_memory` | Create an in-memory project (no .xpr written). |
| `viv_current_project` | Return the current project object name. |
| `viv_export_project_user_template` | Export the project as a user template. |
| `viv_get_default_lib` | Get the default library name. |
| `viv_get_part` | Return the project's target part. |
| `viv_get_project_dir` | Return the project directory. |
| `viv_get_project_property` | Get a top-level project property. |
| `viv_get_projects` | List all open projects. |
| `viv_get_target_language` | Get the default HDL (Verilog/VHDL). |
| `viv_import_project` | Import a project from an archive or .xpr. |
| `viv_open_project` | Open an existing .xpr project. |
| `viv_save_project` | Save the project (optionally as a new path). |
| `viv_set_default_lib` | Set the default library name. |
| `viv_set_part` | Change the target part. |
| `viv_set_project_property` | Set a top-level project property. |
| `viv_set_target_language` | Set the default HDL. |

</details>

<details><summary><code>simulation</code> (21)</summary>

| Name | Summary |
|---|---|
| `viv_add_wave` | Add a signal to the wave viewer. |
| `viv_add_wave_divider` | Add a divider to the wave viewer. |
| `viv_close_simulation` | Close the simulation. |
| `viv_current_sim` | Return the current simulation handle. |
| `viv_force_signal` | Force a signal value in the simulation. |
| `viv_get_sim_property` | Get a sim_1 property. |
| `viv_get_sim_state` | Return simulation state. |
| `viv_get_value` | Get the current value of a signal. |
| `viv_get_wave_objects` | List all objects in the wave viewer. |
| `viv_launch_simulation` | Launch XSim. |
| `viv_launch_simulation_post_synth` | Launch post-synth simulation. |
| `viv_launch_simulation_timing` | Launch timing (post-impl) simulation. |
| `viv_release_signal` | Release a previously forced signal. |
| `viv_restart_simulation` | Restart the running simulation. |
| `viv_run_all_simulation` | Run the simulation to completion. |
| `viv_run_simulation` | Run the simulation for a duration. |
| `viv_set_sim_compile_order` | Recompute sim_1 compile order. |
| `viv_set_sim_property` | Set a sim_1 property. |
| `viv_set_sim_top` | Set the sim_1 fileset top. |
| `viv_set_value` | Set the value of a signal. |
| `viv_step_simulation` | Step one delta cycle. |

</details>

<details><summary><code>synth</code> (9)</summary>

| Name | Summary |
|---|---|
| `viv_get_synth_progress` | Get synth_1 progress %. |
| `viv_get_synth_status` | Get synth_1 status string. |
| `viv_launch_synth` | Launch synth_1 with N parallel jobs. |
| `viv_opt_design` | Run opt_design on the open design. |
| `viv_reset_synth_run` | Reset the synth_1 run. |
| `viv_set_synth_step` | Set synth_design directive. |
| `viv_set_synth_strategy` | Set synth_1 strategy (e.g. Vivado Synthesis Defaults). |
| `viv_synth_design` | Run synth_design directly on an in-memory design. |
| `viv_wait_on_synth` | Block until synth_1 completes. |

</details>

<details><summary><code>tcl</code> (21)</summary>

| Name | Summary |
|---|---|
| `viv_catch` | Catch an error from a Tcl command. |
| `viv_cd` | Change the working directory. |
| `viv_error_msg` | Log an ERROR message. |
| `viv_exec` | Run a system command inside the Vivado session. |
| `viv_file_exists` | Return 1 if PATH exists. |
| `viv_file_mtime` | Get the modification time of a file. |
| `viv_file_stat` | Get the size of a file. |
| `viv_get_env` | Get an environment variable. |
| `viv_get_user_id` | Return the current user name. |
| `viv_get_var` | Get a Tcl variable's value. |
| `viv_get_vivado_install_dir` | Return the Vivado install directory. |
| `viv_get_vivado_version` | Return the Vivado version string. |
| `viv_info` | Log an INFO message. |
| `viv_list_dir` | List files in a directory. |
| `viv_puts` | Print a message to the Vivado console. |
| `viv_puts_log` | Append a message to a log file. |
| `viv_pwd` | Return the current working directory. |
| `viv_set_env` | Set an environment variable. |
| `viv_set_var` | Set a Tcl variable in the session. |
| `viv_source_tcl` | Source a Tcl file inside the Vivado session. |
| `viv_warning` | Log a WARNING message. |

</details>

<details><summary><code>timing_reports</code> (30)</summary>

| Name | Summary |
|---|---|
| `viv_get_path_property` | Get a property on the i-th timing path. |
| `viv_get_timing_paths` | Return failing timing paths as objects. |
| `viv_get_tns` | Get TNS as a float. |
| `viv_get_wns` | Get WNS as a float. |
| `viv_report_bus_skew` | Report bus skew. |
| `viv_report_cdc` | Report CDC violations. |
| `viv_report_clock_groups` | Report clock groups. |
| `viv_report_clock_interaction` | Report clock-domain interactions. |
| `viv_report_clock_jitter` | Report clock jitter. |
| `viv_report_clock_latency` | Report clock latency. |
| `viv_report_clock_propagation` | Report clock propagation tree. |
| `viv_report_clock_routing` | Report clock routing resources. |
| `viv_report_clock_transfers` | Report clock-to-clock transfers. |
| `viv_report_clocks` | Report all clocks in the design. |
| `viv_report_design_analysis` | Report design analysis (congestion, depth). |
| `viv_report_environment` | Report the environment (versions, etc.). |
| `viv_report_exceptions` | Report timing exceptions (false paths etc.). |
| `viv_report_floorplan` | Report floorplanning. |
| `viv_report_hierarchy` | Report the design hierarchy. |
| `viv_report_high_fanout_nets` | Report high-fanout nets. |
| `viv_report_methodology` | Report methodology checks. |
| `viv_report_path_delay` | Report delay between two specific pins. |
| `viv_report_pipeline_analysis` | Report pipeline stages in the design. |
| `viv_report_powerup` | Report power-up state of registers. |
| `viv_report_property` | Report all properties of a cell. |
| `viv_report_qor_suggestions` | Report QoR optimization suggestions. |
| `viv_report_route_status` | Report routing status (routed/unrouted). |
| `viv_report_timing` | Report failing timing paths. |
| `viv_report_timing_max_paths` | Report top-N paths sorted by group. |
| `viv_report_timing_summary` | Report timing summary (WNS/TNS). |

</details>

<details><summary><code>utilization_reports</code> (21)</summary>

| Name | Summary |
|---|---|
| `viv_get_clocks_summary` | Concise clock summary. |
| `viv_get_project_summary` | Report project summary. |
| `viv_report_clock_utilization` | Report clock-related resources. |
| `viv_report_compile_order` | Report file compile order. |
| `viv_report_drc` | Run design rule checks. |
| `viv_report_drc_specific` | Run specific DRC checks. |
| `viv_report_env` | Report Vivado environment (versions, install path). |
| `viv_report_exceptions_summary` | Summarize timing exceptions. |
| `viv_report_failfast` | Run fail-fast design checks. |
| `viv_report_io` | Report I/O pin assignments. |
| `viv_report_methodology_violations` | Report methodology violations only. |
| `viv_report_pin_costs` | Report pin cost. |
| `viv_report_power` | Report power consumption. |
| `viv_report_power_verbose` | Report power in detail. |
| `viv_report_ram_widgets` | Report RAM widget usage. |
| `viv_report_route_status_verbose` | Detailed routing status. |
| `viv_report_utilization` | Report device utilization. |
| `viv_report_utilization_bram` | Report BRAM utilization only. |
| `viv_report_utilization_dsp` | Report DSP utilization only. |
| `viv_report_utilization_hierarchical` | Report utilization by hierarchy. |
| `viv_report_utilization_slr` | Report utilization per SLR (SSIT only). |

</details>

<details><summary><code>xsct</code> (60)</summary>

| Name | Summary |
|---|---|
| `viv_xsct_backtrace` | Show call stack backtrace. |
| `viv_xsct_build_app` | Build the application project. |
| `viv_xsct_build_platform` | Build the platform project. |
| `viv_xsct_clean_app` | Clean the application project. |
| `viv_xsct_clean_platform` | Clean the platform project. |
| `viv_xsct_close_serial` | Close the JTAG UART terminal. |
| `viv_xsct_create_app` | Create an application project. |
| `viv_xsct_create_bsp` | Create a Board Support Package. |
| `viv_xsct_create_platform` | Create a platform project from hardware definition. |
| `viv_xsct_create_workspace` | Create a new XSCT workspace. |
| `viv_xsct_download_bitstream` | Download bitstream to FPGA via JTAG. |
| `viv_xsct_download_elf` | Download ELF file to target processor. |
| `viv_xsct_exec` | Execute a shell command from XSCT. |
| `viv_xsct_finish` | Step out of current function. |
| `viv_xsct_get_app_config` | Get application build configuration. |
| `viv_xsct_get_global` | Print value of a global/static variable. |
| `viv_xsct_get_locals` | List local variables in current scope. |
| `viv_xsct_get_platform_info` | Get platform project information. |
| `viv_xsct_get_register` | Read a specific register. |
| `viv_xsct_get_registers` | Read all processor registers. |
| `viv_xsct_get_target_info` | Get target information. |
| `viv_xsct_get_workspace` | Get the current XSCT workspace. |
| `viv_xsct_help` | Get help on an XSCT command. |
| `viv_xsct_hsi_close` | Close the current HSI hardware design. |
| `viv_xsct_hsi_generate_drivers` | Generate software drivers. |
| `viv_xsct_hsi_generate_libs` | Generate software libraries. |
| `viv_xsct_hsi_get_addr_map` | Get address map for a processor. |
| `viv_xsct_hsi_get_cpus` | List all processors in the design. |
| `viv_xsct_hsi_get_ip_config` | Get IP configuration parameter. |
| `viv_xsct_hsi_get_memory` | List all memory instances in the design. |
| `viv_xsct_hsi_get_peripherals` | List all peripherals in the design. |
| `viv_xsct_hsi_open_hw` | Open hardware design for HSI queries. |
| `viv_xsct_jtag_drscan` | Perform JTAG DR scan. |
| `viv_xsct_jtag_irscan` | Perform JTAG IR scan. |
| `viv_xsct_jtag_sequence` | Execute a JTAG sequence. |
| `viv_xsct_list_apps` | List all application projects. |
| `viv_xsct_list_breakpoints` | List all breakpoints. |
| `viv_xsct_list_platforms` | List all platform projects. |
| `viv_xsct_list_targets` | List all JTAG targets. |
| `viv_xsct_next` | Step over (next line). |
| `viv_xsct_open_serial` | Open a JTAG UART terminal. |
| `viv_xsct_read_memory` | Read memory at address. |
| `viv_xsct_read_serial` | Read bytes from JTAG UART. |
| `viv_xsct_regen_bsp` | Regenerate the BSP sources. |
| `viv_xsct_remove_breakpoint` | Remove a breakpoint by ID. |
| `viv_xsct_reset_processor` | Reset the target processor. |
| `viv_xsct_reset_system` | Reset the entire system (processor + peripherals). |
| `viv_xsct_run_elf` | Continue execution (run the downloaded ELF). |
| `viv_xsct_select_target` | Select a JTAG target by ID. |
| `viv_xsct_set_app_config` | Set application build configuration. |
| `viv_xsct_set_breakpoint` | Set a breakpoint at a function. |
| `viv_xsct_set_breakpoint_line` | Set a breakpoint at a specific line. |
| `viv_xsct_set_bsp_config` | Set a BSP configuration option. |
| `viv_xsct_set_register` | Write a value to a register. |
| `viv_xsct_set_workspace` | Set the XSCT workspace directory. |
| `viv_xsct_step` | Step into (single step). |
| `viv_xsct_stop_elf` | Stop processor execution. |
| `viv_xsct_version` | Get XSCT version. |
| `viv_xsct_write_memory` | Write value to memory address. |
| `viv_xsct_write_serial` | Write bytes to JTAG UART. |

</details>

### Quartus (167)

<details><summary><code>constraints</code> (19)</summary>

| Name | Summary |
|---|---|
| `q_all_clocks` | Return all clocks. |
| `q_all_inputs` | Return all input ports. |
| `q_all_outputs` | Return all output ports. |
| `q_all_registers` | Return all registers. |
| `q_create_clock` | Create a primary clock (SDC). |
| `q_create_generated_clock` | Create a generated clock. |
| `q_get_clocks` | List all clocks. |
| `q_get_clocks_pattern` | List clocks matching PATTERN. |
| `q_set_clock_groups` | Set clock groups as async. |
| `q_set_clock_groups_exclusive` | Set clock groups as exclusive. |
| `q_set_clock_latency` | Set clock latency. |
| `q_set_clock_uncertainty` | Set clock uncertainty. |
| `q_set_disable_timing` | Disable timing arcs between two pins. |
| `q_set_false_path` | Set a false path between clocks. |
| `q_set_input_delay` | Set input delay (max). |
| `q_set_max_delay` | Set max delay. |
| `q_set_min_delay` | Set min delay. |
| `q_set_multicycle_path` | Set a multicycle path. |
| `q_set_output_delay` | Set output delay (max). |

</details>

<details><summary><code>fileset</code> (20)</summary>

| Name | Summary |
|---|---|
| `q_get_all_assignments` | Return every global assignment (verbose). |
| `q_get_instance_assignment` | Get a per-instance assignment. |
| `q_get_pin_location` | Get the pin location of a port. |
| `q_remove_assignment` | Remove a global assignment. |
| `q_remove_instance_assignment` | Remove a per-instance assignment. |
| `q_set_current_strength` | Set drive current (mA). |
| `q_set_global_clock` | Promote a signal to a global clock. |
| `q_set_instance_assignment` | Set a per-instance assignment. |
| `q_set_io_standard` | Set IOSTANDARD of a port. |
| `q_set_pin_location` | Assign a pin to a port. |
| `q_set_qsf_file` | Add a QSF include file. |
| `q_set_sdc_file` | Add an SDC constraint file. |
| `q_set_search_path` | Add a Verilog include search path. |
| `q_set_slew_rate` | Set fast slew on a port. |
| `q_set_systemverilog_file` | Add a SystemVerilog file. |
| `q_set_verilog_file` | Add a Verilog file. |
| `q_set_verilog_version` | Set Verilog version (e.g. Verilog-2001). |
| `q_set_vhdl_file` | Add a VHDL file. |
| `q_set_vhdl_version` | Set VHDL version (e.g. VHDL-2008). |
| `q_set_weak_pullup` | Enable weak pull-up on a port. |

</details>

<details><summary><code>flow</code> (21)</summary>

| Name | Summary |
|---|---|
| `q_add_device_pgm` | Add a device to the programmer. |
| `q_begin_execution` | Begin a programmer execution session. |
| `q_create_progress` | Create a progress tracker. |
| `q_end_execution` | End a programmer execution session. |
| `q_execute_all_flows` | Run full compile (map+fit+asm+sta). |
| `q_execute_asm` | Run Assembler (bitstream generation). |
| `q_execute_eda` | Run EDA Netlist Writer. |
| `q_execute_fit` | Run Fitter (place & route). |
| `q_execute_flow_from` | Run compile from a stage onward. |
| `q_execute_flow_to` | Run compile up to a stage. |
| `q_execute_map` | Run Analysis & Synthesis. |
| `q_execute_pow` | Run Power Analyzer. |
| `q_execute_sta` | Run Static Timing Analyzer. |
| `q_load_package_programmer` | Load the programmer package. |
| `q_program_device_pgm` | Program the configured device. |
| `q_run_quartus_asm` | Run quartus_asm directly. |
| `q_run_quartus_fit` | Run quartus_fit directly. |
| `q_run_quartus_map` | Run quartus_map directly (alternative to execute_module). |
| `q_run_quartus_pgm` | Program a .sof via JTAG using quartus_pgm. |
| `q_run_quartus_sta` | Run quartus_sta directly. |
| `q_set_progress` | Update progress (scripted flow only). |

</details>

<details><summary><code>ip</code> (19)</summary>

| Name | Summary |
|---|---|
| `q_qsys_add_component` | Add a component to the Qsys file. |
| `q_qsys_close` | Close the current Qsys file. |
| `q_qsys_connect` | Connect two Qsys pins. |
| `q_qsys_create` | Create a Qsys IP file. |
| `q_qsys_create_clock` | Set Qsys clock source. |
| `q_qsys_create_reset` | Set Qsys reset source. |
| `q_qsys_disconnect` | Disconnect two Qsys pins. |
| `q_qsys_export` | Export a Qsys file to another format. |
| `q_qsys_generate` | Generate Qsys output products. |
| `q_qsys_get_parameter` | Get a component parameter. |
| `q_qsys_list_components` | List all Qsys components. |
| `q_qsys_list_connections` | List all Qsys connections. |
| `q_qsys_load_library` | Load an additional Qsys library. |
| `q_qsys_open` | Open an existing Qsys file. |
| `q_qsys_remove_component` | Remove a component. |
| `q_qsys_remove_library` | Remove a Qsys library. |
| `q_qsys_save` | Save the current Qsys file. |
| `q_qsys_set_parameter` | Set a component parameter. |
| `q_qsys_validate` | Validate the current Qsys file. |

</details>

<details><summary><code>project</code> (16)</summary>

| Name | Summary |
|---|---|
| `q_create_revision` | Create a new revision. |
| `q_delete_revision` | Delete a revision. |
| `q_get_current_revision` | Return the current revision name. |
| `q_get_family` | Return the project's FAMILY. |
| `q_get_part` | Return the project's DEVICE. |
| `q_get_revisions` | List all revisions in the project. |
| `q_get_top_entity` | Return the top entity. |
| `q_is_project_open` | Return 1 if a project is currently open. |
| `q_project_close` | Close the current project. |
| `q_project_exists` | Return 1 if the project file exists. |
| `q_project_new` | Create a new Quartus project. |
| `q_project_open` | Open an existing Quartus project by revision name. |
| `q_set_current_revision` | Switch to a different revision. |
| `q_set_family` | Set the FAMILY assignment. |
| `q_set_part` | Set the DEVICE assignment. |
| `q_set_top_entity` | Set the top entity. |

</details>

<details><summary><code>timing_reports</code> (18)</summary>

| Name | Summary |
|---|---|
| `q_create_timing_netlist` | Build the STA timing netlist. |
| `q_get_failing_paths` | Get failing paths as objects. |
| `q_get_hold_paths` | Get hold paths. |
| `q_get_max_delay` | Get max delay between two pins. |
| `q_get_min_delay` | Get min delay between two pins. |
| `q_get_setup_paths` | Get setup paths. |
| `q_read_sdc` | Read the project's SDC into the STA netlist. |
| `q_report_clock_relationships` | Report clock relationships. |
| `q_report_clock_transfers` | Report clock-to-clock transfers. |
| `q_report_metastability` | Report metastability analysis. |
| `q_report_path` | Report a single path. |
| `q_report_recovery` | Report recovery timing. |
| `q_report_removal` | Report removal timing. |
| `q_report_timing` | Report top-N paths. |
| `q_report_timing_from_to` | Report timing between two pins. |
| `q_report_timing_summary` | Report timing summary. |
| `q_report_unconstrained_paths` | Report unconstrained / failing paths only. |
| `q_update_timing_netlist` | Update the STA timing netlist. |

</details>

<details><summary><code>utilization_reports</code> (54)</summary>

| Name | Summary |
|---|---|
| `q_get_board` | Get board file. |
| `q_get_option` | Get a Quartus option. |
| `q_report_area` | Report area. |
| `q_report_assignments` | Report all assignments. |
| `q_report_board` | Report board assignments. |
| `q_report_chip` | Report chip summary. |
| `q_report_clock_failures` | Report clock failures. |
| `q_report_database` | Report database files. |
| `q_report_database_files` | Report DB files. |
| `q_report_drc` | Run DRC. |
| `q_report_drc_specific` | Run a specific DRC check. |
| `q_report_dsp` | Report DSP usage. |
| `q_report_false_path_failures` | Report false path failures. |
| `q_report_fmax` | Report Fmax per clock. |
| `q_report_hold_failures` | Report hold failures. |
| `q_report_io` | Report I/O assignments. |
| `q_report_license` | Report license status. |
| `q_report_logic_option` | Report logic options. |
| `q_report_multicycle_failures` | Report multicycle failures. |
| `q_report_netlist` | Report netlist info. |
| `q_report_param` | Report a Quartus parameter. |
| `q_report_partitions` | Report partition assignments. |
| `q_report_path_summary` | Report paths summary. |
| `q_report_power` | Report power. |
| `q_report_ram` | Report RAM usage. |
| `q_report_recovery_failures` | Report recovery failures. |
| `q_report_removal_failures` | Report removal failures. |
| `q_report_resource` | Report resource utilization. |
| `q_report_setup_failures` | Report setup failures. |
| `q_run_quartus_cdb` | Run a custom Tcl script via quartus_cdb. |
| `q_set_board_part` | Set board file. |
| `q_set_default_switching_activity` | Set default input toggle rate. |
| `q_set_dsp_block_balanced` | Set DSP balancing mode. |
| `q_set_fitter_effort` | Set fitter effort (Standard, Auto Fit, Fast). |
| `q_set_global_assignment_dont_touch` | Disable auto-carry on a register. |
| `q_set_incremental_compile` | Enable incremental compilation. |
| `q_set_op_cond` | Set thermal model. |
| `q_set_optimization_technique` | Set optimization technique (Area, Speed, Balanced). |
| `q_set_option` | Set a Quartus option (e.g. OPTIMIZATION_TECHNIQUE). |
| `q_set_power_analysis_mode` | Set cooling solution preset. |
| `q_set_revision_part` | Set device family for revision. |
| `q_set_router_effort` | Set router effort (0-10). |
| `q_set_signal_probe` | Enable SignalProbe. |
| `q_set_sim_output_dir` | Set EDA output directory. |
| `q_set_sim_tool` | Set simulation tool (ModelSim/Questa). |
| `q_set_sim_tool_args` | Set custom EDA tool command. |
| `q_set_smart_compile` | Enable smart recompile. |
| `q_set_speed_grade` | Set device speed grade. |
| `q_set_temp_grade` | Set device temperature grade. |
| `q_set_testbench_file` | Set testbench resource file. |
| `q_set_testbench_name` | Set testbench name. |
| `q_set_testbench_top` | Set testbench top module. |
| `q_set_timing_driven` | Enable max-effort timing-driven routing. |
| `q_set_vccint` | Set VCCINT voltage. |

</details>

### Anlogic (157)

<details><summary><code>constraints</code> (20)</summary>

| Name | Summary |
|---|---|
| `a_all_inputs` | Return all input ports. |
| `a_all_outputs` | Return all output ports. |
| `a_all_registers` | Return all registers. |
| `a_create_clock` | Define a primary clock. |
| `a_create_generated_clock` | Define a generated clock. |
| `a_get_clocks` | List all clocks. |
| `a_get_clocks_pattern` | List clocks matching a pattern. |
| `a_set_async_reg` | Mark a register as async (CDC). |
| `a_set_case_analysis` | Apply case analysis to a pin. |
| `a_set_clock_groups` | Declare two clock groups as async. |
| `a_set_clock_latency` | Set clock latency. |
| `a_set_clock_uncertainty` | Set clock uncertainty. |
| `a_set_disable_timing` | Disable timing arcs on a pin. |
| `a_set_dont_touch` | Prevent optimization on a cell. |
| `a_set_false_path` | Set a false path. |
| `a_set_input_delay` | Set input delay (max). |
| `a_set_max_delay` | Set max delay. |
| `a_set_min_delay` | Set min delay. |
| `a_set_multicycle_path` | Set a multicycle path. |
| `a_set_output_delay` | Set output delay (max). |

</details>

<details><summary><code>fileset</code> (14)</summary>

| Name | Summary |
|---|---|
| `a_add_constraint` | Add an .sdc / .fdc constraint file. |
| `a_add_file` | Add a source file to the project. |
| `a_add_include_dir` | Add a Verilog include directory. |
| `a_create_lib` | Create a user library. |
| `a_delete_lib` | Delete a user library. |
| `a_export_files` | Export project files to a directory. |
| `a_get_constraints` | List all constraint files. |
| `a_get_file_property` | Get a per-file property. |
| `a_get_files` | List all source files. |
| `a_import_files` | Import (copy) files into the project. |
| `a_list_libs` | List all libraries. |
| `a_remove_file` | Remove a source file. |
| `a_set_file_property` | Set a per-file property. |
| `a_set_lib` | Assign a source file to a library. |

</details>

<details><summary><code>hardware</code> (8)</summary>

| Name | Summary |
|---|---|
| `a_close_hw_manager` | Close the hardware manager. |
| `a_close_hw_target` | Close the open JTAG target. |
| `a_get_hw_devices` | List devices on the open target. |
| `a_get_hw_targets` | List JTAG targets. |
| `a_open_hw_manager` | Open the hardware manager. |
| `a_open_hw_target` | Open the first available JTAG target. |
| `a_program_device` | Program an FPGA via JTAG. |
| `a_refresh_hw_device` | Refresh a device's state. |

</details>

<details><summary><code>impl</code> (20)</summary>

| Name | Summary |
|---|---|
| `a_close_design` | Close the current design. |
| `a_current_design` | Return the current design handle. |
| `a_enable_post_place_phys_opt` | Enable post-place phys_opt. |
| `a_enable_post_route_phys_opt` | Enable post-route phys_opt. |
| `a_generate_bitstream` | Generate the bitstream. |
| `a_get_pnr_progress` | Get impl run progress %. |
| `a_get_pnr_status` | Get impl run status. |
| `a_open_checkpoint` | Open a saved checkpoint. |
| `a_open_run` | Open a run as a design. |
| `a_reset_pnr` | Reset the impl run. |
| `a_run_pnr` | Run place & route (includes bitstream on older TD). |
| `a_save_checkpoint` | Save design checkpoint. |
| `a_set_max_bram` | Set max BRAM count. |
| `a_set_max_dsp` | Set max DSP count. |
| `a_set_max_luts` | Set max LUT count. |
| `a_set_placer_seed` | Set placer seed. |
| `a_set_pnr_effort` | Set P&R effort level. |
| `a_set_pnr_strategy` | Set impl strategy. |
| `a_set_router_seed` | Set router seed. |
| `a_stop_pnr` | Stop the impl run. |

</details>

<details><summary><code>ip</code> (12)</summary>

| Name | Summary |
|---|---|
| `a_create_ip` | Create an IP instance. |
| `a_generate_ip` | Generate IP output products. |
| `a_get_ip_defs` | List IP definitions matching a pattern. |
| `a_get_ip_property` | Get an IP property. |
| `a_get_ips` | List all IP instances. |
| `a_list_ip_catalog` | List all available IPs. |
| `a_lock_ip` | Lock an IP against edits. |
| `a_set_ip_property` | Set an IP property. |
| `a_set_ip_repo` | Register a custom IP repo path. |
| `a_unlock_ip` | Unlock an IP. |
| `a_update_ip_catalog` | Refresh the IP catalog. |
| `a_upgrade_ip` | Upgrade an out-of-date IP. |

</details>

<details><summary><code>netlist</code> (17)</summary>

| Name | Summary |
|---|---|
| `a_add_cells_to_pblock` | Add cells to a pblock. |
| `a_create_pblock` | Create a pblock. |
| `a_delete_pblock` | Delete a pblock. |
| `a_get_cell_property` | Get a property of a cell. |
| `a_get_cells` | List all cells. |
| `a_get_cells_pattern` | List cells matching PATTERN. |
| `a_get_net_property` | Get a property of a net. |
| `a_get_nets` | List all nets. |
| `a_get_nets_pattern` | List nets matching PATTERN. |
| `a_get_pblocks` | List all pblocks. |
| `a_get_pin_property` | Get a property of a pin. |
| `a_get_pins` | List all pins. |
| `a_get_pins_of_cell` | List pins of a cell. |
| `a_get_port_property` | Get a property of a port. |
| `a_get_ports` | List all ports. |
| `a_get_ports_pattern` | List ports matching PATTERN. |
| `a_set_cell_property` | Set a property of a cell. |

</details>

<details><summary><code>project</code> (13)</summary>

| Name | Summary |
|---|---|
| `a_close_project` | Close the current project. |
| `a_create_project` | Create an Anlogic project. |
| `a_current_project` | Return the current project handle. |
| `a_get_hdl` | Return the HDL family. |
| `a_get_part` | Return the project's target part. |
| `a_get_project_dir` | Return the project directory. |
| `a_get_top` | Return the project top. |
| `a_open_project` | Open an existing .al project. |
| `a_save_project` | Save the current project. |
| `a_save_project_as` | Save the project to a new path. |
| `a_set_hdl` | Set the HDL family. |
| `a_set_part` | Change the target part. |
| `a_set_top` | Set the project top module. |

</details>

<details><summary><code>simulation</code> (4)</summary>

| Name | Summary |
|---|---|
| `a_close_simulation` | Close the simulation. |
| `a_export_simulation` | Export simulation netlist for an external simulator. |
| `a_run_simulation` | Launch the simulator. |
| `a_set_simulation_top` | Set sim_1 top module. |

</details>

<details><summary><code>synth</code> (14)</summary>

| Name | Summary |
|---|---|
| `a_disable_pipelining` | Disable pipelining. |
| `a_enable_dsp_balancing` | Enable DSP balancing. |
| `a_enable_fsm_extract` | Enable FSM extraction. |
| `a_enable_pipelining` | Enable pipelining. |
| `a_enable_ram_balancing` | Enable RAM balancing. |
| `a_get_syn_progress` | Get synth run progress %. |
| `a_get_syn_status` | Get synth run status. |
| `a_reset_syn` | Reset the synth run. |
| `a_run_syn` | Run synthesis. |
| `a_set_optimization` | Set optimization mode (area/speed/balanced). |
| `a_set_resource_sharing` | Set resource sharing level. |
| `a_set_syn_effort` | Set synth effort level. |
| `a_set_syn_strategy` | Set synth strategy. |
| `a_stop_syn` | Stop the synth run. |

</details>

<details><summary><code>tcl</code> (15)</summary>

| Name | Summary |
|---|---|
| `a_catch` | Catch a Tcl error. |
| `a_cd` | Change working directory. |
| `a_exec` | Run a system command. |
| `a_file_exists` | Check if a path exists. |
| `a_get_td_version` | Return TD version string. |
| `a_get_user` | Return the current user. |
| `a_get_var` | Get a Tcl variable. |
| `a_list_dir` | List files in a directory. |
| `a_log_error` | Log ERROR message. |
| `a_log_info` | Log INFO message. |
| `a_log_warning` | Log WARNING message. |
| `a_puts` | Print a message to the TD console. |
| `a_pwd` | Return the current working directory. |
| `a_set_var` | Set a Tcl variable. |
| `a_source` | Source a Tcl file. |

</details>

<details><summary><code>timing_reports</code> (11)</summary>

| Name | Summary |
|---|---|
| `a_report_cdc` | Report CDC violations. |
| `a_report_clock_groups` | Report clock groups. |
| `a_report_clock_routing` | Report clock routing resources. |
| `a_report_clock_transfers` | Report clock-to-clock transfers. |
| `a_report_clocks` | Report all clocks. |
| `a_report_exceptions` | Report timing exceptions. |
| `a_report_high_fanout` | Report high-fanout nets. |
| `a_report_qor_suggestions` | Report QoR optimization suggestions. |
| `a_report_route_status` | Report routing status. |
| `a_report_timing` | Report timing paths. |
| `a_report_timing_summary` | Report timing summary. |

</details>

<details><summary><code>utilization_reports</code> (9)</summary>

| Name | Summary |
|---|---|
| `a_report_design_analysis` | Report design analysis. |
| `a_report_drc` | Run design rule checks. |
| `a_report_floorplan` | Report floorplanning. |
| `a_report_hierarchy` | Report design hierarchy. |
| `a_report_io` | Report I/O assignments. |
| `a_report_methodology` | Report methodology checks. |
| `a_report_pin_costs` | Report pin cost. |
| `a_report_power` | Report power. |
| `a_report_utilization` | Report resource utilization. |

</details>

<!-- END TOOL INDEX -->
