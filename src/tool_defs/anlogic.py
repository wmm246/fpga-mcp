"""Anlogic TangDynasty (TD) tool catalogue.

Thin Tcl wrappers over the TD Tcl console commands. The TD Tcl surface is
smaller than Vivado's; the bulk of tools here cover project / flow /
timing / reports. Many commands are vendor-specific to Tang / EG / ELF /
PH1 families.
"""

from __future__ import annotations

from fpga_mcp.tool_defs import ArgSpec, ToolSpec


def _t(name, tcl, summary, category, args=None, notes="", timeout=600.0):
    return ToolSpec(
        name=name,
        tcl_template=tcl,
        summary=summary,
        category=category,
        vendor="anlogic",
        args=args or [],
        notes=notes,
        timeout=timeout,
    )


SPECS: list[ToolSpec] = []

# ============================================================================
# Project & files
# ============================================================================

SPECS += [
    _t(
        "a_create_project",
        "create_project -name {{{{name}}}} -dir {{{{dir}}}} -part {{{{part}}}} -hdl {{{{hdl}}}}",
        "Create an Anlogic project.",
        "project",
        [
            ArgSpec("name"),
            ArgSpec("dir"),
            ArgSpec("part", "e.g. EG4S20BG256."),
            ArgSpec("hdl", "verilog or vhdl.", required=False, default="verilog"),
        ],
    ),
    _t(
        "a_open_project",
        "open_project {{{{path}}}}",
        "Open an existing .al project.",
        "project",
        [ArgSpec("path")],
    ),
    _t("a_close_project", "close_project", "Close the current project.", "project"),
    _t("a_save_project", "save_project", "Save the current project.", "project"),
    _t(
        "a_save_project_as",
        "save_project_as {{{{path}}}}",
        "Save the project to a new path.",
        "project",
        [ArgSpec("path")],
    ),
    _t("a_current_project", "current_project", "Return the current project handle.", "project"),
    _t("a_get_part", "get_part", "Return the project's target part.", "project"),
    _t(
        "a_set_part",
        "set_part {{{{part}}}}",
        "Change the target part.",
        "project",
        [ArgSpec("part")],
    ),
    _t("a_get_top", "get_top", "Return the project top.", "project"),
    _t(
        "a_set_top",
        "set_top {{{{top}}}}",
        "Set the project top module.",
        "project",
        [ArgSpec("top")],
    ),
    _t("a_get_hdl", "get_hdl", "Return the HDL family.", "project"),
    _t("a_set_hdl", "set_hdl {{{{hdl}}}}", "Set the HDL family.", "project", [ArgSpec("hdl")]),
    _t("a_get_project_dir", "get_project_dir", "Return the project directory.", "project"),
    _t(
        "a_add_file",
        "add_file {{{{file}}}}",
        "Add a source file to the project.",
        "fileset",
        [ArgSpec("file")],
    ),
    _t(
        "a_add_include_dir",
        "add_include_dir {{{{dir}}}}",
        "Add a Verilog include directory.",
        "fileset",
        [ArgSpec("dir")],
    ),
    _t(
        "a_add_constraint",
        "add_constraint {{{{file}}}}",
        "Add an .sdc / .fdc constraint file.",
        "fileset",
        [ArgSpec("file")],
    ),
    _t(
        "a_remove_file",
        "remove_file {{{{file}}}}",
        "Remove a source file.",
        "fileset",
        [ArgSpec("file")],
    ),
    _t("a_get_files", "get_files", "List all source files.", "fileset"),
    _t("a_get_constraints", "get_constraints", "List all constraint files.", "fileset"),
    _t(
        "a_import_files",
        "import_files {{{{files}}}}",
        "Import (copy) files into the project.",
        "fileset",
        [ArgSpec("files")],
    ),
    _t(
        "a_export_files",
        "export_files {{{{dir}}}}",
        "Export project files to a directory.",
        "fileset",
        [ArgSpec("dir")],
    ),
    _t(
        "a_set_file_property",
        "set_file_property -file {{{{file}}}} -name {{{{name}}}} -value {{{{value}}}}",
        "Set a per-file property.",
        "fileset",
        [ArgSpec("file"), ArgSpec("name"), ArgSpec("value")],
    ),
    _t(
        "a_get_file_property",
        "get_file_property -file {{{{file}}}} -name {{{{name}}}}",
        "Get a per-file property.",
        "fileset",
        [ArgSpec("file"), ArgSpec("name")],
    ),
    _t(
        "a_set_lib",
        "set_property -file {{{{file}}}} -name LIBRARY -value {{{{lib}}}}",
        "Assign a source file to a library.",
        "fileset",
        [ArgSpec("file"), ArgSpec("lib")],
    ),
    _t("a_list_libs", "list_libs", "List all libraries.", "fileset"),
    _t(
        "a_create_lib",
        "create_library -name {{{{name}}}}",
        "Create a user library.",
        "fileset",
        [ArgSpec("name")],
    ),
    _t(
        "a_delete_lib",
        "delete_library -name {{{{name}}}}",
        "Delete a user library.",
        "fileset",
        [ArgSpec("name")],
    ),
]

