# =============================================================================
# fpga-mcp — Vivado stdin/stdout bridge
# =============================================================================
# Alternative to vivado_server.tcl that does NOT use socket -server / vwait.
# Instead, it reads JSON commands from stdin and writes JSON responses to
# stdout — a simple line-delimited protocol that works with Vivado's Tcl
# event loop (which does not process socket server callbacks).
#
# Usage from Python:
#   subprocess.Popen(['vivado', '-mode', 'tcl',
#                     '-source', 'tcl/vivado_stdio_bridge.tcl'],
#                    stdin=PIPE, stdout=PIPE, stderr=PIPE)
#
# Protocol (identical to the TCP server):
#   Client -> Server:  {"id": <int>, "cmd": "<tcl>", "timeout": <sec?>}\n
#   Server -> Client:  {"id": <int>, "ok": <bool>, "result": "<str>", "error": "<str>"}\n
#   On startup, the bridge emits:
#       READY <identifying string> <version>\n
# =============================================================================

set ::OMNI_SERVER_NAME "fpga-mcp/vivado-stdio"
set ::OMNI_PROTOCOL_VERSION "1.0"

# Source the shared JSON helpers (omni_json_parse, omni_json_response, etc.)
set script_dir [file dirname [file normalize [info script]]]
source [file join $script_dir "_omni_protocol.tcl"]

# -----------------------------------------------------------------------------
# Redirect Vivado's `puts` output to stderr so stdout stays clean for our
# JSON protocol.  Vivado's own INFO/WARNING/ERROR messages go through its
# internal message system (not `puts`), so they already go to stderr.
# Tcl `puts` calls from user scripts are redirected to stderr as well.
# -----------------------------------------------------------------------------
rename puts _orig_puts

proc puts {args} {
    # Parse puts arguments: ?-nonewline? ?channelId? string
    set nonewline 0
    set args_copy $args

    if {[llength $args_copy] > 0 && [lindex $args_copy 0] eq "-nonewline"} {
        set nonewline 1
        set args_copy [lrange $args_copy 1 end]
    }

    if {[llength $args_copy] >= 2} {
        set channel [lindex $args_copy 0]
        set text [lindex $args_copy 1]
        if {$channel eq "stdout"} {
            # Redirect stdout puts to stderr
            if {$nonewline} {
                _orig_puts -nonewline stderr $text
            } else {
                _orig_puts stderr $text
            }
        } else {
            # Other channels (stderr, files, etc.) pass through
            if {$nonewline} {
                _orig_puts -nonewline $channel $text
            } else {
                _orig_puts $channel $text
            }
        }
    } else {
        # Single argument: just the text — redirect to stderr
        set text [lindex $args_copy 0]
        if {$nonewline} {
            _orig_puts -nonewline stderr $text
        } else {
            _orig_puts stderr $text
        }
    }
}

# Clean output function that bypasses the redirect
proc _protocol_puts {text} {
    _orig_puts stdout $text
    flush stdout
}

# -----------------------------------------------------------------------------
# Main stdin/stdout loop
# -----------------------------------------------------------------------------

# Emit READY banner
_protocol_puts "READY $::OMNI_SERVER_NAME $::OMNI_PROTOCOL_VERSION"

# Read commands from stdin until EOF or omni_stop
while {1} {
    set line [gets stdin]
    if {[eof stdin]} break
    if {[string length $line] == 0} continue
    set line [string trim $line]
    if {$line eq ""} continue

    # Parse JSON envelope
    if {[catch {omni_json_parse $line} envelope]} {
        _protocol_puts [omni_json_response 0 0 "" "bad request: $envelope"]
        continue
    }

    set id [dict get $envelope id]
    set cmd ""
    if {[dict exists $envelope cmd]} { set cmd [dict get $envelope cmd] }
    set timeout ""
    if {[dict exists $envelope timeout]} { set timeout [dict get $envelope timeout] }

    # Handle stop command
    if {[string trim $cmd] eq "omni_stop"} {
        _protocol_puts [omni_json_response $id 1 "stopping" ""]
        break
    }

    # Execute the Tcl command
    if {$timeout ne "" && $timeout > 0} {
        set timer [after [expr {int($timeout * 1000)}] \
            [list set ::omni_timeout_$id 1]]
        set result [catch {uplevel #0 $cmd} rc]
        catch {after cancel $timer}
        if {[info exists ::omni_timeout_$id] && [set ::omni_timeout_$id]} {
            unset ::omni_timeout_$id
            _protocol_puts [omni_json_response $id 0 "" "timeout after ${timeout}s"]
            continue
        }
        unset -nocomplain ::omni_timeout_$id
    } else {
        set result [catch {uplevel #0 $cmd} rc]
    }

    if {$result == 0} {
        _protocol_puts [omni_json_response $id 1 $rc ""]
    } else {
        _protocol_puts [omni_json_response $id 0 "" $rc]
    }
}

# Clean exit
exit 0
