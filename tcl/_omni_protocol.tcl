# =============================================================================
# fpga-mcp — shared Tcl TCP server protocol helpers
# =============================================================================
# Sourced by each vendor's `*_server.tcl` file. Implements a tiny,
# dependency-free JSON-over-TCP RPC so a Python client can drive the host
# EDA tool (Vivado / Quartus / Anlogic TD) over a local socket.
#
# Protocol (newline-delimited JSON):
#   Client -> Server:  {"id": <int>, "cmd": "<tcl>", "timeout": <sec?>}\n
#   Server -> Client:  {"id": <int>, "ok": <bool>, "result": "<str>", "error": "<str>"}\n
#   On connect, the server emits a banner line:
#       READY <identifying string> <version>\n
#
# Vendor scripts only need to:
#   1. `package require` their vendor packages
#   2. set ::OMNI_SERVER_NAME
#   3. (optionally) set ::OMNI_PORT  (default 9999)
#   4. call omni_start_server
# =============================================================================

if {![info exists ::OMNI_PORT]} { set ::OMNI_PORT 9999 }
if {![info exists ::OMNI_SERVER_NAME]} { set ::OMNI_SERVER_NAME "fpga-mcp" }
set ::OMNI_PROTOCOL_VERSION "1.0"

# --- JSON helpers -----------------------------------------------------------

proc omni_json_escape {s} {
    set s [string map {\\ \\\\ \" \\\" \n \\n \r \\r \t \\t} $s]
    return $s
}

proc omni_json_response {id ok result error} {
    set r [omni_json_escape $result]
    set e [omni_json_escape $error]
    set okStr [expr {$ok ? "true" : "false"}]
    return "{\"id\":$id,\"ok\":$okStr,\"result\":\"$r\",\"error\":\"$e\"}"
}

# Minimal recursive JSON parser sufficient for our request envelope.
proc omni_json_parse {s} {
    set pos 0
    return [omni_json_parse_value $s pos]
}

proc omni_json_parse_value {s posvar} {
    upvar 1 $posvar pos
    while {$pos < [string length $s] && [string is space -strict [string index $s $pos]]} { incr pos }
    set ch [string index $s $pos]
    if {$ch eq "\{"} {
        incr pos
        set result [dict create]
        while {1} {
            while {$pos < [string length $s] && [string is space -strict [string index $s $pos]]} { incr pos }
            set c [string index $s $pos]
            if {$c eq "\}"} { incr pos; break }
            if {$c eq ","} { incr pos; continue }
            set key [omni_json_parse_string $s pos]
            while {$pos < [string length $s] && [string is space -strict [string index $s $pos]]} { incr pos }
            incr pos ;# skip ':'
            while {$pos < [string length $s] && [string is space -strict [string index $s $pos]]} { incr pos }
            set val [omni_json_parse_value $s pos]
            dict set result $key $val
        }
        return $result
    } elseif {$ch eq "\""} {
        return [omni_json_parse_string $s pos]
    } elseif {$ch eq "t"} {
        incr pos 4
        return 1
    } elseif {$ch eq "f"} {
        incr pos 5
        return 0
    } elseif {$ch eq "n"} {
        incr pos 4
        return ""
    } else {
        set start $pos
        while {$pos < [string length $s]} {
            set c [string index $s $pos]
            if {$c eq "," || $c eq "\}" || [string is space -strict $c]} { break }
            incr pos
        }
        return [string range $s $start [expr {$pos - 1}]]
    }
}

proc omni_json_parse_string {s posvar} {
    upvar 1 $posvar pos
    incr pos
    set out ""
    while {$pos < [string length $s]} {
        set c [string index $s $pos]
        if {$c eq "\\"} {
            incr pos
            set nxt [string index $s $pos]
            switch -- $nxt {
                "n" { append out "\n" }
                "r" { append out "\r" }
                "t" { append out "\t" }
                "u" {
                    set hex [string range $s [expr {$pos + 1}] [expr {$pos + 4}]]
                    incr pos 4
                    append out [format %c [scan $hex %x]]
                }
                default { append out $nxt }
            }
            incr pos
        } elseif {$c eq "\""} {
            incr pos
            return $out
        } else {
            append out $c
            incr pos
        }
    }
    return $out
}

# --- TCP server -------------------------------------------------------------

proc omni_accept {sock addr port} {
    fconfigure $sock -buffering none -translation auto -encoding utf-8
    fileevent $sock readable [list omni_handle $sock]
    puts $sock "READY $::OMNI_SERVER_NAME $::OMNI_PROTOCOL_VERSION"
    flush $sock
}

proc omni_handle {sock} {
    if {[eof $sock]} { close $sock; return }
    set line [gets $sock]
    if {[string length $line] == 0} return
    set line [string trim $line]
    if {$line eq ""} return

    if {[catch {omni_json_parse $line} envelope]} {
        puts $sock [omni_json_response 0 0 "" "bad request: $envelope"]
        flush $sock
        return
    }

    set id [dict get $envelope id]
    set cmd ""
    if {[dict exists $envelope cmd]} { set cmd [dict get $envelope cmd] }
    set timeout ""
    if {[dict exists $envelope timeout]} { set timeout [dict get $envelope timeout] }

    if {[string trim $cmd] eq "omni_stop"} {
        catch {puts $sock [omni_json_response $id 1 "stopping" ""]}
        catch {flush $sock}
        catch {close $sock}
        after 0 { set ::omni_stop 1 }
        return
    }

    if {$timeout ne "" && $timeout > 0} {
        set timer [after [expr {int($timeout * 1000)}] \
            [list set ::omni_timeout_$id 1]]
        set result [catch {uplevel #0 $cmd} rc]
        catch {after cancel $timer}
        if {[info exists ::omni_timeout_$id] && [set ::omni_timeout_$id]} {
            unset ::omni_timeout_$id
            puts $sock [omni_json_response $id 0 "" "timeout after ${timeout}s"]
            flush $sock
            return
        }
        unset -nocomplain ::omni_timeout_$id
    } else {
        set result [catch {uplevel #0 $cmd} rc]
    }

    if {$result == 0} {
        puts $sock [omni_json_response $id 1 $rc ""]
    } else {
        puts $sock [omni_json_response $id 0 "" $rc]
    }
    flush $sock
}

proc omni_start_server {} {
    set srv [socket -server omni_accept $::OMNI_PORT]
    set ::OMNI_SERVER_SOCKET $srv
    puts "fpga-mcp: '$::OMNI_SERVER_NAME' listening on port $::OMNI_PORT"
    puts "fpga-mcp: send 'omni_stop' to shut down."
    flush stdout
    vwait ::omni_stop
    puts "fpga-mcp: server stopping."
    catch {close $srv}
}