# ============================================================================
# Synthesis & implementation
# ============================================================================

SPECS += [
    _t("a_run_syn", "run_syn", "Run synthesis.", "synth", timeout=7200.0),
    _t(
        "a_run_pnr",
        "run_pnr",
        "Run place & route (includes bitstream on older TD).",
        "impl",
        timeout=14400.0,
    ),
    _t("a_reset_syn", "reset_run -syn", "Reset the synth run.", "synth"),
    _t("a_reset_pnr", "reset_run -pnr", "Reset the impl run.", "impl"),
    _t("a_get_syn_status", "get_run_status -run syn", "Get synth run status.", "synth"),
    _t("a_get_pnr_status", "get_run_status -run pnr", "Get impl run status.", "impl"),
    _t("a_get_syn_progress", "get_run_progress -run syn", "Get synth run progress %.", "synth"),
    _t("a_get_pnr_progress", "get_run_progress -run pnr", "Get impl run progress %.", "impl"),
    _t("a_stop_syn", "stop_run -syn", "Stop the synth run.", "synth"),
    _t("a_stop_pnr", "stop_run -pnr", "Stop the impl run.", "impl"),
    _t(
        "a_set_syn_strategy",
        "set_property -run syn -name STRATEGY -value {{{{strategy}}}}",
        "Set synth strategy.",
        "synth",
        [ArgSpec("strategy")],
    ),
    _t(
        "a_set_pnr_strategy",
        "set_property -run pnr -name STRATEGY -value {{{{strategy}}}}",
        "Set impl strategy.",
        "impl",
        [ArgSpec("strategy")],
    ),
    _t(
        "a_set_syn_effort",
        "set_property -run syn -name EFFORT_LEVEL -value {{{{effort}}}}",
        "Set synth effort level.",
        "synth",
        [ArgSpec("effort", "low/medium/high.")],
    ),
    _t(
        "a_set_pnr_effort",
        "set_property -run pnr -name EFFORT_LEVEL -value {{{{effort}}}}",
        "Set P&R effort level.",
        "impl",
        [ArgSpec("effort")],
    ),
    _t(
        "a_enable_pipelining",
        "set_property -run syn -name PIPELINING -value on",
        "Enable pipelining.",
        "synth",
    ),
    _t(
        "a_disable_pipelining",
        "set_property -run syn -name PIPELINING -value off",
        "Disable pipelining.",
        "synth",
    ),
    _t(
        "a_set_resource_sharing",
        "set_property -run syn -name RESOURCE_SHARING -value {{{{value}}}}",
        "Set resource sharing level.",
        "synth",
        [ArgSpec("value")],
    ),
    _t(
        "a_set_optimization",
        "set_property -run syn -name OPTIMIZATION -value {{{{mode}}}}",
        "Set optimization mode (area/speed/balanced).",
        "synth",
        [ArgSpec("mode")],
    ),
    _t(
        "a_enable_ram_balancing",
        "set_property -run syn -name RAM_BALANCING -value on",
        "Enable RAM balancing.",
        "synth",
    ),
    _t(
        "a_enable_dsp_balancing",
        "set_property -run syn -name DSP_BALANCING -value on",
        "Enable DSP balancing.",
        "synth",
    ),
    _t(
        "a_enable_fsm_extract",
        "set_property -run syn -name FSM_EXTRACT -value on",
        "Enable FSM extraction.",
        "synth",
    ),
    _t(
        "a_set_max_bram",
        "set_property -run pnr -name MAX_BRAM -value {{{{n}}}}",
        "Set max BRAM count.",
        "impl",
        [ArgSpec("n", type_hint=int)],
    ),
    _t(
        "a_set_max_dsp",
        "set_property -run pnr -name MAX_DSP -value {{{{n}}}}",
        "Set max DSP count.",
        "impl",
        [ArgSpec("n", type_hint=int)],
    ),
    _t(
        "a_set_max_luts",
        "set_property -run pnr -name MAX_LUTS -value {{{{n}}}}",
        "Set max LUT count.",
        "impl",
        [ArgSpec("n", type_hint=int)],
    ),
    _t(
        "a_set_placer_seed",
        "set_property -run pnr -name PLACER_SEED -value {{{{seed}}}}",
        "Set placer seed.",
        "impl",
        [ArgSpec("seed", type_hint=int)],
    ),
    _t(
        "a_set_router_seed",
        "set_property -run pnr -name ROUTER_SEED -value {{{{seed}}}}",
        "Set router seed.",
        "impl",
        [ArgSpec("seed", type_hint=int)],
    ),
    _t(
        "a_enable_post_place_phys_opt",
        "set_property -run pnr -name POST_PLACE_PHYS_OPT -value on",
        "Enable post-place phys_opt.",
        "impl",
    ),
    _t(
        "a_enable_post_route_phys_opt",
        "set_property -run pnr -name POST_ROUTE_PHYS_OPT -value on",
        "Enable post-route phys_opt.",
        "impl",
    ),
    _t(
        "a_generate_bitstream",
        "generate_bitstream",
        "Generate the bitstream.",
        "impl",
        timeout=3600.0,
    ),
    _t(
        "a_save_checkpoint",
        "save_checkpoint -file {{{{path}}}}",
        "Save design checkpoint.",
        "impl",
        [ArgSpec("path")],
    ),
    _t(
        "a_open_checkpoint",
        "open_checkpoint {{{{path}}}}",
        "Open a saved checkpoint.",
        "impl",
        [ArgSpec("path")],
    ),
    _t(
        "a_open_run",
        "open_run -run {{{{run}}}}",
        "Open a run as a design.",
        "impl",
        [ArgSpec("run")],
    ),
    _t("a_close_design", "close_design", "Close the current design.", "impl"),
    _t("a_current_design", "current_design", "Return the current design handle.", "impl"),
]

