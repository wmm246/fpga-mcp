"""Runtime configuration for fpga-mcp.

All settings can be overridden via environment variables or a JSON config
file (default: ``~/.config/fpga-mcp/config.json``). The config is
deliberately tiny — heavy state lives inside the running EDA tool, not here.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_DIR = Path(
    os.environ.get("FPGA_MCP_CONFIG_DIR", str(Path.home() / ".config" / "fpga-mcp"))
)
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"

# Default port for the Vivado Tcl TCP server. Matches SynthPilot's choice so
# users migrating from it do not need to retune firewalls.
VIVADO_TCL_PORT_DEFAULT = 9999
# Quartus tclsh port (a separate small Tcl helper launched by our backend).
QUARTUS_TCL_PORT_DEFAULT = 9998
# Anlogic TD CLI bridge port (a small socket relay that the TD CLI talks to).
ANLOGIC_TCL_PORT_DEFAULT = 9997


@dataclass
class BackendConfig:
    """Per-backend connection settings."""

    vivado_host: str = "127.0.0.1"
    vivado_port: int = VIVADO_TCL_PORT_DEFAULT
    vivado_path: str | None = None  # auto-detect if None

    quartus_host: str = "127.0.0.1"
    quartus_port: int = QUARTUS_TCL_PORT_DEFAULT
    quartus_path: str | None = None

    anlogic_host: str = "127.0.0.1"
    anlogic_port: int = ANLOGIC_TCL_PORT_DEFAULT
    anlogic_td_path: str | None = None


@dataclass
class Config:
    """Top-level runtime config."""

    active_backend: str = "vivado"
    log_level: str = "INFO"
    workspace: str = str(Path.cwd())
    backends: BackendConfig = field(default_factory=BackendConfig)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Config":
        """Load config from ``path`` (or the default location).

        Missing files are OK — sensible defaults are returned. Environment
        variables override file values, so users can ``export`` per session.
        """
        path = Path(path) if path else DEFAULT_CONFIG_PATH
        data: dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid config at {path}: {exc}") from exc

        backends_data = data.pop("backends", {})
        cfg = cls(
            active_backend=data.pop("active_backend", "vivado"),
            log_level=data.pop("log_level", "INFO"),
            workspace=data.pop("workspace", str(Path.cwd())),
            backends=BackendConfig(**backends_data),
            extra=data,
        )
        cls._apply_env(cfg)
        return cfg

    @staticmethod
    def _apply_env(cfg: "Config") -> None:
        env = os.environ
        cfg.active_backend = env.get("FPGA_MCP_BACKEND", cfg.active_backend)
        cfg.log_level = env.get("FPGA_MCP_LOG_LEVEL", cfg.log_level)
        cfg.workspace = env.get("FPGA_MCP_WORKSPACE", cfg.workspace)
        b = cfg.backends
        b.vivado_host = env.get("FPGA_MCP_VIVADO_HOST", b.vivado_host)
        b.vivado_port = int(env.get("FPGA_MCP_VIVADO_PORT", b.vivado_port))
        b.vivado_path = env.get("FPGA_MCP_VIVADO_PATH", b.vivado_path) or b.vivado_path
        b.quartus_host = env.get("FPGA_MCP_QUARTUS_HOST", b.quartus_host)
        b.quartus_port = int(env.get("FPGA_MCP_QUARTUS_PORT", b.quartus_port))
        b.quartus_path = env.get("FPGA_MCP_QUARTUS_PATH", b.quartus_path) or b.quartus_path
        b.anlogic_host = env.get("FPGA_MCP_ANLOGIC_HOST", b.anlogic_host)
        b.anlogic_port = int(env.get("FPGA_MCP_ANLOGIC_PORT", b.anlogic_port))
        b.anlogic_td_path = (
            env.get("FPGA_MCP_ANLOGIC_TD_PATH", b.anlogic_td_path) or b.anlogic_td_path
        )

    def save(self, path: Path | str | None = None) -> Path:
        path = Path(path) if path else DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path
