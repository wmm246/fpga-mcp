"""Declarative tool definitions — the catalogue of 500+ MCP tools.

Instead of hand-writing one Python function per MCP tool (which is what
SynthPilot-style projects do and ends up with ~500 near-duplicate
functions), fpga-mcp uses a **declarative** approach:

  1. A :class:`ToolSpec` is a 5-tuple
     ``(name, tcl_template, summary, category, vendor)``.
  2. The tool factory builds a thin wrapper around each spec that delegates
     to ``backend.exec_tcl(...)``.
  3. ``register_all(mcp, manager)`` walks every spec and registers it.

This file is the *shared machinery*. Per-vendor catalogues live in
``tool_defs/vivado.py``, ``tool_defs/quartus.py``, ``tool_defs/anlogic.py``
and ``tool_defs/common.py``.

Why this works well for LLMs
---------------------------
Each tool's docstring is auto-generated from the spec, so the LLM still sees
a discoverable surface. The `exec_tcl` escape hatch remains for the truly
ad-hoc cases; the catalogue covers the 80/20 of everyday flows.

Template syntax
---------------
``tcl_template`` uses Python ``str.format`` with named placeholders. Each
placeholder becomes a tool argument:

    ToolSpec(
        name="get_clocks",
        tcl_template="get_clocks {pattern}",
        summary="List clocks whose name matches PATTERN.",
        category="timing",
        vendor="vivado",
    )

The generated tool has one argument ``pattern`` (string). If the template
contains a literal ``{`` or ``}`` (Tcl brace), escape with ``{{`` and ``}}``.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from fpga_mcp.session import BackendManager
from fpga_mcp.transports.base import BackendError


# ---------------------------------------------------------------------------
# Spec dataclasses
# ---------------------------------------------------------------------------


#: Argument descriptor — lets us attach JSDoc-style descriptions to each
#: positional arg of an auto-generated tool. Optional; templates without
#: ArgSpecs are still registered, the args just get a generic docstring.
@dataclass
class ArgSpec:
    name: str
    description: str = ""
    required: bool = True
    default: Any = None
    type_hint: type = str

    def to_param_default(self) -> Any:
        if self.required:
            return ...
        return self.default


@dataclass
class ToolSpec:
    """One declarative MCP tool.

    Attributes
    ----------
    name : str
        Tool name as exposed to the LLM. Should be snake_case, no prefix
        (vendor is added automatically as a tag in the docstring).
    tcl_template : str
        A ``str.format``-style template. Named placeholders become tool
        arguments. Use ``{{`` / ``}}`` for literal Tcl braces.
    summary : str
        One-line description shown to the LLM.
    category : str
        Logical grouping for the auto-generated docs index.
    vendor : str
        Backend that owns this tool ("vivado" / "quartus" / "anlogic" /
        "common" — the latter is always available regardless of active
        backend).
    args : list[ArgSpec]
        Optional richer argument metadata. If empty, args are inferred
        from the template.
    timeout : float
        Default timeout in seconds for the underlying Tcl call.
    notes : str
        Extra multi-line docs appended after the summary.
    handler : Callable[[BackendManager, dict], str] | None
        If set, the factory calls this Python function instead of rendering
        the template. Use it for tools that need backend-specific Python
        API calls (create_project, run_synthesis, set_backend, etc.).
        The handler receives ``(manager, kwargs_dict)`` and returns a str.
    """

    name: str
    tcl_template: str
    summary: str
    category: str
    vendor: str
    args: list[ArgSpec] = field(default_factory=list)
    timeout: float = 600.0
    notes: str = ""
    handler: Callable[[BackendManager, dict], str] | None = None

    # ------------------------------------------------------------------

    def placeholder_names(self) -> list[str]:
        """Return the named placeholders in ``tcl_template`` in order."""
        # Find all {name} but skip {{ }} escapes.
        cleaned = self.tcl_template.replace("{{", "").replace("}}", "")
        return re.findall(r"\{([a-zA-Z_][a-zA-Z_0-9]*)\}", cleaned)

    def resolved_args(self) -> list[ArgSpec]:
        """Return ArgSpec list — either explicit or inferred from template."""
        if self.args:
            by_name = {a.name: a for a in self.args}
            # Make sure every template placeholder has a spec.
            result: list[ArgSpec] = []
            for n in self.placeholder_names():
                if n in by_name:
                    result.append(by_name[n])
                else:
                    result.append(ArgSpec(name=n))
            # Include explicit args that aren't template placeholders
            # (e.g., for handler-only tools with empty templates).
            seen = {a.name for a in result}
            for a in self.args:
                if a.name not in seen:
                    result.append(a)
            return result
        return [ArgSpec(name=n) for n in self.placeholder_names()]

    def docstring(self) -> str:
        """Generate a clean multi-line docstring for the tool."""
        lines = [self.summary]
        lines.append("")
        lines.append(f"Backend: {self.vendor}. Category: {self.category}.")
        lines.append("")
        args = self.resolved_args()
        if args:
            lines.append("Arguments:")
            for a in args:
                req = "required" if a.required else "optional"
                desc = f" — {a.description}" if a.description else ""
                lines.append(f"  - {a.name} ({req}){desc}")
            lines.append("")
        if self.notes:
            lines.append(self.notes)
            lines.append("")
        lines.append(
            "Returns the raw Tcl output string. If the underlying Tcl "
            "command raises, the error text is returned instead."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _build_callable(spec: ToolSpec, manager: BackendManager):
    """Construct a Python callable matching the spec.

    The callable accepts the spec's args as **explicit named parameters**
    (set via ``inspect.Signature``) so FastMCP can generate a proper JSON
    Schema with typed, named parameters instead of a single opaque
    ``kwargs`` blob.

    Dispatch:
    * If ``spec.handler`` is set, call ``handler(manager, kwargs_dict)``.
    * Otherwise render ``tcl_template`` and run via ``backend.exec_tcl``.
    """
    arg_specs = spec.resolved_args()

    # Build the inspect.Signature parameters from ArgSpecs so FastMCP
    # introspects real named parameters with types and defaults.
    # Python requires non-default args before default args, so we sort:
    # required params first, then optional params (preserving original order
    # within each group).
    # Also, Python keywords (e.g. 'from') cannot be parameter names, so
    # we append '_' and strip it back inside _impl.
    import keyword as _kwmod
    sig_params: list[inspect.Parameter] = []
    kind = inspect.Parameter.POSITIONAL_OR_KEYWORD

    def _safe_name(n: str) -> str:
        """Append '_' if n is a Python keyword (e.g. 'from' -> 'from_')."""
        return n + "_" if _kwmod.iskeyword(n) else n

    # First pass: required args (no default)
    for a in arg_specs:
        if a.required:
            sig_params.append(
                inspect.Parameter(_safe_name(a.name), kind, annotation=a.type_hint)
            )
    # Second pass: optional args (with default)
    for a in arg_specs:
        if not a.required:
            sig_params.append(
                inspect.Parameter(
                    _safe_name(a.name), kind, default=a.default, annotation=a.type_hint
                )
            )

    def _impl(**kwargs):
        # Map safe names back to original names for handler/template.
        orig_kwargs: dict[str, Any] = {}
        for a in arg_specs:
            sn = _safe_name(a.name)
            if sn in kwargs:
                orig_kwargs[a.name] = kwargs[sn]
            elif a.name in kwargs:
                orig_kwargs[a.name] = kwargs[a.name]

        # Validate required args.
        for a in arg_specs:
            if a.required and orig_kwargs.get(a.name) is None:
                return f"ERROR: missing required argument '{a.name}'"

        # Dispatch path 1: Python handler.
        if spec.handler is not None:
            try:
                return spec.handler(manager, orig_kwargs)
            except BackendError as exc:
                return f"ERROR: {exc}"

        # Dispatch path 2: render template + Tcl exec.
        try:
            cmd = spec.tcl_template.format(
                **{a.name: _to_tcl_value(orig_kwargs.get(a.name)) for a in arg_specs}
            )
        except KeyError as exc:
            return f"ERROR: missing argument {exc}"

        # Pick the backend.
        try:
            backend = manager.ensure_connected(
                spec.vendor if spec.vendor != "common" else None,
            )
        except BackendError as exc:
            return f"ERROR: {exc}"

        try:
            return backend.exec_tcl(cmd, timeout=spec.timeout)
        except BackendError as exc:
            return f"ERROR: {exc}"

    _impl.__doc__ = spec.docstring()
    _impl.__name__ = f"tool_{spec.name}"
    # Set the signature so FastMCP sees named parameters, not **kwargs.
    _impl.__signature__ = inspect.Signature(sig_params)  # type: ignore[attr-defined]
    # Attach arg specs so tests can introspect.
    _impl.__tool_spec__ = spec  # type: ignore[attr-defined]
    return _impl


def _to_tcl_value(v: Any) -> str:
    """Render a Python value as a Tcl-safe literal token.

    Strings get braced; None becomes the empty string; bools become 0/1;
    lists/tuples get rendered as a Tcl list.
    """
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, tuple)):
        from fpga_mcp.transports._tcl_helpers import tcl_list

        return tcl_list(v)
    s = str(v)
    from fpga_mcp.transports._tcl_helpers import tcl_quote

    return tcl_quote(s)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_specs(mcp, manager: BackendManager, specs: list[ToolSpec]) -> int:
    """Register every spec as a tool on the FastMCP server.

    Returns the number of tools registered (for assertion in tests).
    """
    n = 0
    for spec in specs:
        mcp.tool(name=spec.name, description=spec.summary)(_build_callable(spec, manager))
        n += 1
    return n


def register_all(mcp, manager: BackendManager) -> int:
    """Register every spec from every vendor catalogue.

    Returns the total number of tools registered. Tests assert this is ≥ 500.
    """
    from fpga_mcp.tool_defs.anlogic import SPECS as ANLOGIC_SPECS
    from fpga_mcp.tool_defs.common import SPECS as COMMON_SPECS
    from fpga_mcp.tool_defs.quartus import SPECS as QUARTUS_SPECS
    from fpga_mcp.tool_defs.vivado import SPECS as VIVADO_SPECS

    all_specs: list[ToolSpec] = []
    all_specs.extend(COMMON_SPECS)
    all_specs.extend(VIVADO_SPECS)
    all_specs.extend(QUARTUS_SPECS)
    all_specs.extend(ANLOGIC_SPECS)

    # Guard against accidental name collisions — they'd silently overwrite.
    seen: dict[str, ToolSpec] = {}
    for s in all_specs:
        if s.name in seen:
            raise RuntimeError(
                f"duplicate tool name '{s.name}' (defined in {seen[s.name].vendor} and {s.vendor})"
            )
        seen[s.name] = s

    return register_specs(mcp, manager, all_specs)