# ============================================================================
# IP
# ============================================================================

SPECS += [
    _t(
        "a_create_ip",
        "create_ip -name {{{{name}}}} -module_name {{{{module}}}}",
        "Create an IP instance.",
        "ip",
        [ArgSpec("name"), ArgSpec("module")],
    ),
    _t("a_get_ips", "get_ips", "List all IP instances.", "ip"),
    _t(
        "a_set_ip_property",
        "set_ip_property {{{{name}}}} {{{{prop}}}} {{{{value}}}}",
        "Set an IP property.",
        "ip",
        [ArgSpec("name"), ArgSpec("prop"), ArgSpec("value")],
    ),
    _t(
        "a_get_ip_property",
        "get_ip_property {{{{name}}}} {{{{prop}}}}",
        "Get an IP property.",
        "ip",
        [ArgSpec("name"), ArgSpec("prop")],
    ),
    _t(
        "a_generate_ip",
        "generate_ip {{{{name}}}}",
        "Generate IP output products.",
        "ip",
        [ArgSpec("name")],
        timeout=1800.0,
    ),
    _t(
        "a_upgrade_ip",
        "upgrade_ip {{{{name}}}}",
        "Upgrade an out-of-date IP.",
        "ip",
        [ArgSpec("name")],
        timeout=1800.0,
    ),
    _t(
        "a_lock_ip",
        "set_ip_property {{{{name}}}} LOCKED true",
        "Lock an IP against edits.",
        "ip",
        [ArgSpec("name")],
    ),
    _t(
        "a_unlock_ip",
        "set_ip_property {{{{name}}}} LOCKED false",
        "Unlock an IP.",
        "ip",
        [ArgSpec("name")],
    ),
    _t("a_list_ip_catalog", "list_ip_catalog", "List all available IPs.", "ip"),
    _t(
        "a_get_ip_defs",
        "get_ip_defs -name {{{{pattern}}}}",
        "List IP definitions matching a pattern.",
        "ip",
        [ArgSpec("pattern")],
    ),
    _t(
        "a_set_ip_repo",
        "set_ip_repo_paths {{{{path}}}}",
        "Register a custom IP repo path.",
        "ip",
        [ArgSpec("path")],
    ),
    _t("a_update_ip_catalog", "update_ip_catalog", "Refresh the IP catalog.", "ip"),
]

