"""Xilinx Vivado backend.

Talks to the bundled Tcl TCP server (``tcl/vivado_server.tcl``) over a local
socket. The Vivado process is owned by the user (they start it once in a
terminal or GUI tab); this backend just connects to port 9999 and drives it.

SynthPilot is the inspiration for the architecture; this code is written from
scratch under MIT and intentionally simpler/smaller. The big difference vs
SynthPilot: there is no closed-source edition gating, no proprietary licensing
layer — everything here ships open.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from fpga_mcp.config import Config
from fpga_mcp.transports._tcl_client import TclClient, TclClientError
from fpga_mcp.transports.base import (
    BackendError,
    BackendNotConnectedError,
    ProjectHandle,
    RunResult,
    TimingPath,
    TimingReport,
    UtilizationReport,
    UtilizationRow,
)
from fpga_mcp.transports.factory import register


def _tcl_list(items) -> str:
    """Quote a Python list as a Tcl list (whitespace-safe)."""
    return " ".join(_tcl_quote(str(i)) for i in items)


def _tcl_quote(s: str) -> str:
    """Vivado accepts `{...}` braced strings or `"..."` quoted strings.

    We use braces unless the string contains an unmatched brace, in which
    case we fall back to backslash-quoted double-quoted form.
    """
    s = s.replace(chr(92), "/")  # Windows backslashes to forward slashes for Tcl
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


class VivadoBackend:
    """Drives Xilinx Vivado over a local Tcl TCP server (port 9999)."""

    name = "vivado"

    def __init__(self, config: Config):
        self._config = config
        b = config.backends
        self._client = TclClient(
            host=b.vivado_host,
            port=b.vivado_port,
            connect_timeout=5.0,
            default_timeout=7200.0,  # 2h — long synth/impl runs
        )
        self._current: ProjectHandle | None = None

    # --- lifecycle ---------------------------------------------------

    def connect(self) -> None:
        try:
            self._client.connect()
        except (TclClientError, OSError) as exc:
            raise BackendNotConnectedError(
                self.name,
                hint=(
                    f"Could not reach Vivado Tcl server at "
                    f"{self._config.backends.vivado_host}:"
                    f"{self._config.backends.vivado_port}. Start it with:\n"
                    f"  vivado -mode tcl -source tcl/vivado_server.tcl\n"
                    f"Original error: {exc}"
                ),
            ) from exc

    def disconnect(self) -> None:
        self._client.disconnect()
        self._current = None

    def is_connected(self) -> bool:
        return self._client.is_connected()

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
        # -force lets us recreate; -in_memory is reserved for ephemeral runs.
        self._tcl(
            f"create_project -force -part {_tcl_quote(part)} "
            f"{_tcl_quote(name)} {_tcl_quote(str(directory))}"
        )
        # Default target_language so users don't have to specify it per file.
        lang = "VHDL" if hdl.lower().startswith("vhdl") else "Verilog"
        self._tcl(f"set_property target_language {_tcl_quote(lang)} [current_project]")
        if top:
            self._tcl(f"set_property top {_tcl_quote(top)} [current_fileset]")
        xpr = directory / f"{name}.xpr"
        h = ProjectHandle(path=xpr, name=name, part=part, backend=self.name, top=top)
        self._current = h
        return h

    def open_project(self, path: Path) -> ProjectHandle:
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise BackendError(f"project not found: {path}")
        self._tcl(f"open_project {_tcl_quote(str(path))}")
        name = path.stem
        part = self._safe_tcl("get_property PART [current_project]", default="")
        top = self._safe_tcl("get_property top [current_fileset]", default="") or None
        h = ProjectHandle(path=path, name=name, part=part or "", backend=self.name, top=top)
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
        # Ask Vivado whether a project is open.
        if self._safe_tcl("catch {current_project}", default="1") == "0":
            name = self._safe_tcl("current_project", default="")
            if name:
                part = self._safe_tcl("get_property PART [current_project]", default="")
                path = (
                    Path(self._safe_tcl("get_property DIRECTORY [current_project]", default="."))
                    / f"{name}.xpr"
                )
                self._current = ProjectHandle(
                    path=path,
                    name=name,
                    part=part or "",
                    backend=self.name,
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
        files_tcl = _tcl_list(files)
        cmd = f"add_files -norecurse -fileset [get_filesets sources_1] {files_tcl}"
        if library:
            cmd += f" -library {_tcl_quote(library)}"
        self._tcl(cmd)
        # Optionally import files (copy into the project dir)
        # — let users opt in via the include_dirs hint, which we don't use here.
        # Set Verilog include dirs if provided.
        if include_dirs:
            inc_tcl = _tcl_list([str(Path(d).resolve()) for d in include_dirs])
            self._tcl(
                "set_property include_dirs [list "
                + inc_tcl.replace("{", "").replace("}", "")
                + "] "
                "[get_filesets sources_1]"
            )
        return len(files)

    def add_constraints(self, files) -> int:
        files = [Path(f).expanduser().resolve() for f in files]
        if not files:
            return 0
        files_tcl = _tcl_list(files)
        self._tcl(f"add_files -norecurse -fileset [get_filesets constrs_1] {files_tcl}")
        return len(files)

    def set_top(self, top: str) -> None:
        self._tcl(f"set_property top {_tcl_quote(top)} [current_fileset]")
        self._tcl("update_compile_order -fileset [get_filesets sources_1]")
        if self._current:
            self._current.top = top

    # --- synthesis & implementation ---------------------------------

    def run_synthesis(self, *, force: bool = False) -> RunResult:
        self._require_project()
        if force:
            self._safe_tcl("reset_run synth_1")
        t0 = time.time()
        self._tcl("launch_runs synth_1 -jobs 8", timeout=7200.0)
        self._tcl("wait_on_run synth_1", timeout=7200.0)
        elapsed = time.time() - t0
        status = self._safe_tcl("get_property STATUS [get_runs synth_1]", default="")
        ok = "synth_design Complete" in status
        log = (
            Path(self._safe_tcl("get_property DIRECTORY [get_runs synth_1]", default="."))
            / "runme.log"
        )
        errors, warnings = self._parse_vivado_log(log)
        return RunResult(
            ok=ok,
            stage="synthesis",
            log_path=log if log.exists() else None,
            duration_sec=elapsed,
            summary=status,
            errors=errors,
            warnings=warnings,
        )

    def run_implementation(self, *, force: bool = False) -> RunResult:
        self._require_project()
        if force:
            self._safe_tcl("reset_run impl_1")
        t0 = time.time()
        self._tcl(
            "launch_runs impl_1 -to_step write_bitstream -jobs 8",
            timeout=14400.0,
        )
        self._tcl("wait_on_run impl_1", timeout=14400.0)
        elapsed = time.time() - t0
        status = self._safe_tcl("get_property STATUS [get_runs impl_1]", default="")
        ok = "route_design Complete" in status or "write_bitstream Complete" in status
        log = (
            Path(self._safe_tcl("get_property DIRECTORY [get_runs impl_1]", default="."))
            / "runme.log"
        )
        errors, warnings = self._parse_vivado_log(log)
        return RunResult(
            ok=ok,
            stage="implementation",
            log_path=log if log.exists() else None,
            duration_sec=elapsed,
            summary=status,
            errors=errors,
            warnings=warnings,
        )

    # --- IP ----------------------------------------------------------

    def create_ip(self, ip_name: str, *, name: str | None = None, **props) -> str:
        inst_name = name or f"{ip_name}_0"
        # Resolve version if user did not give one; use latest.
        version_tcl = ""
        # The set_property -dict CONFIG.* on the IP works without a version
        # only if we pin the IP version at create time. We attempt to read
        # the latest version from the IP catalog.
        latest = self._safe_tcl(
            f"get_ipdefs -name {_tcl_quote(ip_name)}",
            default="",
        )
        if latest:
            # First matching def — pick the highest version string.
            defs = latest.split()
            defs = sorted(defs, reverse=True)
            if defs:
                version_tcl = f" -version {_tcl_quote(defs[0])}"
        self._tcl(
            f"create_ip -name {_tcl_quote(ip_name)}{version_tcl} "
            f"-module_name {_tcl_quote(inst_name)}"
        )
        if props:
            # Pass props as a list of (key, value) pairs — `value` is ignored
            # when `prop` is not a str (see set_ip_property below).
            self.set_ip_property(inst_name, list(props.items()), None)
        return inst_name

    def set_ip_property(self, ip_name: str, prop, value) -> None:
        # Accept both ("prop", val) and [("p1","v1"),("p2","v2")] shapes.
        if isinstance(prop, str):
            pairs = [(prop, value)]
        else:
            pairs = list(prop)
        items = []
        for k, v in pairs:
            items.append(f"CONFIG.{k} {_tcl_quote(str(v))}")
        dict_tcl = "[list " + " ".join(items) + "]"
        self._tcl(f"set_property -dict {dict_tcl} [get_ips {_tcl_quote(ip_name)}]")

    def generate_ip(self, ip_name: str) -> RunResult:
        t0 = time.time()
        self._tcl(
            f"generate_target all [get_ips {_tcl_quote(ip_name)}]",
            timeout=1800.0,
        )
        self._tcl(
            f"synth_ip [get_ips {_tcl_quote(ip_name)}]",
            timeout=1800.0,
        )
        return RunResult(
            ok=True,
            stage="ip_synth",
            duration_sec=time.time() - t0,
            summary=f"generated IP {ip_name}",
        )

    # --- reports ----------------------------------------------------

    def report_timing(self, *, max_paths: int = 10) -> TimingReport:
        self._require_project()
        # Need an open design for timing. Prefer impl_1 then synth_1.
        self._open_a_run()
        out = self._tcl(f"report_timing_summary -return_string -max_paths {int(max_paths)}")
        wns, tns = self._extract_wns_tns(out)
        whs, ths = self._extract_whs_ths(out)
        paths = self._extract_failing_paths(out)
        return TimingReport(
            wns_ns=wns,
            tns_ns=tns,
            whs_ns=whs,
            ths_ns=ths,
            failing_paths=paths,
        )

    def report_utilization(self) -> UtilizationReport:
        self._require_project()
        self._open_a_run()
        out = self._tcl("report_utilization -return_string")
        rows: list[UtilizationRow] = []
        for m in re.finditer(
            r"^\|\s*([A-Za-z][\w /().-]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|",
            out,
            re.MULTILINE,
        ):
            try:
                used = int(m.group(2))
                avail = int(m.group(3))
                pct = float(m.group(4))
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
        self._require_project()
        kind = (kind or "rtl").lower()
        mode_map = {
            "rtl": "behavioral",
            "post_syn": "post-synthesis",
            "post_impl": "timing",
        }
        mode = mode_map.get(kind, "behavioral")
        top_name = top or testbench or self._current.top if self._current else top
        if not top_name:
            return RunResult(
                ok=False,
                stage="simulation",
                errors=["no top-level testbench specified"],
            )
        cmd = f"launch_simulation -mode {_tcl_quote(mode)} -type {_tcl_quote('all')} "
        # We can't specify top directly in launch_simulation — top is the
        # fileset's `top` property. So set it first.
        self._tcl(f"set_property top {_tcl_quote(top_name)} [get_filesets sim_1]")
        t0 = time.time()
        try:
            self._tcl(cmd, timeout=1800.0)
        except TclClientError as exc:
            return RunResult(
                ok=False,
                stage="simulation",
                duration_sec=time.time() - t0,
                errors=[str(exc)],
            )
        return RunResult(
            ok=True,
            stage="simulation",
            duration_sec=time.time() - t0,
            summary=f"simulated {top_name} (mode={mode})"
            + (f" for {duration}" if duration else ""),
        )

    # --- bitstream & device ----------------------------------------

    def generate_bitstream(self, *, include_ltx: bool = True) -> Path:
        self._require_project()
        # write_bitstream step is part of impl_1 in our flow; if it has not
        # run yet, do it now via reset_run impl_1 -from_step write_bitstream.
        # Otherwise just locate the .bit produced.
        self._tcl(
            "launch_runs impl_1 -to_step write_bitstream -jobs 8",
            timeout=14400.0,
        )
        self._tcl("wait_on_run impl_1", timeout=14400.0)
        proj_dir = Path(self._safe_tcl("get_property DIRECTORY [current_project]", default="."))
        name = self._current.name if self._current else "top"
        bit = proj_dir / f"{name}.runs" / "impl_1" / f"{self._current.top or name}.bit"
        if not bit.exists():
            # Fallback: search impl_1 dir for any .bit
            impl_dir = proj_dir / f"{name}.runs" / "impl_1"
            matches = list(impl_dir.glob("*.bit"))
            bit = matches[0] if matches else bit
        if not bit.exists():
            raise BackendError(f"bitstream not found after write_bitstream: {bit}")
        return bit

    def program_device(
        self, bitstream: Path, *, cable: str | None = None, device_index: int = 0
    ) -> RunResult:
        bitstream = Path(bitstream).expanduser().resolve()
        if not bitstream.exists():
            raise BackendError(f"bitstream not found: {bitstream}")
        t0 = time.time()
        self._tcl("open_hw_manager")
        # Open the first available target if not already open.
        if self._safe_tcl("get_hw_targets") == "":
            self._tcl("open_hw_target")
        # Pick the requested device.
        devices = self._safe_tcl("get_hw_devices", default="").split()
        if not devices:
            return RunResult(
                ok=False,
                stage="program",
                errors=["no hw devices found via JTAG"],
            )
        if device_index >= len(devices):
            return RunResult(
                ok=False,
                stage="program",
                errors=[
                    f"device_index {device_index} out of range ({len(devices)} devices available)"
                ],
            )
        dev = devices[device_index]
        ltx = bitstream.with_suffix(".ltx")
        self._tcl(
            f"set_property PROGRAM.FILE {{ {_tcl_quote(str(bitstream))} }} "
            f"[get_hw_devices {_tcl_quote(dev)}]"
        )
        if ltx.exists():
            self._tcl(
                f"set_property PROBES.FILE {{ {_tcl_quote(str(ltx))} }} "
                f"[get_hw_devices {_tcl_quote(dev)}]"
            )
        self._tcl(f"program_hw_devices [get_hw_devices {_tcl_quote(dev)}]")
        return RunResult(
            ok=True,
            stage="program",
            duration_sec=time.time() - t0,
            summary=f"programmed {bitstream.name} into {dev}",
        )

    # --- escape hatch -----------------------------------------------

    def exec_tcl(self, command: str, *, timeout: float | None = None) -> str:
        return self._tcl(command, timeout=timeout)

    # --- internals --------------------------------------------------

    def _tcl(self, command: str, *, timeout: float | None = None) -> str:
        if not self.is_connected():
            # Best-effort auto-reconnect for transient drops.
            try:
                self.connect()
            except BackendError:
                raise
        return self._client.request(command, timeout=timeout)

    def _safe_tcl(self, command: str, default: str = "") -> str:
        wrapped = (
            "if {[catch {" + command + "} rc opt]} {set rc " + _tcl_quote(default) + "}; return $rc"
        )
        try:
            return self._tcl(wrapped).strip()
        except TclClientError:
            return default

    def _require_project(self) -> None:
        if self.current_project() is None:
            raise BackendError(
                "no active Vivado project — call create_project or open_project first"
            )

    def _open_a_run(self) -> None:
        # Idempotent: if a design is already open, skip.
        if (
            self._safe_tcl("catch {current_design}") == "0"
            and self._safe_tcl("current_design", default="") != ""
        ):
            return
        # Prefer impl_1, fall back to synth_1.
        if self._safe_tcl("get_property STATUS [get_runs impl_1]", default="").startswith(
            "write_bitstream"
        ):
            self._safe_tcl("open_run impl_1")
        else:
            self._safe_tcl("open_run synth_1")

    def _parse_vivado_log(self, log: Path) -> tuple[list[str], list[str]]:
        if not log.exists():
            return [], []
        text = log.read_text(encoding="utf-8", errors="replace")
        errors = [m.group(0) for m in re.finditer(r"^ERROR: \[.*$", text, re.MULTILINE)]
        warnings = [m.group(0) for m in re.finditer(r"^WARNING: \[.*$", text, re.MULTILINE)][:20]
        return errors, warnings

    @staticmethod
    def _extract_wns_tns(report: str) -> tuple[float, float]:
        # Vivado prints a table like:
        #   Design Timing Summary
        #   | Clock        | WNS(ns) | TNS(ns) |
        #   |-------------|---------|---------|
        #   | clk          |  +2.341 |   0.000 |
        # ...
        # The overall WNS/TNS appears in the "Design Timing Summary" block.
        m = re.search(
            r"WNS\(ns\).*?TNS\(ns\).*?\n(\|[^\n]*\|)\s*\n(\|[^\n]*\|)",
            report,
            re.DOTALL,
        )
        if not m:
            return 0.0, 0.0
        # Take the first data row.
        row = re.findall(r"[-+]?\d+\.\d+", m.group(2))
        if len(row) < 2:
            return 0.0, 0.0
        try:
            return float(row[0]), float(row[1])
        except ValueError:
            return 0.0, 0.0

    @staticmethod
    def _extract_whs_ths(report: str) -> tuple[float | None, float | None]:
        m = re.search(
            r"WHS\(ns\).*?THS\(ns\).*?\n(\|[^\n]*\|)\s*\n(\|[^\n]*\|)",
            report,
            re.DOTALL,
        )
        if not m:
            return None, None
        row = re.findall(r"[-+]?\d+\.\d+", m.group(2))
        if len(row) < 2:
            return None, None
        try:
            return float(row[0]), float(row[1])
        except ValueError:
            return None, None

    @staticmethod
    def _extract_failing_paths(report: str) -> list[TimingPath]:
        # Very lightweight: scan for "Slack (VIOLATED)" lines.
        paths: list[TimingPath] = []
        for m in re.finditer(
            r"Slack\s*\(\s*VIOLATED\s*\)\s+([-+]?\d+\.\d+)ns",
            report,
        ):
            slack = float(m.group(1))
            paths.append(
                TimingPath(
                    startpoint="<unknown>",
                    endpoint="<unknown>",
                    slack_ns=slack,
                )
            )
        return paths[:10]


register("vivado", VivadoBackend)
