"""Unit tests for the small helper utilities."""

from __future__ import annotations

from fpga_mcp.transports._tcl_helpers import tcl_dict, tcl_list, tcl_quote


def test_tcl_quote_plain():
    assert tcl_quote("hello") == "{hello}"


def test_tcl_quote_empty():
    assert tcl_quote("") == "{}"


def test_tcl_quote_unbalanced_brace_falls_back_to_quoted():
    # The string "has {brace" has an unbalanced {, so we must use "..." form.
    q = tcl_quote("has {brace")
    assert q.startswith('"') and q.endswith('"')
    assert "{" in q  # literal brace preserved


def test_tcl_quote_balanced_braces_pass_through():
    # All braces balanced -> brace form.
    assert tcl_quote("a {b} c") == "{a {b} c}"


def test_tcl_quote_quote_char_in_braces():
    # A string with " but balanced braces uses brace form — Tcl allows "
    # inside braces.
    assert tcl_quote('say "hi"') == '{say "hi"}'


def test_tcl_list():
    assert tcl_list(["a", "b", "c"]) == "{a} {b} {c}"
    assert tcl_list([]) == ""


def test_tcl_dict_pairs():
    out = tcl_dict([("CLK_FREQ", "200"), ("RESET", "active_low")])
    assert "{CLK_FREQ} {200}" in out
    assert "{RESET} {active_low}" in out