# ============================================================================
# Constraints (SDC / FDC)
# ============================================================================

SPECS += [
    _t(
        "a_create_clock",
        "create_clock -name {{{{name}}}} -period {{{{period}}}} -waveform {{0 {{{{high}}}}}} [get_ports {{{{port}}}}]",
        "Define a primary clock.",
        "constraints",
        [
            ArgSpec("name"),
            ArgSpec("period"),
            ArgSpec("high", required=False, default="5"),
            ArgSpec("port"),
        ],
    ),
    _t(
        "a_create_generated_clock",
        "create_generated_clock -name {{{{name}}}} -source [get_pins {{{{src}}}}] -divide_by {{{{div}}}} [get_pins {{{{dst}}}}]",
        "Define a generated clock.",
        "constraints",
        [ArgSpec("name"), ArgSpec("src"), ArgSpec("div"), ArgSpec("dst")],
    ),
    _t(
        "a_set_false_path",
        "set_false_path -from [get_clocks {{{{from}}}}] -to [get_clocks {{{{to}}}}]",
        "Set a false path.",
        "constraints",
        [ArgSpec("from"), ArgSpec("to")],
    ),
    _t(
        "a_set_max_delay",
        "set_max_delay -from [get_clocks {{{{from}}}}] -to [get_clocks {{{{to}}}}] {{{{delay}}}}",
        "Set max delay.",
        "constraints",
        [ArgSpec("from"), ArgSpec("to"), ArgSpec("delay")],
    ),
    _t(
        "a_set_min_delay",
        "set_min_delay -from [get_pins {{{{from}}}}] -to [get_pins {{{{to}}}}] {{{{delay}}}}",
        "Set min delay.",
        "constraints",
        [ArgSpec("from"), ArgSpec("to"), ArgSpec("delay")],
    ),
    _t(
        "a_set_multicycle_path",
        "set_multicycle_path -setup -from [get_clocks {{{{from}}}}] -to [get_clocks {{{{to}}}}] {{{{n}}}}",
        "Set a multicycle path.",
        "constraints",
        [ArgSpec("from"), ArgSpec("to"), ArgSpec("n", type_hint=int)],
    ),
    _t(
        "a_set_clock_groups",
        "set_clock_groups -asynchronous -group [get_clocks {{{{g1}}}}] -group [get_clocks {{{{g2}}}}]",
        "Declare two clock groups as async.",
        "constraints",
        [ArgSpec("g1"), ArgSpec("g2")],
    ),
    _t(
        "a_set_input_delay",
        "set_input_delay -clock [get_clocks {{{{clock}}}}] -max {{{{delay}}}} [get_ports {{{{port}}}}]",
        "Set input delay (max).",
        "constraints",
        [ArgSpec("clock"), ArgSpec("delay"), ArgSpec("port")],
    ),
    _t(
        "a_set_output_delay",
        "set_output_delay -clock [get_clocks {{{{clock}}}}] -max {{{{delay}}}} [get_ports {{{{port}}}}]",
        "Set output delay (max).",
        "constraints",
        [ArgSpec("clock"), ArgSpec("delay"), ArgSpec("port")],
    ),
    _t(
        "a_set_clock_uncertainty",
        "set_clock_uncertainty -setup {{{{unc}}}} [get_clocks {{{{clock}}}}]",
        "Set clock uncertainty.",
        "constraints",
        [ArgSpec("unc"), ArgSpec("clock")],
    ),
    _t(
        "a_set_clock_latency",
        "set_clock_latency -source {{{{lat}}}} [get_clocks {{{{clock}}}}]",
        "Set clock latency.",
        "constraints",
        [ArgSpec("lat"), ArgSpec("clock")],
    ),
    _t(
        "a_set_case_analysis",
        "set_case_analysis {{{{val}}}} [get_pins {{{{pin}}}}]",
        "Apply case analysis to a pin.",
        "constraints",
        [ArgSpec("val"), ArgSpec("pin")],
    ),
    _t(
        "a_set_disable_timing",
        "set_disable_timing [get_pins {{{{pin}}}}]",
        "Disable timing arcs on a pin.",
        "constraints",
        [ArgSpec("pin")],
    ),
    _t("a_get_clocks", "get_clocks", "List all clocks.", "constraints"),
    _t(
        "a_get_clocks_pattern",
        "get_clocks {{{{pattern}}}}",
        "List clocks matching a pattern.",
        "constraints",
        [ArgSpec("pattern")],
    ),
    _t("a_all_inputs", "all_inputs", "Return all input ports.", "constraints"),
    _t("a_all_outputs", "all_outputs", "Return all output ports.", "constraints"),
    _t("a_all_registers", "all_registers", "Return all registers.", "constraints"),
    _t(
        "a_set_async_reg",
        "set_property ASYNC_REG true [get_cells {{{{name}}}}]",
        "Mark a register as async (CDC).",
        "constraints",
        [ArgSpec("name")],
    ),
    _t(
        "a_set_dont_touch",
        "set_property DONT_TOUCH true [get_cells {{{{cell}}}}]",
        "Prevent optimization on a cell.",
        "constraints",
        [ArgSpec("cell")],
    ),
]

