"""Tests for Config load/save + env overrides."""

from __future__ import annotations

import json
from pathlib import Path

from fpga_mcp.config import Config


def test_default_config_round_trips(tmp_path: Path):
    cfg = Config(active_backend="quartus")
    p = cfg.save(tmp_path / "config.json")
    assert p.exists()
    loaded = Config.load(p)
    assert loaded.active_backend == "quartus"
    assert loaded.backends.vivado_port == 9999


def test_env_overrides(monkeypatch, tmp_path: Path):
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps(
            {
                "active_backend": "vivado",
                "backends": {"vivado_port": 9999, "quartus_port": 9998},
            }
        )
    )
    monkeypatch.setenv("FPGA_MCP_BACKEND", "anlogic")
    monkeypatch.setenv("FPGA_MCP_VIVADO_PORT", "12345")
    cfg = Config.load(p)
    assert cfg.active_backend == "anlogic"
    assert cfg.backends.vivado_port == 12345
    assert cfg.backends.quartus_port == 9998  # untouched


def test_missing_file_uses_defaults(tmp_path: Path):
    p = tmp_path / "missing.json"
    cfg = Config.load(p)
    assert cfg.active_backend == "vivado"
    assert cfg.backends.vivado_host == "127.0.0.1"
