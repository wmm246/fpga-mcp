"""Tests that the FastMCP server builds and exposes the expected surface."""

from __future__ import annotations

import pytest

from fpga_mcp.config import Config
from fpga_mcp.server import build_server


@pytest.fixture
def server():
    cfg = Config(active_backend="vivado")
    return build_server(cfg)


async def test_server_lists_tools(server):
    tools = await server.list_tools()
    names = {t.name for t in tools}
    expected = {
        "list_backends",
        "set_backend",
        "ping_backend",
        "status",
        "exec_tcl",
        "create_project",
        "open_project",
        "close_project",
        "current_project",
        "add_sources",
        "add_constraints",
        "set_top",
        "run_synthesis",
        "run_implementation",
        "create_ip",
        "set_ip_property",
        "generate_ip",
        "run_simulation",
        "generate_bitstream",
        "program_device",
        "report_timing",
        "report_utilization",
    }
    assert expected.issubset(names), f"missing: {expected - names}"


async def test_server_has_at_least_500_tools(server):
    """fpga-mcp ships ~500+ tools like SynthPilot. Assert the surface exists."""
    tools = await server.list_tools()
    assert len(tools) >= 500, f"expected >=500 tools, got {len(tools)}"


async def test_server_covers_all_three_vendors(server):
    """Each vendor prefix must be represented in the tool catalogue."""
    tools = await server.list_tools()
    names = {t.name for t in tools}
    # Vivado specs use the viv_ prefix.
    assert any(n.startswith("viv_") for n in names), "no vivado-prefixed tools"
    # Quartus specs use the q_ prefix.
    assert any(n.startswith("q_") for n in names), "no quartus-prefixed tools"
    # Anlogic specs use the a_ prefix.
    assert any(n.startswith("a_") for n in names), "no anlogic-prefixed tools"


async def test_tool_descriptions_are_non_empty(server):
    """Every registered tool must have a description the LLM can read."""
    tools = await server.list_tools()
    empty = [t.name for t in tools if not (t.description or "").strip()]
    assert not empty, f"tools with empty description: {empty[:10]}"


async def test_server_lists_methodology_prompts(server):
    prompts = await server.list_prompts()
    names = {p.name for p in prompts}
    expected = {
        "full_flow",
        "timing_closure",
        "cdc_audit",
        "resource_budgeting",
        "sim_signoff",
        "bitstream_handoff",
        "soc_bringup",
    }
    assert expected.issubset(names), f"missing: {expected - names}"
