"""Vendor-agnostic tool catalogue.

These tools are available regardless of which backend is active. They cover
session lifecycle, project high-level verbs and the universal ``exec_tcl``
escape hatch. Backend-specific catalogues live in ``vivado.py``, ``quartus.py``,
``anlogic.py``.

Each spec wires up a Python ``handler`` from :mod:`fpga_mcp.tool_defs._handlers`
that calls the active backend's typed Python API (not raw Tcl). This preserves
the behaviour of the old ``fpga_mcp/tools/`` directory while letting the rest
of the catalogue (~667 vendor-specific tools) stay as pure Tcl templates.
"""

from __future__ import annotations

from fpga_mcp.tool_defs import ArgSpec, ToolSpec
from fpga_mcp.tool_defs import _handlers as h

SPECS: list[ToolSpec] = [
    # --- session -----------------------------------------------------
    ToolSpec(
        name="list_backends",
        tcl_template="",
        summary="List the EDA backends this MCP server can drive.",
        category="session",
        vendor="common",
        notes="No arguments. The active backend is marked.",
        handler=h.list_backends,
    ),
    ToolSpec(
        name="set_backend",
        tcl_template="",
        summary="Switch the active EDA backend (vivado/quartus/anlogic).",
        category="session",
        vendor="common",
        args=[ArgSpec("name", "One of vivado/quartus/anlogic.")],
        notes="Persists for the rest of the session.",
        handler=h.set_backend,
    ),
    ToolSpec(
        name="ping_backend",
        tcl_template="",
        summary="Check whether the named (or active) backend's Tcl server is reachable.",
        category="session",
        vendor="common",
        args=[ArgSpec("name", "Backend name. Empty = active.", required=False, default="")],
        handler=h.ping_backend,
    ),
    ToolSpec(
        name="status",
        tcl_template="",
        summary="Snapshot of every backend's connection + project state.",
        category="session",
        vendor="common",
        handler=h.status,
    ),
    ToolSpec(
        name="exec_tcl",
        tcl_template="{command}",
        summary="Run an arbitrary backend-native Tcl command (escape hatch).",
        category="session",
        vendor="common",
        args=[
            ArgSpec("command", "The Tcl code to evaluate."),
            ArgSpec(
                "timeout",
                "Seconds before abort (default 600).",
                required=False,
                default=600.0,
                type_hint=float,
            ),
        ],
        notes="Returns the raw Tcl output. Anything missing from the typed "
        "surface can be done via raw Tcl.",
        handler=h.exec_tcl,
    ),
    # --- project lifecycle (high-level, routed to the active backend) -
    ToolSpec(
        name="create_project",
        tcl_template="",
        summary="Create a new FPGA project on the active backend.",
        category="project",
        vendor="common",
        args=[
            ArgSpec("name", "Project name."),
            ArgSpec("part", "Vendor part number, e.g. xc7a35tcpg236-1."),
            ArgSpec("directory", "Where to create the project.", required=False, default="."),
            ArgSpec("top", "Optional top-level module.", required=False, default=""),
            ArgSpec("hdl", "verilog or vhdl.", required=False, default="verilog"),
        ],
        handler=h.create_project,
    ),
    ToolSpec(
        name="open_project",
        tcl_template="",
        summary="Open an existing FPGA project.",
        category="project",
        vendor="common",
        args=[ArgSpec("path", "Path to .xpr/.qpf/.al file.")],
        handler=h.open_project,
    ),
    ToolSpec(
        name="close_project",
        tcl_template="",
        summary="Close the active backend's currently-open project (if any).",
        category="project",
        vendor="common",
        handler=h.close_project,
    ),
    ToolSpec(
        name="current_project",
        tcl_template="",
        summary="Return info about the currently-open project on the active backend.",
        category="project",
        vendor="common",
        handler=h.current_project,
    ),
    ToolSpec(
        name="add_sources",
        tcl_template="",
        summary="Add HDL source files to the active project.",
        category="project",
        vendor="common",
        args=[
            ArgSpec("files", "List of file paths."),
            ArgSpec("library", "Optional target library.", required=False, default=""),
            ArgSpec("include_dirs", "Optional Verilog include dirs.", required=False, default=None),
        ],
        handler=h.add_sources,
    ),
    ToolSpec(
        name="add_constraints",
        tcl_template="",
        summary="Add constraint files (.xdc/.sdc/.qsf/.fdc) to the project.",
        category="project",
        vendor="common",
        args=[ArgSpec("files", "List of constraint file paths.")],
        handler=h.add_constraints,
    ),
    ToolSpec(
        name="set_top",
        tcl_template="",
        summary="Set the top-level module / entity for the active project.",
        category="project",
        vendor="common",
        args=[ArgSpec("top", "Top module name.")],
        handler=h.set_top,
    ),
    # --- flow --------------------------------------------------------
    ToolSpec(
        name="run_synthesis",
        tcl_template="",
        summary="Run synthesis on the active backend.",
        category="flow",
        vendor="common",
        args=[
            ArgSpec("force", "Reset before launch.", required=False, default=False, type_hint=bool)
        ],
        handler=h.run_synthesis,
    ),
    ToolSpec(
        name="run_implementation",
        tcl_template="",
        summary="Run implementation (place & route) on the active backend.",
        category="flow",
        vendor="common",
        args=[
            ArgSpec("force", "Reset before launch.", required=False, default=False, type_hint=bool)
        ],
        handler=h.run_implementation,
    ),
    ToolSpec(
        name="run_simulation",
        tcl_template="",
        summary="Run a simulation on the active backend.",
        category="flow",
        vendor="common",
        args=[
            ArgSpec("top", "Testbench top.", required=False, default=""),
            ArgSpec("kind", "rtl/post_syn/post_impl.", required=False, default="rtl"),
            ArgSpec("duration", "Sim duration, e.g. 1000ns.", required=False, default=""),
        ],
        handler=h.run_simulation,
    ),
    ToolSpec(
        name="generate_bitstream",
        tcl_template="",
        summary="Generate the bitstream for the active project.",
        category="flow",
        vendor="common",
        args=[
            ArgSpec(
                "include_ltx", "Include probes file.", required=False, default=True, type_hint=bool
            )
        ],
        handler=h.generate_bitstream,
    ),
    ToolSpec(
        name="program_device",
        tcl_template="",
        summary="Program an FPGA with the given bitstream via JTAG.",
        category="flow",
        vendor="common",
        args=[
            ArgSpec("bitstream", "Path to .bit/.sof file."),
            ArgSpec("cable", "Optional cable name.", required=False, default=""),
            ArgSpec(
                "device_index", "Zero-based device index.", required=False, default=0, type_hint=int
            ),
        ],
        handler=h.program_device,
    ),
    ToolSpec(
        name="report_timing",
        tcl_template="",
        summary="Report timing on the active project (WNS/TNS/failing paths).",
        category="reports",
        vendor="common",
        args=[
            ArgSpec(
                "max_paths", "Max failing paths to show.", required=False, default=10, type_hint=int
            )
        ],
        handler=h.report_timing,
    ),
    ToolSpec(
        name="report_utilization",
        tcl_template="",
        summary="Report resource utilization on the active project.",
        category="reports",
        vendor="common",
        handler=h.report_utilization,
    ),
    # --- IP (high-level) ---------------------------------------------
    ToolSpec(
        name="create_ip",
        tcl_template="",
        summary="Instantiate a vendor IP core.",
        category="ip",
        vendor="common",
        args=[
            ArgSpec("ip_name", "IP catalog name."),
            ArgSpec("name", "Optional instance name.", required=False, default=""),
            ArgSpec(
                "properties", "Optional dict of CONFIG.* properties.", required=False, default=None
            ),
        ],
        handler=h.create_ip,
    ),
    ToolSpec(
        name="set_ip_property",
        tcl_template="",
        summary="Set a single property on an existing IP instance.",
        category="ip",
        vendor="common",
        args=[
            ArgSpec("ip_name", "IP instance name."),
            ArgSpec("property_name", "Property key."),
            ArgSpec("value", "Property value."),
        ],
        handler=h.set_ip_property,
    ),
    ToolSpec(
        name="generate_ip",
        tcl_template="",
        summary="Generate the IP's synthesis targets / output products.",
        category="ip",
        vendor="common",
        args=[ArgSpec("ip_name", "IP instance name.")],
        handler=h.generate_ip,
    ),
    # --- SynthPilot compatibility: Project utilities --------------------
    ToolSpec(
        name="get_project_info",
        tcl_template="",
        summary="Get project name, part, directory, top module, status.",
        category="project",
        vendor="common",
        handler=h.get_project_info,
    ),
    ToolSpec(
        name="add_source_file",
        tcl_template="",
        summary="Add a single Verilog/VHDL/SystemVerilog source file.",
        category="project",
        vendor="common",
        args=[
            ArgSpec("filename", "Path to source file."),
            ArgSpec("library", "Optional library.", required=False, default=""),
        ],
        handler=h.add_source_file,
    ),
    ToolSpec(
        name="add_constraint_file",
        tcl_template="",
        summary="Add a single constraint file.",
        category="project",
        vendor="common",
        args=[ArgSpec("filename", "Path to constraint file.")],
        handler=h.add_constraint_file,
    ),
    ToolSpec(
        name="set_top_module",
        tcl_template="",
        summary="Set the top-level module.",
        category="project",
        vendor="common",
        args=[ArgSpec("module_name", "Top module name.")],
        handler=h.set_top_module,
    ),
    ToolSpec(
        name="list_source_files",
        tcl_template="",
        summary="List all source files in the project.",
        category="project",
        vendor="common",
        handler=h.list_source_files,
    ),
    ToolSpec(
        name="list_constraint_files",
        tcl_template="",
        summary="List all constraint files.",
        category="project",
        vendor="common",
        handler=h.list_constraint_files,
    ),
    ToolSpec(
        name="remove_file",
        tcl_template="",
        summary="Remove a file from the project.",
        category="project",
        vendor="common",
        args=[ArgSpec("filename", "Path to file.")],
        handler=h.remove_file,
    ),
    # --- SynthPilot compatibility: Flow utilities -----------------------
    ToolSpec(
        name="get_run_status",
        tcl_template="",
        summary="Check run status (synth/impl).",
        category="flow",
        vendor="common",
        args=[ArgSpec("run_name", "Run name.", required=False, default="impl_1")],
        handler=h.get_run_status,
    ),
    ToolSpec(
        name="get_synthesis_report",
        tcl_template="",
        summary="Get synthesis utilization summary.",
        category="reports",
        vendor="common",
        handler=h.get_synthesis_report,
    ),
    ToolSpec(
        name="export_hardware",
        tcl_template="",
        summary="Export hardware definition (.xsa) for embedded development.",
        category="flow",
        vendor="common",
        handler=h.export_hardware,
    ),
    # --- SynthPilot compatibility: Reports ------------------------------
    ToolSpec(
        name="report_timing_summary",
        tcl_template="",
        summary="Overall timing: WNS, TNS, WHS, THS.",
        category="reports",
        vendor="common",
        args=[
            ArgSpec("max_paths", "Max paths to show.", required=False, default=10, type_hint=int)
        ],
        handler=h.report_timing_summary,
    ),
    ToolSpec(
        name="report_drc",
        tcl_template="",
        summary="Design Rule Check violations.",
        category="reports",
        vendor="common",
        handler=h.report_drc,
    ),
    # --- SynthPilot compatibility: Constraints --------------------------
    ToolSpec(
        name="create_clock_constraint",
        tcl_template="",
        summary="Define a primary clock.",
        category="constraints",
        vendor="common",
        args=[
            ArgSpec("name", "Clock name."),
            ArgSpec("period", "Clock period in ns."),
            ArgSpec("waveform", "Waveform values.", required=False, default="0 0.5"),
        ],
        handler=h.create_clock_constraint,
    ),
    ToolSpec(
        name="create_io_constraint",
        tcl_template="",
        summary="Pin assignment + I/O standard.",
        category="constraints",
        vendor="common",
        args=[
            ArgSpec("port", "Port name."),
            ArgSpec("pin", "Package pin."),
            ArgSpec("iostandard", "I/O standard.", required=False, default="LVCMOS33"),
        ],
        handler=h.create_io_constraint,
    ),
    ToolSpec(
        name="get_all_clocks",
        tcl_template="",
        summary="List all defined clocks.",
        category="constraints",
        vendor="common",
        handler=h.get_all_clocks,
    ),
    ToolSpec(
        name="get_clock_info",
        tcl_template="",
        summary="Get clock period, waveform, sources.",
        category="constraints",
        vendor="common",
        args=[ArgSpec("clock", "Clock name.", required=False, default="")],
        handler=h.get_clock_info,
    ),
    ToolSpec(
        name="save_constraints",
        tcl_template="",
        summary="Write constraints to XDC file.",
        category="constraints",
        vendor="common",
        args=[ArgSpec("filename", "Output filename.", required=False, default="constraints.xdc")],
        handler=h.save_constraints,
    ),
    # --- SynthPilot compatibility: File operations ----------------------
    ToolSpec(
        name="create_source_file",
        tcl_template="",
        summary="Create new Verilog/VHDL file with template.",
        category="files",
        vendor="common",
        args=[
            ArgSpec("filename", "Output filename."),
            ArgSpec("content", "File content.", required=False, default=""),
        ],
        handler=h.create_source_file,
    ),
    ToolSpec(
        name="create_constraint_file",
        tcl_template="",
        summary="Create new XDC file.",
        category="files",
        vendor="common",
        args=[
            ArgSpec("filename", "Output filename."),
            ArgSpec("content", "File content.", required=False, default=""),
        ],
        handler=h.create_constraint_file,
    ),
    ToolSpec(
        name="read_file",
        tcl_template="",
        summary="Read file contents.",
        category="files",
        vendor="common",
        args=[ArgSpec("filename", "Path to file.")],
        handler=h.read_file,
    ),
    ToolSpec(
        name="append_to_file",
        tcl_template="",
        summary="Append content to file.",
        category="files",
        vendor="common",
        args=[
            ArgSpec("filename", "Path to file."),
            ArgSpec("content", "Content to append."),
        ],
        handler=h.append_to_file,
    ),
    ToolSpec(
        name="read_file_lines",
        tcl_template="",
        summary="Read specific line range.",
        category="files",
        vendor="common",
        args=[
            ArgSpec("filename", "Path to file."),
            ArgSpec("start", "Start line.", required=False, default=1, type_hint=int),
            ArgSpec("end", "End line.", required=False, default=-1, type_hint=int),
        ],
        handler=h.read_file_lines,
    ),
    ToolSpec(
        name="list_all_files",
        tcl_template="",
        summary="List project files.",
        category="files",
        vendor="common",
        handler=h.list_all_files,
    ),
    # --- SynthPilot compatibility: Hardware management ------------------
    ToolSpec(
        name="open_hardware_manager",
        tcl_template="",
        summary="Open Hardware Manager.",
        category="hardware",
        vendor="common",
        handler=h.open_hardware_manager,
    ),
    ToolSpec(
        name="connect_hardware_server",
        tcl_template="",
        summary="Connect to hw_server.",
        category="hardware",
        vendor="common",
        args=[
            ArgSpec("host", "Server host.", required=False, default="localhost"),
            ArgSpec("port", "Server port.", required=False, default=3121, type_hint=int),
        ],
        handler=h.connect_hardware_server,
    ),
    ToolSpec(
        name="list_hardware_targets",
        tcl_template="",
        summary="List JTAG targets.",
        category="hardware",
        vendor="common",
        handler=h.list_hardware_targets,
    ),
    ToolSpec(
        name="open_hardware_target",
        tcl_template="",
        summary="Open target.",
        category="hardware",
        vendor="common",
        args=[ArgSpec("target", "Target name.", required=False, default="")],
        handler=h.open_hardware_target,
    ),
    ToolSpec(
        name="list_hardware_devices",
        tcl_template="",
        summary="List devices on target.",
        category="hardware",
        vendor="common",
        handler=h.list_hardware_devices,
    ),
    ToolSpec(
        name="disconnect_hardware",
        tcl_template="",
        summary="Disconnect from hardware.",
        category="hardware",
        vendor="common",
        handler=h.disconnect_hardware,
    ),
]
