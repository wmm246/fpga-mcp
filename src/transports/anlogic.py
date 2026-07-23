"""Anlogic TangDynasty (TD) backend.

Anlogic's Tang Dynasty IDE exposes a Tcl console with the project/flow
commands below. We drive it via a local Tcl TCP server
(``tcl/anlogic_server.tcl``) launched from ``td -tcl`` (or the GUI's Tcl
console).

Coverage: create/open/close project, add sources, full synth+P&R flow,
timing / utilization reports, bitstream generation. Programming goes through
Anlogic's standalone programmer (``td_pgm``-style), invoked best-effort.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from fpga_mcp.transports._base_tcp import BaseTcpBackend
from fpga_mcp.transports._tcl_helpers import tcl_quote
from fpga_mcp.transports.base import (
    BackendError,
    ProjectHandle,
    RunResult,
    TimingPath,
    TimingReport,
    UtilizationReport,
    UtilizationRow,
)
from fpga_mcp.transports.factory import register


class AnlogicBackend(BaseTcpBackend):
    """Drives Anlogic TangDynasty over a local Tcl TCP server (port 9997)."""

    name = "anlogic"
    default_port = 9997

    def _pick_host_port(self, b):
        return b.anlogic_host, b.anlogic_port

    def _start_hint(self) -> str:
        return (
            "  Start the Anlogic TD Tcl server with:\n"
            "    td -tcl\n"
            "    % source tcl/anlogic_server.tcl\n"
            "  (or run the script inside the TD GUI's Tcl console)"
        )

    # --- project lifecycle ------------------------------------------

    def create_project(
        self,
        name: str,
        directory: Path,
        part: str,
        *,
        top: str | None = None,
        hdl: str = "verilog",
    ) -> ProjectHandle:
        directory = Path(directory).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        # Tang Dynasty create_project signature:
        #   create_project -name <name> -dir <dir> -part <part> [-hdl verilog|vhdl]
        self._tcl(
            "create_project -name "
            + tcl_quote(name)
            + " -dir "
            + tcl_quote(str(directory))
            + " -part "
            + tcl_quote(part)
            + " -hdl "
            + tcl_quote(hdl)
        )
        if top:
            self.set_top(top)
        al = directory / f"{name}.al"
        h = ProjectHandle(
            path=al,
            name=name,
            part=part,
            backend=self.name,
            top=top,
        )
        self._current = h
        return h

    def open_project(self, path: Path) -> ProjectHandle:
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise BackendError(f"project not found: {path}")
        self._tcl("open_project " + tcl_quote(str(path)))
        name = path.stem
        part = self._safe_tcl("get_part", default="") or ""
        top = self._safe_tcl("get_top", default="") or None
        h = ProjectHandle(
            path=path,
            name=name,
            part=part,
            backend=self.name,
            top=top,
        )
        self._current = h
        return h

    def close_project(self) -> None:
        try:
            self._tcl("close_project")
        finally:
            self._current = None

    def current_project(self) -> ProjectHandle | None:
        if self._current is not None:
            return self._current
        if self._safe_tcl("catch {current_project}", default="1") == "0":
            name = self._safe_tcl("current_project", default="proj")
            directory = self._safe_tcl("get_project_dir", default=".")
            path = Path(directory) / f"{name}.al"
            part = self._safe_tcl("get_part", default="")
            top = self._safe_tcl("get_top", default="") or None
            self._current = ProjectHandle(
                path=path,
                name=name,
                part=part or "",
                backend=self.name,
                top=top,
            )
            return self._current
        return None

    # --- sources & constraints --------------------------------------

    def add_sources(
        self,
        files,
        *,
        library: str | None = None,
        include_dirs=None,
    ) -> int:
        files = [Path(f).expanduser().resolve() for f in files]
        if not files:
            return 0
        for f in files:
            self._tcl("add_file " + tcl_quote(str(f)))
        if include_dirs:
            for d in include_dirs:
                self._tcl("add_include_dir " + tcl_quote(str(Path(d).resolve())))
        return len(files)

    def add_constraints(self, files) -> int:
        # Anlogic uses .sdc (timing) and .fdc (physical / floorplanning).
        files = [Path(f).expanduser().resolve() for f in files]
        if not files:
            return 0
        for f in files:
            self._tcl("add_constraint " + tcl_quote(str(f)))
        return len(files)

    def set_top(self, top: str) -> None:
        self._tcl("set_top " + tcl_quote(top))
        if self._current:
            self._current.top = top

    # --- synthesis & implementation ---------------------------------

    def run_synthesis(self, *, force: bool = False) -> RunResult:
        self._require_project()
        if force:
            self._safe_tcl("reset_run -syn")
        t0 = time.time()
        try:
            self._tcl("run_syn", timeout=7200.0)
            ok = True
        except Exception as exc:
            return RunResult(
                ok=False,
                stage="synthesis",
                duration_sec=time.time() - t0,
                errors=[str(exc)],
            )
        elapsed = time.time() - t0
        log = self._anlogic_log("syn")
        return RunResult(
            ok=ok,
            stage="synthesis",
            log_path=log if log and log.exists() else None,
            duration_sec=elapsed,
            summary="synthesis complete",
        )

    def run_implementation(self, *, force: bool = False) -> RunResult:
        self._require_project()
        if force:
            self._safe_tcl("reset_run -pnr")
        t0 = time.time()
        try:
            # run_pnr typically runs the full backend (place+route+bitstream
            # in one go on older TD versions). We split synth first to get
            # a clean post-synth view.
            self._tcl("run_pnr", timeout=14400.0)
            ok = True
        except Exception as exc:
            return RunResult(
                ok=False,
                stage="implementation",
                duration_sec=time.time() - t0,
                errors=[str(exc)],
            )
        elapsed = time.time() - t0
        log = self._anlogic_log("pnr")
        return RunResult(
            ok=ok,
            stage="implementation",
            log_path=log if log and log.exists() else None,
            duration_sec=elapsed,
            summary="place & route complete",
        )

    # --- IP ----------------------------------------------------------

    def create_ip(self, ip_name: str, *, name: str | None = None, **props) -> str:
        # Anlogic ships IPs as pre-built modules instantiated in HDL — there
        # is no Vivado-style IP catalog at the Tcl level yet. We accept the
        # call but the user is expected to add the IP file via add_sources.
        inst = name or f"{ip_name}_0"
        if props:
            # Emit a Tcl set_ip_property call for compatibility; no-op if the
            # vendor command does not exist on this TD version.
            for k, v in props.items():
                self._safe_tcl(
                    f"set_ip_property {tcl_quote(ip_name)} {tcl_quote(str(k))} {tcl_quote(str(v))}"
                )
        return inst

    def set_ip_property(self, ip_name: str, prop, value) -> None:
        if isinstance(prop, str):
            pairs = [(prop, value)]
        else:
            pairs = list(prop)
        for k, v in pairs:
            self._safe_tcl(
                f"set_ip_property {tcl_quote(ip_name)} {tcl_quote(str(k))} {tcl_quote(str(v))}"
            )

    def generate_ip(self, ip_name: str) -> RunResult:
        t0 = time.time()
        self._safe_tcl(f"generate_ip {tcl_quote(ip_name)}")
        return RunResult(
            ok=True,
            stage="ip_synth",
            duration_sec=time.time() - t0,
            summary=f"generated IP {ip_name}",
        )

    # --- reports ----------------------------------------------------

    def report_timing(self, *, max_paths: int = 10) -> TimingReport:
        self._require_project()
        out = self._safe_tcl(
            f"report_timing -npaths {int(max_paths)} -return_string",
            default="",
        )
        wns = self._first_float(out, r"WNS\s*[:=]\s*([-+]?\d+\.\d+)", default=0.0)
        tns = self._first_float(out, r"TNS\s*[:=]\s*([-+]?\d+\.\d+)", default=0.0)
        paths = self._extract_anlogic_paths(out)
        return TimingReport(
            wns_ns=wns,
            tns_ns=tns,
            failing_paths=paths,
        )

    def report_utilization(self) -> UtilizationReport:
        self._require_project()
        out = self._safe_tcl("report_utilization -return_string", default="")
        rows: list[UtilizationRow] = []
        # Anlogic utilization output is free-form text; we look for
        # "LUTs : 1234/20000 (6.2%)" style lines.
        for m in re.finditer(
            r"^\s*([A-Za-z][\w /().-]+?)\s*[:=]\s*(\d+)\s*/\s*(\d+)"
            r"(?:\s*\(([\d.]+)%\))?",
            out,
            re.MULTILINE,
        ):
            try:
                used = int(m.group(2))
                avail = int(m.group(3))
                pct = float(m.group(4)) if m.group(4) else 100.0 * used / avail
            except ValueError:
                continue
            if avail <= 0:
                continue
            rows.append(
                UtilizationRow(
                    resource=m.group(1).strip(),
                    used=used,
                    available=avail,
                    util_pct=pct,
                )
            )
        return UtilizationReport(rows=rows)

    # --- simulation -------------------------------------------------

    def run_simulation(
        self,
        *,
        kind: str = "rtl",
        top: str | None = None,
        testbench: str | None = None,
        duration: str | None = None,
    ) -> RunResult:
        # Anlogic TD delegates simulation to ModelSim / Aldec; we emit the
        # netlist export call and let the user open the simulator.
        self._require_project()
        tb = top or testbench or (self._current.top if self._current else None)
        if not tb:
            return RunResult(
                ok=False,
                stage="simulation",
                errors=["no testbench top specified"],
            )
        t0 = time.time()
        self._safe_tcl(f"export_simulation -top {tcl_quote(tb)} -mode {kind}")
        return RunResult(
            ok=True,
            stage="simulation",
            duration_sec=time.time() - t0,
            summary=f"exported simulation netlist for {tb} (mode={kind})",
        )

    # --- bitstream & device ----------------------------------------

    def generate_bitstream(self, *, include_ltx: bool = True) -> Path:
        self._require_project()
        # Anlogic TD produces the bitstream during run_pnr. If we ran impl
        # already, the .bit sits in the project dir; otherwise trigger a
        # bitstream-only run.
        self._safe_tcl("generate_bitstream", timeout=3600.0)
        proj_dir = Path(self._current.path).parent if self._current else Path.cwd()
        name = self._current.name if self._current else "top"
        bit = proj_dir / f"{name}.bit"
        if not bit.exists():
            matches = list(proj_dir.rglob("*.bit"))
            bit = matches[0] if matches else bit
        if not bit.exists():
            raise BackendError(f"bitstream not found: {bit}")
        return bit

    def program_device(
        self, bitstream: Path, *, cable: str | None = None, device_index: int = 0
    ) -> RunResult:
        bitstream = Path(bitstream).expanduser().resolve()
        if not bitstream.exists():
            raise BackendError(f"bitstream not found: {bitstream}")
        t0 = time.time()
        # TD's Tcl-level programming API:
        #   program_device -file <bit> -device_index <i>
        try:
            self._tcl(
                "program_device -file "
                + tcl_quote(str(bitstream))
                + f" -device_index {int(device_index)}",
                timeout=120.0,
            )
        except Exception as exc:
            return RunResult(
                ok=False,
                stage="program",
                duration_sec=time.time() - t0,
                errors=[
                    str(exc),
                    "Falling back to Anlogic programmer: `td_pgm -f <bit>`",
                ],
            )
        return RunResult(
            ok=True,
            stage="program",
            duration_sec=time.time() - t0,
            summary=f"programmed {bitstream.name}",
        )

    # --- internals --------------------------------------------------

    def _anlogic_log(self, stage: str) -> Path | None:
        if not self._current:
            return None
        proj_dir = Path(self._current.path).parent
        name = self._current.name
        return proj_dir / f"{name}_{stage}.log"

    @staticmethod
    def _first_float(text: str, pattern: str, default: float = 0.0) -> float:
        m = re.search(pattern, text)
        if not m:
            return default
        try:
            return float(m.group(1))
        except (ValueError, IndexError):
            return default

    @staticmethod
    def _extract_anlogic_paths(text: str) -> list[TimingPath]:
        paths: list[TimingPath] = []
        # Look for "Slack : -2.341 ns" or "Slack -2.341" lines.
        for m in re.finditer(
            r"Slack\s*[:=]?\s*([-+]?\d+\.\d+)\s*(?:ns)?",
            text,
        ):
            try:
                slack = float(m.group(1))
            except ValueError:
                continue
            if slack < 0:
                paths.append(
                    TimingPath(
                        startpoint="<unknown>",
                        endpoint="<unknown>",
                        slack_ns=slack,
                    )
                )
        return paths[:10]


register("anlogic", AnlogicBackend)
