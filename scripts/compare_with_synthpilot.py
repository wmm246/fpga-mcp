#!/usr/bin/env python3
"""Compare fpga-mcp against SynthPilot feature list."""

from fpga_mcp.tool_defs.common import SPECS as COMMON
from fpga_mcp.tool_defs.vivado import SPECS as VIVADO
from fpga_mcp.tool_defs.quartus import SPECS as QUARTUS
from fpga_mcp.tool_defs.anlogic import SPECS as ANLOGIC


def main():
    print("=" * 70)
    print("fpga-mcp vs SynthPilot Feature Comparison")
    print("=" * 70)

    # Collect all tools
    all_tools = {s.name: s for s in COMMON + VIVADO + QUARTUS + ANLOGIC}

    # SynthPilot Free (40 tools)
    print("\n" + "=" * 70)
    print("1. SynthPilot Free Plan Coverage (40 tools)")
    print("=" * 70)

    synthpilot_free = {
        "Project Management": [
            "create_project",
            "open_project",
            "close_project",
            "get_project_info",
            "add_source_file",
            "add_constraint_file",
            "set_top_module",
            "list_source_files",
            "list_constraint_files",
            "remove_file",
        ],
        "Synthesis": ["run_synthesis", "get_run_status", "get_synthesis_report"],
        "Implementation": ["run_implementation", "export_hardware"],
        "Reports": ["report_utilization", "report_timing_summary", "report_drc"],
        "Constraints": [
            "create_clock_constraint",
            "create_io_constraint",
            "get_all_clocks",
            "get_clock_info",
            "save_constraints",
        ],
        "File Operations": [
            "create_source_file",
            "create_constraint_file",
            "read_file",
            "list_all_files",
            "append_to_file",
            "read_file_lines",
        ],
        "Device Programming": [
            "generate_bitstream",
            "open_hardware_manager",
            "connect_hardware_server",
            "list_hardware_targets",
            "open_hardware_target",
            "list_hardware_devices",
            "program_device",
            "disconnect_hardware",
        ],
    }

    free_covered = 0
    free_total = 0
    free_missing = []

    for category, tools in synthpilot_free.items():
        print(f"\n  {category}:")
        for tool in tools:
            free_total += 1
            status = "✅" if tool in all_tools else "❌"
            if tool in all_tools:
                free_covered += 1
            else:
                free_missing.append(tool)
            print(f"    {status} {tool}")

    print(f"\n  Total: {free_covered}/{free_total} covered")

    # SynthPilot Pro categories
    print("\n" + "=" * 70)
    print("2. SynthPilot Pro Plan Coverage")
    print("=" * 70)

    pro_categories = [
        ("Advanced Synthesis", "synth"),
        ("Advanced Implementation", "impl"),
        ("Advanced Reports", "timing_reports"),
        ("Advanced Constraints", "constraints"),
        ("IP Configuration", "ip"),
        ("Block Design", "block_design"),
        ("Simulation", "simulation"),
        ("Linting", "lint"),
        ("Debug Core", "debug"),
        ("Flash Programming", "flash"),
        ("Embedded Development", "xsct"),
    ]

    pro_scores = []
    for cat_name, cat_keyword in pro_categories:
        count = sum(1 for s in VIVADO if cat_keyword in s.category.lower())
        status = "✅" if count > 0 else "❌"
        pro_scores.append((cat_name, count, status))
        print(f"  {status} {cat_name}: {count} tools")

    # SynthPilot Max features
    print("\n" + "=" * 70)
    print("3. SynthPilot Max Plan Coverage")
    print("=" * 70)

    max_features = [
        ("Custom Tcl Execution", "exec_tcl", "exec_tcl" in all_tools),
        ("Non-Project Mode", "netlist", any("netlist" in s.category.lower() for s in VIVADO)),
        ("JTAG-AXI Debug", "debug", any("debug" in s.category.lower() for s in VIVADO)),
        ("ILA Runtime", "debug", any("debug" in s.category.lower() for s in VIVADO)),
    ]

    for name, keyword, covered in max_features:
        status = "✅" if covered else "❌"
        print(f"  {status} {name}")

    # Multi-vendor comparison
    print("\n" + "=" * 70)
    print("4. Multi-Vendor Support")
    print("=" * 70)

    print(f"  ✅ Vivado: {len(VIVADO)} tools")
    print(f"  ✅ Quartus: {len(QUARTUS)} tools")
    print(f"  ✅ Anlogic: {len(ANLOGIC)} tools")
    print(f"  ✅ Common (vendor-agnostic): {len(COMMON)} tools")

    # Summary
    print("\n" + "=" * 70)
    print("5. Summary")
    print("=" * 70)

    print(f"\n  fpga-mcp total tools: {len(all_tools)}")
    print(
        f"  SynthPilot Free: {free_covered}/{free_total} ({free_covered / free_total * 100:.1f}%)"
    )

    pro_covered = sum(1 for _, _, s in pro_scores if s == "✅")
    pro_total = len(pro_scores)
    print(
        f"  SynthPilot Pro categories: {pro_covered}/{pro_total} ({pro_covered / pro_total * 100:.1f}%)"
    )

    max_covered = sum(1 for _, _, c in max_features if c)
    max_total = len(max_features)
    print(
        f"  SynthPilot Max features: {max_covered}/{max_total} ({max_covered / max_total * 100:.1f}%)"
    )

    print("\n  Missing Free tools to add:")
    for tool in free_missing:
        print(f"    - {tool}")

    return 0 if free_covered == free_total else 1


if __name__ == "__main__":
    exit(main())
