# =============================================================================
# fpga-mcp — Vivado Tcl TCP server
# =============================================================================
# Source this file from Vivado to expose a JSON-over-TCP RPC the Python
# backend talks to.
#
#   vivado -mode tcl -source tcl/vivado_server.tcl
#   # or pick it from the GUI: Tools > Run Tcl Script...
#
# Override the port with:
#   set ::OMNI_PORT 12345
#   source tcl/vivado_server.tcl
# =============================================================================

set ::OMNI_SERVER_NAME "fpga-mcp/vivado-server"
set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir _omni_protocol.tcl]

omni_start_server
