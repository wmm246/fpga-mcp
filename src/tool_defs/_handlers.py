"""Python handlers for the high-level common tools.

These tools don't map to a single Tcl command — they call backend-specific
Python API methods on the active :class:`~fpga_mcp.transports.base.EDABackend`.
Each handler takes ``(manager, kwargs)`` and returns a string result.

Used by :mod:`fpga_mcp.tool_defs.common` to attach the same Python behaviour
that previously lived in the old ``fpga_mcp/tools/`` directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fpga_mcp.session import BackendManager
from fpga_mcp.transports.base import BackendError


def _backend(manager: BackendManager, name: str | None = None):
    """Return the connected backend, raising BackendError on failure."""
    return manager.ensure_connected(name)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


def list_backends(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    names = manager.available()
    out = ["Available backends:"]
    for n in names:
        mark = " (active)" if n == manager.active_name else ""
        out.append(f"- {n}{mark}")
    return "\n".join(out)


def set_backend(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    name = kwargs["name"]
    try:
        return manager.switch(name)
    except BackendError as exc:
        return f"ERROR: {exc}"


def ping_backend(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    name = kwargs.get("name") or ""
    backend_name = name or manager.active_name
    try:
        backend = manager.ensure_connected(backend_name)
        ok = backend.is_connected()
        return f"{backend_name}: {'connected' if ok else 'not connected'}"
    except BackendError as exc:
        return f"{backend_name}: NOT connected\n\n{exc}"


def status(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    snap = manager.status()
    return json.dumps(snap, indent=2, default=str)


def exec_tcl(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    command = kwargs["command"]
    timeout = float(kwargs.get("timeout") or 600.0)
    backend = _backend(manager)
    return backend.exec_tcl(command, timeout=timeout)


# ---------------------------------------------------------------------------
# Project lifecycle
# ---------------------------------------------------------------------------


def create_project(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    name = kwargs["name"]
    part = kwargs["part"]
    directory = kwargs.get("directory") or "."
    top = kwargs.get("top") or ""
    hdl = kwargs.get("hdl") or "verilog"
    backend = _backend(manager)
    h = backend.create_project(
        name,
        Path(directory),
        part,
        top=top or None,
        hdl=hdl,
    )
    extra = f" (top={h.top})" if h.top else ""
    return f"Created {backend.name} project '{name}' at {h.path} (part={part}){extra}"


def open_project(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    path = kwargs["path"]
    backend = _backend(manager)
    h = backend.open_project(Path(path))
    return (
        f"Opened {backend.name} project '{h.name}' "
        f"(part={h.part or 'unknown'}, top={h.top or 'unset'})"
    )


def close_project(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    backend = _backend(manager)
    backend.close_project()
    return f"Closed project on {backend.name}"


def current_project(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    backend = _backend(manager)
    h = backend.current_project()
    if h is None:
        return f"{backend.name}: no project open"
    return (
        f"{backend.name} project '{h.name}'\n"
        f"  path: {h.path}\n"
        f"  part: {h.part}\n"
        f"  top:  {h.top or '(unset)'}"
    )


def add_sources(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    files = kwargs.get("files") or []
    if isinstance(files, str):
        files = [files]
    if not files:
        return "ERROR: no files provided"
    library = kwargs.get("library") or ""
    include_dirs = kwargs.get("include_dirs") or None
    backend = _backend(manager)
    n = backend.add_sources(
        [Path(f) for f in files],
        library=library or None,
        include_dirs=[Path(d) for d in include_dirs] if include_dirs else None,
    )
    return f"Added {n} source file(s) to {backend.name} project"


def add_constraints(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    files = kwargs.get("files") or []
    if isinstance(files, str):
        files = [files]
    if not files:
        return "ERROR: no files provided"
    backend = _backend(manager)
    n = backend.add_constraints([Path(f) for f in files])
    return f"Added {n} constraint file(s) to {backend.name} project"


def set_top(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    top = kwargs["top"]
    backend = _backend(manager)
    backend.set_top(top)
    return f"Top set to '{top}' on {backend.name}"


# ---------------------------------------------------------------------------
# Flow
# ---------------------------------------------------------------------------


def run_synthesis(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    force = bool(kwargs.get("force", False))
    backend = _backend(manager)
    r = backend.run_synthesis(force=force)
    return r.to_text()


def run_implementation(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    force = bool(kwargs.get("force", False))
    backend = _backend(manager)
    r = backend.run_implementation(force=force)
    return r.to_text()


def run_simulation(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    top = kwargs.get("top") or ""
    kind = kwargs.get("kind") or "rtl"
    duration = kwargs.get("duration") or ""
    backend = _backend(manager)
    r = backend.run_simulation(top=top or None, kind=kind, duration=duration)
    return r.to_text()


def generate_bitstream(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    include_ltx = bool(kwargs.get("include_ltx", True))
    backend = _backend(manager)
    bit = backend.generate_bitstream(include_ltx=include_ltx)
    return f"Generated bitstream at {bit} on {backend.name}"


def program_device(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    bitstream = kwargs["bitstream"]
    cable = kwargs.get("cable") or ""
    device_index = int(kwargs.get("device_index") or 0)
    backend = _backend(manager)
    r = backend.program_device(
        Path(bitstream),
        cable=cable or None,
        device_index=device_index,
    )
    return r.to_text()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def report_timing(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    max_paths = int(kwargs.get("max_paths") or 10)
    backend = _backend(manager)
    r = backend.report_timing(max_paths=max_paths)
    return r.to_text()


def report_utilization(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    backend = _backend(manager)
    r = backend.report_utilization()
    return r.to_text()


# ---------------------------------------------------------------------------
# IP
# ---------------------------------------------------------------------------


def create_ip(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    ip_name = kwargs["ip_name"]
    name = kwargs.get("name") or ""
    properties = kwargs.get("properties") or None
    backend = _backend(manager)
    if isinstance(properties, dict):
        inst_name = backend.create_ip(ip_name, name=name or None, **properties)
    else:
        inst_name = backend.create_ip(ip_name, name=name or None)
    return f"Created IP '{ip_name}' as '{inst_name}' on {backend.name}"


def set_ip_property(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    ip_name = kwargs["ip_name"]
    property_name = kwargs["property_name"]
    value = kwargs["value"]
    backend = _backend(manager)
    backend.set_ip_property(ip_name, property_name, value)
    return f"Set {ip_name}.{property_name} = {value!r}"


def generate_ip(manager: BackendManager, kwargs: dict[str, Any]) -> str:
    ip_name = kwargs["ip_name"]
    backend = _backend(manager)
    backend.generate_ip(ip_name)
    return f"Generated IP '{ip_name}' on {backend.name}"
