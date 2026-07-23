"""Unit tests for the declarative tool factory.

Covers:
  * ``ToolSpec.placeholder_names()`` extracts the right args.
  * ``ToolSpec.resolved_args()`` merges explicit ArgSpecs with template
    placeholders.
  * ``register_all()`` registers 500+ tools with no name collisions.
  * The factory-built callable actually dispatches to a Python handler when
    one is set, and to ``backend.exec_tcl`` otherwise.
  * The Tcl value rendering rules (None, bool, list).
"""

from __future__ import annotations

import asyncio


from fpga_mcp.config import Config
from fpga_mcp.server import build_server
from fpga_mcp.session import BackendManager
from fpga_mcp.tool_defs import (
    ArgSpec,
    ToolSpec,
    _build_callable,
    _to_tcl_value,
)
from fpga_mcp.tool_defs.anlogic import SPECS as ANLOGIC_SPECS
from fpga_mcp.tool_defs.common import SPECS as COMMON_SPECS
from fpga_mcp.tool_defs.quartus import SPECS as QUARTUS_SPECS
from fpga_mcp.tool_defs.vivado import SPECS as VIVADO_SPECS


# ---------------------------------------------------------------------------
# Spec parsing
# ---------------------------------------------------------------------------


def test_placeholder_names_basic():
    s = ToolSpec(
        name="t",
        tcl_template="get_clocks {pattern}",
        summary="",
        category="",
        vendor="vivado",
    )
    assert s.placeholder_names() == ["pattern"]


def test_placeholder_names_multiple_and_ordered():
    s = ToolSpec(
        name="t",
        tcl_template="set_property {prop} {value} [get_ips {ip}]",
        summary="",
        category="",
        vendor="vivado",
    )
    assert s.placeholder_names() == ["prop", "value", "ip"]


def test_placeholder_names_skip_escaped_braces():
    # {{ and }} are literal Tcl braces and must not become args.
    s = ToolSpec(
        name="t",
        tcl_template="foreach x {{a b c}} {{put $x}}",
        summary="",
        category="",
        vendor="vivado",
    )
    assert s.placeholder_names() == []


def test_resolved_args_uses_explicit_specs_when_given():
    s = ToolSpec(
        name="t",
        tcl_template="set_property {prop} {value}",
        summary="",
        category="",
        vendor="vivado",
        args=[
            ArgSpec("prop", "Property key."),
            ArgSpec("value", "Property value.", required=False, default=""),
        ],
    )
    args = s.resolved_args()
    assert [a.name for a in args] == ["prop", "value"]
    assert args[0].description == "Property key."
    assert args[1].required is False
    assert args[1].default == ""


def test_resolved_args_infers_specs_when_empty():
    s = ToolSpec(
        name="t",
        tcl_template="get_clocks {pattern}",
        summary="",
        category="",
        vendor="vivado",
    )
    args = s.resolved_args()
    assert len(args) == 1
    assert args[0].name == "pattern"
    assert args[0].required is True


def test_resolved_args_merges_explicit_and_inferred():
    # Explicit spec for one arg, the other one inferred.
    s = ToolSpec(
        name="t",
        tcl_template="report_timing -from {from_pin} -to {to_pin}",
        summary="",
        category="",
        vendor="vivado",
        args=[ArgSpec("from_pin", "Startpoint.")],
    )
    args = s.resolved_args()
    assert [a.name for a in args] == ["from_pin", "to_pin"]
    assert args[0].description == "Startpoint."
    # Inferred spec has no description but is required.
    assert args[1].description == ""
    assert args[1].required is True


def test_docstring_contains_args_and_vendor():
    s = ToolSpec(
        name="get_clocks",
        tcl_template="get_clocks {pattern}",
        summary="List clocks.",
        category="timing",
        vendor="vivado",
    )
    doc = s.docstring()
    assert "List clocks." in doc
    assert "Backend: vivado" in doc
    assert "pattern" in doc


# ---------------------------------------------------------------------------
# Tcl value rendering
# ---------------------------------------------------------------------------


def test_to_tcl_value_none():
    assert _to_tcl_value(None) == ""


def test_to_tcl_value_bool():
    assert _to_tcl_value(True) == "1"
    assert _to_tcl_value(False) == "0"


def test_to_tcl_value_number():
    assert _to_tcl_value(42) == "42"
    assert _to_tcl_value(3.14) == "3.14"


def test_to_tcl_value_string_is_braced():
    # Strings go through tcl_quote -> {...} when balanced.
    assert _to_tcl_value("hello") == "{hello}"


def test_to_tcl_value_list():
    out = _to_tcl_value(["a", "b"])
    # tcl_list joins with spaces, each item braced.
    assert "{a}" in out and "{b}" in out


# ---------------------------------------------------------------------------
# Factory dispatch
# ---------------------------------------------------------------------------


class _StubBackend:
    """Minimal backend stub for factory dispatch tests."""

    name = "stub"

    def __init__(self):
        self.tcl_calls: list[str] = []
        self.connected = True

    def is_connected(self):
        return self.connected

    def connect(self):
        self.connected = True

    def exec_tcl(self, cmd, *, timeout=None):
        self.tcl_calls.append(cmd)
        return f"ok: {cmd}"


