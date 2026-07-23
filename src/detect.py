"""Detection helpers — find Vivado / Quartus / Anlogic binaries on the host."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolDetection:
    name: str
    found: bool
    binary: Path | None
    detail: str = ""


# Common install locations (best-effort — we only check, never assume).
_VIVADO_DIRS = [
    "/opt/Xilinx/Vivado",  # Linux default
    "/tools/Xilinx/Vivado",
    "C:\\Xilinx\\Vivado",  # Windows default
    "C:\\tools\\Xilinx\\Vivado",
    "/Applications/Xilinx/Vivado",  # macOS (rare)
]
_QUARTUS_DIRS = [
    "/opt/intelFPGA",
    "/opt/altera",
    "C:\\intelFPGA",
    "C:\\altera",
    "/Applications/intelFPGA",
]
_ANLOGIC_DIRS = [
    "/opt/Anlogic/Tang",
    "/opt/TD",
    "C:\\Anlogic\\TD",
    "C:\\Program Files\\Anlogic\\TD",
]


def _which(names: list[str]) -> Path | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return Path(p)
    return None


def _scan_dirs(parents: list[str], sub_pattern: str, target: str) -> Path | None:
    """Look for ``<parent>/<version>/<target>`` across candidate parents."""
    for parent in parents:
        if not Path(parent).is_dir():
            continue
        for ver in sorted(Path(parent).iterdir(), reverse=True):
            cand = ver / sub_pattern
            if cand.exists():
                return cand / target if (cand / target).exists() else cand
    return None


def detect_vivado() -> ToolDetection:
    """Locate the Vivado binary."""
    # 1. PATH lookup.
    p = _which(["vivado", "vivado.bat"])
    if p:
        return ToolDetection("vivado", True, p, "found on PATH")
    # 2. FPGA_MCP_VIVADO_PATH env override.
    env = os.environ.get("FPGA_MCP_VIVADO_PATH")
    if env and Path(env).exists():
        return ToolDetection("vivado", True, Path(env), "via env override")
    # 3. Common install dirs.
    p = _scan_dirs(_VIVADO_DIRS, "bin", "vivado")
    if p:
        return ToolDetection("vivado", True, p, "discovered in install dir")
    return ToolDetection("vivado", False, None, "not found")


def detect_quartus() -> ToolDetection:
    p = _which(["quartus_sh", "quartus", "quartus_sh.bat"])
    if p:
        return ToolDetection("quartus", True, p, "found on PATH")
    env = os.environ.get("FPGA_MCP_QUARTUS_PATH")
    if env and Path(env).exists():
        return ToolDetection("quartus", True, Path(env), "via env override")
    p = _scan_dirs(_QUARTUS_DIRS, "quartus/bin64", "quartus_sh")
    if p:
        return ToolDetection("quartus", True, p, "discovered in install dir")
    return ToolDetection("quartus", False, None, "not found")


def detect_anlogic() -> ToolDetection:
    p = _which(["td", "td_cli", "td.exe", "td_pgm"])
    if p:
        return ToolDetection("anlogic", True, p, "found on PATH")
    env = os.environ.get("FPGA_MCP_ANLOGIC_TD_PATH")
    if env and Path(env).exists():
        return ToolDetection("anlogic", True, Path(env), "via env override")
    p = _scan_dirs(_ANLOGIC_DIRS, "bin", "td")
    if p:
        return ToolDetection("anlogic", True, p, "discovered in install dir")
    return ToolDetection("anlogic", False, None, "not found")


def detect_all() -> list[ToolDetection]:
    return [detect_vivado(), detect_quartus(), detect_anlogic()]


def platform_label() -> str:
    return f"{sys.platform} (python {sys.version_info.major}.{sys.version_info.minor})"
