"""Backend-agnostic contract for FPGA EDA tool drivers.

Every concrete transport (Vivado, Quartus, Anlogic) implements
:class:`EDABackend`. The MCP tools in :mod:`fpga_mcp.tools` call only
this interface, so adding a vendor = implementing this protocol once.

The result objects are plain dataclasses with a ``to_text`` helper so they can
be rendered for the LLM without further formatting layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class BackendError(RuntimeError):
    """Raised when a backend operation fails in a recoverable way."""


class BackendNotConnectedError(BackendError):
    """Raised when an operation requires a live tool session that is missing."""

    def __init__(self, backend: str, hint: str = "") -> None:
        super().__init__(
            f"backend '{backend}' is not connected. "
            f"Run `fpga-mcp setup` and `fpga-mcp doctor`. {hint}".strip()
        )


@dataclass
class ProjectHandle:
    """A handle to an opened EDA project.

    Path is the canonical project file (``.xpr`` / ``.qpf`` / ``.al``).
    ``meta`` is free-form backend-specific metadata (Vivado project GUID,
    Quartus revision, etc.).
    """

    path: Path
    name: str
    part: str
    backend: str
    top: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    """Generic run outcome for synth / impl / sim."""

    ok: bool
    stage: str
    log_path: Path | None = None
    duration_sec: float | None = None
    summary: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [f"[{self.stage}] ok={self.ok}"]
        if self.duration_sec is not None:
            lines.append(f"duration={self.duration_sec:.1f}s")
        if self.summary:
            lines.append(self.summary)
        if self.errors:
            lines.append("errors:")
            lines.extend(f"  - {e}" for e in self.errors[:20])
        if self.warnings:
            lines.append("warnings:")
            lines.extend(f"  - {w}" for w in self.warnings[:10])
        return "\n".join(lines)


@dataclass
class TimingPath:
    startpoint: str
    endpoint: str
    slack_ns: float
    path_group: str = "default"
    requirements_ns: float | None = None
    detail: str = ""

    @property
    def failing(self) -> bool:
        return self.slack_ns < 0.0


@dataclass
class TimingReport:
    wns_ns: float
    tns_ns: float
    whs_ns: float | None = None
    ths_ns: float | None = None
    failing_paths: list[TimingPath] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            f"WNS={self.wns_ns:+.3f}ns  TNS={self.tns_ns:+.3f}ns",
        ]
        if self.whs_ns is not None:
            lines.append(f"WHS={self.whs_ns:+.3f}ns  THS={self.ths_ns:+.3f}ns")
            lines.append("---")
        if not self.failing_paths:
            lines.append("no failing paths")
        else:
            lines.append(f"failing paths ({len(self.failing_paths)} shown):")
            for i, p in enumerate(self.failing_paths[:10], 1):
                lines.append(
                    f"  {i:2d}. {p.startpoint} -> {p.endpoint}  "
                    f"slack={p.slack_ns:+.3f}ns  group={p.path_group}"
                )
        return "\n".join(lines)


@dataclass
class UtilizationRow:
    resource: str
    used: int
    available: int
    util_pct: float

    def to_text(self) -> str:
        return f"  {self.resource:<20} {self.used:>8}/{self.available:<8} {self.util_pct:5.1f}%"


@dataclass
class UtilizationReport:
    rows: list[UtilizationRow] = field(default_factory=list)

    def to_text(self) -> str:
        if not self.rows:
            return "no utilization data"
        header = f"  {'Resource':<20} {'Used':>8}/{'Avail':<8} {'%':>5}"
        return "\n".join([header] + [r.to_text() for r in self.rows])


# Backwards-compatible alias. Project is the public type MCP tools talk about.
Project = ProjectHandle


@runtime_checkable
class EDABackend(Protocol):
    """Vendor-agnostic contract for FPGA EDA drivers."""

    name: str

    # --- lifecycle -----------------------------------------------------

    def connect(self) -> None:
        """Open / verify a live session with the EDA tool."""
        ...

    def disconnect(self) -> None:
        """Tear down any open session. Idempotent."""
        ...

    def is_connected(self) -> bool:
        """Return True iff the backend can immediately serve a command."""
        ...

    # --- project lifecycle --------------------------------------------

    def create_project(
        self,
        name: str,
        directory: Path,
        part: str,
        *,
        top: str | None = None,
        hdl: str = "verilog",
    ) -> ProjectHandle: ...

    def open_project(self, path: Path) -> ProjectHandle: ...

    def close_project(self) -> None: ...

    def current_project(self) -> ProjectHandle | None: ...

    # --- sources & constraints ----------------------------------------

    def add_sources(
        self,
        files: list[Path],
        *,
        library: str | None = None,
        include_dirs: list[Path] | None = None,
    ) -> int:
        """Add HDL source files to the active project. Returns count added."""
        ...

    def add_constraints(self, files: list[Path]) -> int: ...

    def set_top(self, top: str) -> None: ...

    # --- synthesis & implementation -----------------------------------

    def run_synthesis(self, *, force: bool = False) -> RunResult: ...

    def run_implementation(self, *, force: bool = False) -> RunResult: ...

    # --- IP / block design --------------------------------------------

    def create_ip(self, ip_name: str, *, name: str | None = None, **props: Any) -> str:
        """Instantiate a vendor IP. Returns the IP instance name."""
        ...

    def set_ip_property(self, ip_name: str, prop: str, value: Any) -> None: ...

    def generate_ip(self, ip_name: str) -> RunResult: ...

    # --- reports ------------------------------------------------------

    def report_timing(self, *, max_paths: int = 10) -> TimingReport: ...

    def report_utilization(self) -> UtilizationReport: ...

    # --- simulation ---------------------------------------------------

    def run_simulation(
        self,
        *,
        kind: str = "rtl",
        top: str | None = None,
        testbench: str | None = None,
        duration: str | None = None,
    ) -> RunResult:
        """Run a simulation. ``kind`` ∈ {"rtl","post_syn","post_impl"}."""
        ...

    # --- bitstream & device -------------------------------------------

    def generate_bitstream(self, *, include_ltx: bool = True) -> Path: ...

    def program_device(
        self,
        bitstream: Path,
        *,
        cable: str | None = None,
        device_index: int = 0,
    ) -> RunResult: ...

    # --- escape hatch -------------------------------------------------

    def exec_tcl(self, command: str, *, timeout: float | None = None) -> str:
        """Run a backend-native Tcl command and return raw output.

        This is the universal escape hatch — anything missing from the typed
        surface above can be done via raw Tcl. Each backend translates this
        to its own scripting entry point (Vivado socket / quartus_sh / TD).
        """
        ...
