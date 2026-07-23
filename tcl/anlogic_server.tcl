# =============================================================================
# fpga-mcp — Anlogic TangDynasty (TD) Tcl TCP server
# =============================================================================
# Source this file from the Anlogic TD Tcl console to expose a JSON-over-TCP
# RPC the Python backend talks to.
#
#   td -tcl   # then in the console:
#   % source tcl/anlogic_server.tcl
#
# Override the port with:
#   set ::OMNI_PORT 12345
#   source tcl/anlogic_server.tcl
# =============================================================================

set ::OMNI_SERVER_NAME "fpga-mcp/anlogic-server"
if {![info exists ::OMNI_PORT]} { set ::OMNI_PORT 9997 }

set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir _omni_protocol.tcl]

omni_start_server