class _StubManager(BackendManager):
    """A BackendManager that always returns the stub backend."""

    def __init__(self, backend):
        # Skip parent __init__ — we don't need a real Config.
        self._stub = backend
        self._active_name = "stub"

    @property
    def active_name(self):
        return self._active_name

    def ensure_connected(self, name=None):
        return self._stub


def test_factory_dispatches_to_handler_when_set():
    received: dict = {}

    def my_handler(manager, kwargs):
        received["manager"] = manager
        received["kwargs"] = kwargs
        return "handler result"

    spec = ToolSpec(
        name="custom",
        tcl_template="",
        summary="custom tool",
        category="test",
        vendor="common",
        args=[ArgSpec("x", "X value.")],
        handler=my_handler,
    )
    stub = _StubBackend()
    manager = _StubManager(stub)
    fn = _build_callable(spec, manager)

    result = fn(x=42)
    assert result == "handler result"
    assert received["kwargs"] == {"x": 42}
    # Tcl backend must NOT have been called.
    assert stub.tcl_calls == []


def test_factory_validates_required_args_before_handler():
    spec = ToolSpec(
        name="custom",
        tcl_template="",
        summary="custom tool",
        category="test",
        vendor="common",
        args=[ArgSpec("x", "X value.")],
        handler=lambda m, k: "should not reach here",
    )
    stub = _StubBackend()
    manager = _StubManager(stub)
    fn = _build_callable(spec, manager)

    result = fn()
    assert result.startswith("ERROR: missing required argument 'x'")


def test_factory_renders_template_and_calls_exec_tcl():
    spec = ToolSpec(
        name="get_clocks",
        tcl_template="get_clocks {pattern}",
        summary="List clocks.",
        category="timing",
        vendor="vivado",
        args=[ArgSpec("pattern", "Name glob.")],
    )
    stub = _StubBackend()
    manager = _StubManager(stub)
    fn = _build_callable(spec, manager)

    result = fn(pattern="clk*")
    # Template should have rendered to "get_clocks {clk*}"
    assert stub.tcl_calls == ["get_clocks {clk*}"]
    assert result == "ok: get_clocks {clk*}"


def test_factory_returns_error_string_on_backend_error():
    from fpga_mcp.transports.base import BackendError

    def failing_handler(manager, kwargs):
        raise BackendError("boom")

    spec = ToolSpec(
        name="fail",
        tcl_template="",
        summary="failing tool",
        category="test",
        vendor="common",
        handler=failing_handler,
    )
    stub = _StubBackend()
    manager = _StubManager(stub)
    fn = _build_callable(spec, manager)

    result = fn()
    assert result == "ERROR: boom"


# ---------------------------------------------------------------------------
# Catalogue invariants
# ---------------------------------------------------------------------------


def test_catalogue_has_at_least_500_specs():
    total = len(COMMON_SPECS) + len(VIVADO_SPECS) + len(QUARTUS_SPECS) + len(ANLOGIC_SPECS)
    assert total >= 500, f"only {total} specs"


def test_no_duplicate_tool_names():
    all_names = [s.name for s in COMMON_SPECS + VIVADO_SPECS + QUARTUS_SPECS + ANLOGIC_SPECS]
    assert len(all_names) == len(set(all_names)), "duplicate tool names"


def test_each_vendor_has_a_prefix_convention():
    # Vivado specs are viv_, Quartus are q_, Anlogic are a_. Common specs
    # have no prefix.
    assert all(s.name.startswith("viv_") for s in VIVADO_SPECS), "vivado not prefixed"
    assert all(s.name.startswith("q_") for s in QUARTUS_SPECS), "quartus not prefixed"
    assert all(s.name.startswith("a_") for s in ANLOGIC_SPECS), "anlogic not prefixed"


def test_every_spec_has_non_empty_template_or_handler():
    """Each spec must either render a Tcl template or define a Python handler."""
    for s in COMMON_SPECS + VIVADO_SPECS + QUARTUS_SPECS + ANLOGIC_SPECS:
        if not s.tcl_template.strip():
            assert s.handler is not None, f"{s.name} has empty template and no handler"


def test_every_spec_has_summary_and_category():
    for s in COMMON_SPECS + VIVADO_SPECS + QUARTUS_SPECS + ANLOGIC_SPECS:
        assert s.summary, f"{s.name} missing summary"
        assert s.category, f"{s.name} missing category"
        assert s.vendor in {"vivado", "quartus", "anlogic", "common"}, (
            f"{s.name} has bad vendor {s.vendor!r}"
        )


# ---------------------------------------------------------------------------
# register_all end-to-end
# ---------------------------------------------------------------------------


def test_register_all_returns_count_and_registers_each():
    cfg = Config(active_backend="vivado")
    mcp = build_server(cfg)

    # Re-registering would collide because FastMCP stores by name. Just check
    # the count is the same as the catalogue.
    total = len(COMMON_SPECS) + len(VIVADO_SPECS) + len(QUARTUS_SPECS) + len(ANLOGIC_SPECS)

    async def main():
        tools = await mcp.list_tools()
        return len(tools)

    n = asyncio.run(main())
    assert n == total
