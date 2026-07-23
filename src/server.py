"""FastMCP server entry point.

Wires up the backend manager and all MCP tools / prompts. The CLI ``run``
subcommand and the ``fpga-mcp`` console script both end up here.

Usage::

    from fpga_mcp.server import build_server
    mcp = build_server()
    mcp.run()
"""

from __future__ import annotations

import logging

from fpga_mcp.config import Config
from fpga_mcp.prompts import register_prompts
from fpga_mcp.session import default_manager
from fpga_mcp.tool_defs import register_all

log = logging.getLogger("fpga_mcp")

# Lazily-imported FastMCP keeps the module importable in environments where
# the mcp package isn't installed yet (e.g. during a fresh checkout for tests
# of pure-python helpers).
_FASTMCP = None


def _fastmcp():
    global _FASTMCP
    if _FASTMCP is None:
        from mcp.server.fastmcp import FastMCP

        _FASTMCP = FastMCP
    return _FASTMCP


def build_server(
    config: Config | None = None,
    *,
    name: str = "fpga-mcp",
) -> object:
    """Build a FastMCP server wired up with all tools and prompts.

    Returns the FastMCP instance. Callers either call ``.run()`` on it or
    feed it to an ``mcp`` transport runner.
    """
    cfg = config or Config.load()
    FastMCP = _fastmcp()
    mcp = FastMCP(
        name=name,
        instructions=_server_instructions(cfg),
    )

    manager = default_manager(cfg)
    register_all(mcp, manager)
    register_prompts(mcp, manager)
    return mcp


def run_stdio(config: Config | None = None) -> None:
    """Run the MCP server over stdio (the usual MCP transport)."""
    mcp = build_server(config)
    mcp.run()


def _read_version() -> str:
    try:
        from fpga_mcp import __version__

        return __version__
    except Exception:
        return "0.0.0"


def _server_instructions(cfg: Config) -> str:
    return (
        "fpga-mcp drives Xilinx Vivado, Intel Quartus and Anlogic "
        "TangDynasty FPGA toolchains. Use the `set_backend` tool first to "
        "switch vendors if needed (active backend: "
        f"{cfg.active_backend}). Start the matching Tcl TCP server "
        "before invoking flow tools — see tcl/<vendor>_server.tcl."
    )