# ============================================================================
# Reports
# ============================================================================

SPECS += [
    _t(
        "a_report_timing",
        "report_timing -npaths {{{{n}}}} -return_string",
        "Report timing paths.",
        "timing_reports",
        [ArgSpec("n", required=False, default=10, type_hint=int)],
    ),
    _t(
        "a_report_timing_summary",
        "report_timing_summary -return_string",
        "Report timing summary.",
        "timing_reports",
    ),
    _t(
        "a_report_utilization",
        "report_utilization -return_string",
        "Report resource utilization.",
        "utilization_reports",
    ),
    _t("a_report_clocks", "report_clocks -return_string", "Report all clocks.", "timing_reports"),
    _t("a_report_cdc", "report_cdc -return_string", "Report CDC violations.", "timing_reports"),
    _t(
        "a_report_clock_transfers",
        "report_clock_transfers -return_string",
        "Report clock-to-clock transfers.",
        "timing_reports",
    ),
    _t(
        "a_report_exceptions",
        "report_exceptions -return_string",
        "Report timing exceptions.",
        "timing_reports",
    ),
    _t(
        "a_report_methodology",
        "report_methodology -return_string",
        "Report methodology checks.",
        "utilization_reports",
    ),
    _t(
        "a_report_drc",
        "report_drc -return_string",
        "Run design rule checks.",
        "utilization_reports",
    ),
    _t("a_report_power", "report_power -return_string", "Report power.", "utilization_reports"),
    _t(
        "a_report_high_fanout",
        "report_high_fanout_nets -return_string",
        "Report high-fanout nets.",
        "timing_reports",
    ),
    _t(
        "a_report_route_status",
        "report_route_status -return_string",
        "Report routing status.",
        "timing_reports",
    ),
    _t(
        "a_report_clock_routing",
        "report_clock_routing -return_string",
        "Report clock routing resources.",
        "timing_reports",
    ),
    _t(
        "a_report_hierarchy",
        "report_hierarchy -return_string",
        "Report design hierarchy.",
        "utilization_reports",
    ),
    _t("a_report_io", "report_io -return_string", "Report I/O assignments.", "utilization_reports"),
    _t(
        "a_report_clock_groups",
        "report_clock_groups -return_string",
        "Report clock groups.",
        "timing_reports",
    ),
    _t(
        "a_report_qor_suggestions",
        "report_qor_suggestions -return_string",
        "Report QoR optimization suggestions.",
        "timing_reports",
    ),
    _t(
        "a_report_pin_costs",
        "report_pin_costs -return_string",
        "Report pin cost.",
        "utilization_reports",
    ),
    _t(
        "a_report_floorplan",
        "report_floorplan -return_string",
        "Report floorplanning.",
        "utilization_reports",
    ),
    _t(
        "a_report_design_analysis",
        "report_design_analysis -return_string",
        "Report design analysis.",
        "utilization_reports",
    ),
]

