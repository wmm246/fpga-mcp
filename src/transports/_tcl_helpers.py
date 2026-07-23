"""Shared Tcl string-quoting helpers used by every EDA backend.

Vivado, Quartus and Anlogic TD all accept Tcl; the only difference is what
commands are available. The quoting rules are identical, so the helpers live
here once.
"""

from __future__ import annotations

from typing import Iterable


def tcl_quote(s: str) -> str:
    """Quote a Python string as a safe Tcl word.

    Uses ``{...}`` braces when the string is brace-balanced and non-empty
    (cleaner output, no escaping noise), otherwise falls back to a
    backslash-escaped ``"..."`` form for strings containing unbalanced
    braces, embedded quotes, etc.
    """
    if s == "":
        return "{}"
    depth = 0
    balanced = True
    for c in s:
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0:
                balanced = False
                break
    if balanced and depth == 0:
        return "{" + s + "}"
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def tcl_list(items: Iterable) -> str:
    """Quote each item and join with spaces to form a Tcl list literal."""
    return " ".join(tcl_quote(str(i)) for i in items)


def tcl_dict(pairs: Iterable[tuple]) -> str:
    """Format a Python iterable of (key, value) pairs as a Tcl ``-dict`` body.

    Returns the inner list form suitable for ``set_property -dict [list ...]``
    or Quartus ``-name_<key>=<value>`` assignments.
    """
    return " ".join(f"{tcl_quote(str(k))} {tcl_quote(str(v))}" for k, v in pairs)
