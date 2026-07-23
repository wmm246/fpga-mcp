"""Intel Quartus backend.

Drives Quartus Prime / Quartus II over a local Tcl TCP server
(``tcl/quartus_server.tcl``) launched from ``quartus_sh``. The Quartus Tcl
shell ships the standard ``quartus::project``, ``quartus::flow`` and
``quartus::sta`` packages, which is all we need.

Commands implemented here are the canonical Quartus Tcl API — no Quartus
versions newer than 2018 are required; older ones are best-effort.
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


# Mapping from common short families to the canonical Quartus FAMILY string.
_QUARTUS_FAMILIES = {
    # Intel / Altera family aliases — case-insensitive lookup.
    "cyclone": "Cyclone",
    "cyclone ii": "Cyclone II",
    "cyclone iii": "Cyclone III",
    "cyclone iv": "Cyclone IV",
    "cyclone v": "Cyclone V",
    "cyclone 10 lp": "Cyclone 10 LP",
    "cyclone 10 gx": "Cyclone 10 GX",
    "arria": "Arria",
    "arria 10": "Arria 10",
    "stratix": "Stratix",
    "stratix 10": "Stratix 10",
    "max 10": "MAX 10",
    "max ii": "MAX II",
}


def _resolve_family(part: str) -> str:
    """Infer the Quartus family name from a part string.

    Quartus requires both -name FAMILY and -name DEVICE for the project.
    The device string already encodes the family, so this is mostly a table
    lookup. Unknown families fall back to the prefix before the first digit.
    """
    key = part.lower()
    if key in _QUARTUS_FAMILIES:
        return _QUARTUS_FAMILIES[key]
    for k, v in _QUARTUS_FAMILIES.items():
        if key.startswith(k):
            return v
    # Last-resort heuristic: text before the first digit, e.g. "5CGX..." -> "5"
    m = re.match(r"^([A-Za-z]+)", part)
    if m:
        fam = m.group(1)
        # Uppercase first letter for nicer logging only; Quartus is case-fold.
        return fam[0].upper() + fam[1:].lower()
    return "Cyclone V"


class QuartusBackend(BaseTcpBackend):
    """Drives Intel Quartus over a local Tcl TCP server (port 9998)."""

    name = "quartus"
    default_port = 9998

    def _pick_host_port(self, b):
        return b.quartus_host, b.quartus_port

    def _start_hint(self) -> str:
        return (
            "  Start the Quartus Tcl server with:\n"
            "    quartus_sh -t tcl/quartus_server.tcl\n"
            "  (or inside quartus_sh -s:  source tcl/quartus_server.tcl)"
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
        family = _resolve_family(part)
        self._tcl(
            "cd " + tcl_quote(str(directory)) + "; "
            f"project_new -name {tcl_quote(name)} -family {tcl_quote(family)} "
            f"-part {tcl_quote(part)} -overwrite"
        )
        self._tcl(f"set_global_assignment -name FAMILY {tcl_quote(family)}")
        self._tcl(f"set_global_assignment -name DEVICE {tcl_quote(part)}")
        if top:
            self._tcl("set_global_assignment -name TOP_LEVEL_ENTITY " + tcl_quote(top))
        qpf = directory / f"{name}.qpf"
        h = ProjectHandle(
            path=qpf,
            name=name,
            part=part,
            backend=self.name,
            top=top,
            meta={"family": family},
        )
        self._current = h
        return h

    def open_project(self, path: Path) -> ProjectHandle:
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise BackendError(f"project not found: {path}")
        self._tcl("cd " + tcl_quote(str(path.parent)) + "; project_open " + tcl_quote(path.stem))
        name = path.stem
        part = self._safe_tcl("get_global_assignment -name DEVICE", default="")
        top = self._safe_tcl("get_global_assignment -name TOP_LEVEL_ENTITY", default="") or None
        family = self._safe_tcl("get_global_assignment -name FAMILY", default="")
        h = ProjectHandle(
            path=path,
            name=name,
            part=part or "",
            backend=self.name,
            top=top,
            meta={"family": family},
        )
        self._current = h
        return h

    def close_project(self) -> None:
        try:
            self._tcl("project_close")
        finally:
            self._current = None

    def current_project(self) -> ProjectHandle | None:
        if self._current is not None:
            return self._current
        # Quartus exposes is_project_open as a Tcl command.
        if self._safe_tcl("is_project_open", default="0") == "1":
            name = self._safe_tcl("get_current_revision", default="proj")
            directory = self._safe_tcl("pwd", default=".")
            path = Path(directory) / f"{name}.qpf"
            part = self._safe_tcl("get_global_assignment -name DEVICE", default="")
            top = self._safe_tcl("get_global_assignment -name TOP_LEVEL_ENTITY", default="") or None
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
            ext = f.suffix.lower()
            key = {
                ".v": "VERILOG_FILE",
                ".sv": "SYSTEMVERILOG_FILE",
                ".vhd": "VHDL_FILE",
                ".vh": "VERILOG_INCLUDE_FILE",
                ".vhdl": "VHDL_FILE",
            }.get(ext, "VERILOG_FILE")
            self._tcl(f"set_global_assignment -name {key} {tcl_quote(str(f))}")
        if include_dirs:
            joined = ";".join(str(Path(d).resolve()) for d in include_dirs)
            self._tcl("set_global_assignment -name SEARCH_PATH " + tcl_quote(joined))
        return len(files)

    def add_constraints(self, files) -> int:
        files = [Path(f).expanduser().resolve() for f in files]
        if not files:
            return 0
        for f in files:
            # SDC for timing; QSF for full assignments (rare to add raw).
            key = "SDC_FILE" if f.suffix.lower() == ".sdc" else "QSF_FILE"
            self._tcl(f"set_global_assignment -name {key} {tcl_quote(str(f))}")
        return len(files)

    def set_top(self, top: str) -> None:
        self._tcl("set_global_assignment -name TOP_LEVEL_ENTITY " + tcl_quote(top))
        if self._current:
            self._current.top = top

    # --- synthesis & implementation ---------------------------------

    def run_synthesis(self, *, force: bool = False) -> RunResult:
        self._require_project()
        # Map tool = Analysis & Synthesis. Use -tool map in execute_module.
        if force:
            # Quartus has no clean "reset_run"; re-running map overwrites.
            pass
        t0 = time.time()
        ok = self._run_module("map", "synthesis")
        elapsed = time.time() - t0
        log = self._quartus_log("map")
        return RunResult(
            ok=ok,
            stage="synthesis",
            log_path=log if log and log.exists() else None,
            duration_sec=elapsed,
            summary="map" if ok else "map failed",
        )

    def run_implementation(self, *, force: bool = False) -> RunResult:
        self._require_project()
        t0 = time.time()
        ok_map = self._run_module("map", "synthesis")
        ok_fit = self._run_module("fit", "fitter") if ok_map else False
        ok_asm = self._run_module("asm", "assembler") if ok_fit else False
        ok_sta = self._run_module("sta", "timing") if ok_fit else False
        elapsed = time.time() - t0
        stages = []
        if not ok_map:
            stages.append("map failed")
        if not ok_fit:
            stages.append("fit failed")
        if not ok_asm:
            stages.append("asm failed")
        if not ok_sta:
            stages.append("sta failed")
        return RunResult(
            ok=ok_fit and ok_asm,
            stage="implementation",
            log_path=self._quartus_log("fit"),
            duration_sec=elapsed,
            summary=" | ".join(stages) if stages else "fit+asm+sta complete",
        )

    # --- IP ----------------------------------------------------------

    def create_ip(self, ip_name: str, *, name: str | None = None, **props) -> str:
        # Quartus IP is created via qsys / IP Catalog, which has its own flow.
        # We emit the qsys-generate command; users with custom IP can use
        # the escape hatch.
        inst = name or f"{ip_name}_0"
        out_file = (
            Path(self._current.path).parent / f"{inst}.qsys"
            if self._current
            else Path.cwd() / f"{inst}.qsys"
        )
        # Use qsys-script if available; otherwise the user runs it manually.
        self._tcl(f"qsys-create {tcl_quote(str(out_file))} --component={tcl_quote(ip_name)}")
        return inst

    def set_ip_property(self, ip_name: str, prop, value) -> None:
        # ip_name here is the .qsys file path or instance name.
        if isinstance(prop, str):
            pairs = [(prop, value)]
        else:
            pairs = list(prop)
        items = " ".join(f"{tcl_quote(k)} {tcl_quote(str(v))}" for k, v in pairs)
        self._tcl(f"qsys-set-parameter -instance {tcl_quote(ip_name)} -dict [list {items}]")

    def generate_ip(self, ip_name: str) -> RunResult:
        t0 = time.time()
        path = Path(ip_name) if "/" in ip_name or ip_name.endswith(".qsys") else None
        if path is None:
            if self._current:
                path = Path(self._current.path).parent / f"{ip_name}.qsys"
            else:
                path = Path.cwd() / f"{ip_name}.qsys"
        self._tcl(
            f"qsys-generate {tcl_quote(str(path))} --synthesis=VERILOG",
            timeout=1800.0,
        )
        return RunResult(
            ok=True,
            stage="ip_synth",
            duration_sec=time.time() - t0,
            summary=f"generated IP {path.stem}",
        )

    # --- reports ----------------------------------------------------

    def report_timing(self, *, max_paths: int = 10) -> TimingReport:
        self._require_project()
        # Run sta, then read the .rpt file Quartus produces.
        self._safe_tcl("create_timing_netlist")
        self._safe_tcl("read_sdc")
        self._safe_tcl("update_timing_netlist")
        out = self._safe_tcl(
            f"report_timing -npaths {int(max_paths)} -return_string",
            default="",
        )
        wns = self._first_float(out, r"Worst-case (Slack)\s+([-+]?\d+\.\d+)")
        if wns is None:
            wns = self._first_float(out, r"Slack\s+([-+]?\d+\.\d+)", default=0.0)
        tns = self._first_float(out, r"Total Negative Slack\s+([-+]?\d+\.\d+)", default=0.0)
        paths = self._extract_quartus_paths(out)
        return TimingReport(
            wns_ns=wns,
            tns_ns=tns,
            failing_paths=paths,
        )

    def report_utilization(self) -> UtilizationReport:
        self._require_project()
        # `report_resource` writes to the report panel; the safer path is to
        # read the .fit.rpt file produced by the fitter.
        rpt = self._quartus_log("fit", suffix="fit.rpt")
        if rpt and rpt.exists():
            text = rpt.read_text(encoding="utf-8", errors="replace")
        else:
            text = self._safe_tcl("report_resource -return_string", default="")
        rows: list[UtilizationRow] = []
        for m in re.finditer(
            r"^\s*([A-Za-z][\w /().-]+?)\s*:\s*(\d+)\s*/\s*(\d+)",
            text,
            re.MULTILINE,
        ):
            try:
                used = int(m.group(2))
                avail = int(m.group(3))
                if avail <= 0:
                    continue
                pct = 100.0 * used / avail
                rows.append(
                    UtilizationRow(
                        resource=m.group(1).strip(),
                        used=used,
                        available=avail,
                        util_pct=pct,
                    )
                )
            except ValueError:
                continue
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
        # Quartus simulation is launched externally (ModelSim / Questa). We
        # emit a ModelSim .do file via `quartus_eda` and let the user open it.
        self._require_project()
        tb = top or testbench or (self._current.top if self._current else None)
        if not tb:
            return RunResult(
                ok=False,
                stage="simulation",
                errors=["no testbench top specified"],
            )
        tool = "MODELSIM"
        t0 = time.time()
        self._tcl("set_global_assignment -name EDA_SIMULATION_TOOL " + tcl_quote(tool))
        self._tcl("set_global_assignment -name EDA_TEST_BENCH_NAME " + tcl_quote(tb))
        self._safe_tcl(
            f"execute_module -tool eda --simulation_tool={tool} "
            f"--format=VERILOG --testbench_name={tcl_quote(tb)}"
        )
        return RunResult(
            ok=True,
            stage="simulation",
            duration_sec=time.time() - t0,
            summary=f"eda netlist for {tb} generated (run ModelSim to view)",
        )

    # --- bitstream & device ----------------------------------------

    def generate_bitstream(self, *, include_ltx: bool = True) -> Path:
        self._require_project()
        self._run_module("asm", "assembler")
        # .sof sits next to the .qpf under output_files/.
        name = self._current.name if self._current else "top"
        proj_dir = Path(self._current.path).parent if self._current else Path.cwd()
        sof = proj_dir / "output_files" / f"{name}.sof"
        if not sof.exists():
            matches = list(proj_dir.rglob("*.sof"))
            sof = matches[0] if matches else sof
        if not sof.exists():
            raise BackendError(f"bitstream not found after asm: {sof}")
        return sof

    def program_device(
        self, bitstream: Path, *, cable: str | None = None, device_index: int = 0
    ) -> RunResult:
        bitstream = Path(bitstream).expanduser().resolve()
        if not bitstream.exists():
            raise BackendError(f"bitstream not found: {bitstream}")
        # Quartus programming uses the `programmer` Tcl package. This works
        # when quartusd is reachable (USB-Blaster drivers loaded).
        t0 = time.time()
        self._tcl("load_package programmer")
        self._tcl("begin_execution")
        try:
            self._tcl("add_device -chip_id 1 -file " + tcl_quote(str(bitstream)))
            self._tcl("program_device")
        finally:
            self._tcl("end_execution")
        return RunResult(
            ok=True,
            stage="program",
            duration_sec=time.time() - t0,
            summary=f"programmed {bitstream.name}",
        )

    # --- internals --------------------------------------------------

    def _run_module(self, tool: str, label: str) -> bool:
        try:
            self._tcl(
                f"execute_module -tool {tcl_quote(tool)}",
                timeout=14400.0,
            )
            return True
        except Exception:
            return False

    def _quartus_log(self, stage: str, suffix: str | None = None) -> Path | None:
        if not self._current:
            return None
        proj_dir = Path(self._current.path).parent
        name = self._current.name
        ext = suffix or f"{stage}.rpt"
        return proj_dir / "output_files" / f"{name}.{ext}"

    @staticmethod
    def _first_float(text: str, pattern: str, default: float | None = None) -> float | None:
        m = re.search(pattern, text)
        if not m:
            return default
        try:
            return float(m.group(1))
        except (ValueError, IndexError):
            return default

    @staticmethod
    def _extract_quartus_paths(text: str) -> list[TimingPath]:
        # Quartus timing reports list paths in a fixed format with slack per
        # path. We pull just the slack number per path; richer fields require
        # post-processing the .sta.rpt file.
        paths: list[TimingPath] = []
        for m in re.finditer(
            r"Slack:\s+([-+]?\d+\.\d+)\s*(?:ns)?",
            text,
        ):
            try:
                slack = float(m.group(1))
            except ValueError:
                continue
            if slack < 0:
                paths.append(
                    TimingPath(
                        startpoint="<see .sta.rpt>",
                        endpoint="<see .sta.rpt>",
                        slack_ns=slack,
                    )
                )
        return paths[:10]


register("quartus", QuartusBackend)