# ============================================================================
# Netlist queries
# ============================================================================

SPECS += [
    _t("a_get_cells", "get_cells", "List all cells.", "netlist"),
    _t(
        "a_get_cells_pattern",
        "get_cells {{{{pattern}}}} -hier",
        "List cells matching PATTERN.",
        "netlist",
        [ArgSpec("pattern")],
    ),
    _t("a_get_nets", "get_nets", "List all nets.", "netlist"),
    _t(
        "a_get_nets_pattern",
        "get_nets {{{{pattern}}}} -hier",
        "List nets matching PATTERN.",
        "netlist",
        [ArgSpec("pattern")],
    ),
    _t("a_get_pins", "get_pins", "List all pins.", "netlist"),
    _t(
        "a_get_pins_of_cell",
        "get_pins -of_objects [get_cells {{{{cell}}}}]",
        "List pins of a cell.",
        "netlist",
        [ArgSpec("cell")],
    ),
    _t("a_get_ports", "get_ports", "List all ports.", "netlist"),
    _t(
        "a_get_ports_pattern",
        "get_ports {{{{pattern}}}}",
        "List ports matching PATTERN.",
        "netlist",
        [ArgSpec("pattern")],
    ),
    _t(
        "a_get_cell_property",
        "get_property {{{{prop}}}} [get_cells {{{{cell}}}}]",
        "Get a property of a cell.",
        "netlist",
        [ArgSpec("cell"), ArgSpec("prop")],
    ),
    _t(
        "a_set_cell_property",
        "set_property {{{{prop}}}} {{{{value}}}} [get_cells {{{{cell}}}}]",
        "Set a property of a cell.",
        "netlist",
        [ArgSpec("cell"), ArgSpec("prop"), ArgSpec("value")],
    ),
    _t(
        "a_get_net_property",
        "get_property {{{{prop}}}} [get_nets {{{{net}}}}]",
        "Get a property of a net.",
        "netlist",
        [ArgSpec("net"), ArgSpec("prop")],
    ),
    _t(
        "a_get_pin_property",
        "get_property {{{{prop}}}} [get_pins {{{{pin}}}}]",
        "Get a property of a pin.",
        "netlist",
        [ArgSpec("pin"), ArgSpec("prop")],
    ),
    _t(
        "a_get_port_property",
        "get_property {{{{prop}}}} [get_ports {{{{port}}}}]",
        "Get a property of a port.",
        "netlist",
        [ArgSpec("port"), ArgSpec("prop")],
    ),
    _t("a_get_pblocks", "get_pblocks", "List all pblocks.", "netlist"),
    _t(
        "a_create_pblock",
        "create_pblock {{{{name}}}}",
        "Create a pblock.",
        "netlist",
        [ArgSpec("name")],
    ),
    _t(
        "a_delete_pblock",
        "delete_pblocks [get_pblocks {{{{name}}}}]",
        "Delete a pblock.",
        "netlist",
        [ArgSpec("name")],
    ),
    _t(
        "a_add_cells_to_pblock",
        "add_cells_to_pblock [get_pblocks {{{{name}}}}] [get_cells {{{{cells}}}}]",
        "Add cells to a pblock.",
        "netlist",
        [ArgSpec("name"), ArgSpec("cells")],
    ),
]

# ============================================================================
# Simulation & device programming
# ============================================================================

