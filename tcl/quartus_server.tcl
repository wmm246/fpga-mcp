# =============================================================================
# fpga-mcp — Quartus Tcl TCP server
# =============================================================================
# Source this file from the Quartus Tcl shell to expose a JSON-over-TCP RPC
# the Python backend talks to.
#
#   quartus_sh -t tcl/quartus_server.tcl
#   # or inside `quartus_sh -s`:
#   #   tcl> source tcl/quartus_server.tcl
#
# Override the port with:
#   set ::OMNI_PORT 12345
#   source tcl/quartus_server.tcl
# =============================================================================

set ::OMNI_SERVER_NAME "fpga-mcp/quartus-server"
if {![info exists ::OMNI_PORT]} { set ::OMNI_PORT 9998 }

set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir _omni_protocol.tcl]

# Quartus packages — required for the project/flow commands.
if {[catch {package require quartus} err]} {
    puts stderr "fpga-mcp: could not load the 'quartus' Tcl package: $err"
    puts stderr "  start this script from quartus_sh (Quartus Tcl shell)."
    exit 1
}
package require ::quartus::project
package require ::quartus::flow
package require ::quartus::sta

omni_start_server
