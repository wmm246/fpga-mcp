"""fpga-mcp — open multi-vendor MCP server for FPGA toolchains.

Drives Xilinx Vivado, Intel Quartus and Anlogic (Tang) FPGA flows from any
MCP-capable AI assistant. Multi-vendor abstraction lives in
:mod:`fpga_mcp.transports`; the MCP surface and methodology prompts live
in :mod:`fpga_mcp.server` and :mod:`fpga_mcp.prompts`.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