SPECS += [
    _t(
        "a_export_simulation",
        "export_simulation -top {{{{top}}}} -mode {{{{kind}}}}",
        "Export simulation netlist for an external simulator.",
        "simulation",
        [ArgSpec("top"), ArgSpec("kind", "rtl/post_syn/post_impl.", required=False, default="rtl")],
        timeout=1800.0,
    ),
    _t(
        "a_set_simulation_top",
        "set_property top {{{{top}}}} [get_filesets sim_1]",
        "Set sim_1 top module.",
        "simulation",
        [ArgSpec("top")],
    ),
    _t(
        "a_run_simulation",
        "launch_simulation -mode {{{{mode}}}}",
        "Launch the simulator.",
        "simulation",
        [ArgSpec("mode", "behavioral/post-synthesis/timing.")],
        timeout=3600.0,
    ),
    _t("a_close_simulation", "close_sim", "Close the simulation.", "simulation"),
    _t(
        "a_program_device",
        "program_device -file {{{{bit}}}} -device_index {{{{index}}}}",
        "Program an FPGA via JTAG.",
        "hardware",
        [
            ArgSpec("bit", "Path to .bit."),
            ArgSpec("index", "Device index.", required=False, default=0, type_hint=int),
        ],
        timeout=120.0,
    ),
    _t("a_open_hw_manager", "open_hw_manager", "Open the hardware manager.", "hardware"),
    _t("a_close_hw_manager", "close_hw_manager", "Close the hardware manager.", "hardware"),
    _t("a_open_hw_target", "open_hw_target", "Open the first available JTAG target.", "hardware"),
    _t("a_close_hw_target", "close_hw_target", "Close the open JTAG target.", "hardware"),
    _t("a_get_hw_targets", "get_hw_targets", "List JTAG targets.", "hardware"),
    _t("a_get_hw_devices", "get_hw_devices", "List devices on the open target.", "hardware"),
    _t(
        "a_refresh_hw_device",
        "refresh_hw_device [get_hw_devices {{{{device}}}}]",
        "Refresh a device's state.",
        "hardware",
        [ArgSpec("device")],
    ),
]

# ============================================================================
# Tcl-level helpers
# ============================================================================

SPECS += [
    _t("a_source", "source {{{{file}}}}", "Source a Tcl file.", "tcl", [ArgSpec("file")]),
    _t("a_puts", "puts {{{{msg}}}}", "Print a message to the TD console.", "tcl", [ArgSpec("msg")]),
    _t(
        "a_set_var",
        "set {{{{name}}}} {{{{value}}}}",
        "Set a Tcl variable.",
        "tcl",
        [ArgSpec("name"), ArgSpec("value")],
    ),
    _t("a_get_var", "set {{{{name}}}}", "Get a Tcl variable.", "tcl", [ArgSpec("name")]),
    _t("a_pwd", "pwd", "Return the current working directory.", "tcl"),
    _t("a_cd", "cd {{{{dir}}}}", "Change working directory.", "tcl", [ArgSpec("dir")]),
    _t(
        "a_file_exists",
        "file exists {{{{path}}}}",
        "Check if a path exists.",
        "tcl",
        [ArgSpec("path")],
    ),
    _t("a_get_td_version", "version -short", "Return TD version string.", "tcl"),
    _t("a_get_user", "return $::env(USER)", "Return the current user.", "tcl"),
    _t("a_exec", "exec {{{{cmd}}}} >&@stdout", "Run a system command.", "tcl", [ArgSpec("cmd")]),
    _t(
        "a_list_dir",
        "glob -nocomplain -directory {{{{dir}}}} *",
        "List files in a directory.",
        "tcl",
        [ArgSpec("dir")],
    ),
    _t(
        "a_log_info",
        "send_msg_id {{{{id}}}} INFO {{{{msg}}}}",
        "Log INFO message.",
        "tcl",
        [ArgSpec("id"), ArgSpec("msg")],
    ),
    _t(
        "a_log_warning",
        "send_msg_id {{{{id}}}} WARNING {{{{msg}}}}",
        "Log WARNING message.",
        "tcl",
        [ArgSpec("id"), ArgSpec("msg")],
    ),
    _t(
        "a_log_error",
        "send_msg_id {{{{id}}}} ERROR {{{{msg}}}}",
        "Log ERROR message.",
        "tcl",
        [ArgSpec("id"), ArgSpec("msg")],
    ),
    _t(
        "a_catch",
        "catch {{{{cmd}}}} result; return $result",
        "Catch a Tcl error.",
        "tcl",
        [ArgSpec("cmd")],
    ),
]
