"""Smoke tests for the ``fpga-mcp`` CLI commands.

Uses Typer's CliRunner to invoke each command in-process. None of these
tests touch the network — they only verify that commands exist, exit
cleanly and produce expected output substrings.
"""

from __future__ import annotations

from typer.testing import CliRunner

from fpga_mcp import __version__
from fpga_mcp.cli import app

runner = CliRunner()


def test_version_command_prints_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_version_command_includes_platform_label():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    # platform_label always includes "on" or similar OS hint.
    out = result.stdout.lower()
    assert ("linux" in out) or ("windows" in out) or ("darwin" in out) or ("python" in out)


def test_backends_command_runs():
    # On a CI box with no EDA tools, all backends will be "(not found)" —
    # that's fine, the command must still exit 0.
    result = runner.invoke(app, ["backends"])
    assert result.exit_code == 0
    assert "Backend" in result.stdout  # column header


def test_tcl_server_path_vivado_runs():
    result = runner.invoke(app, ["tcl-server-path", "vivado"])
    assert result.exit_code == 0
    # Output should contain a path ending in vivado_server.tcl. Strip any
    # line-wrapping the terminal might insert (CliRunner uses a fixed
    # width that wraps long paths).
    out = result.stdout.replace("\n", "").replace("\r", "")
    assert "vivado_server.tcl" in out


def test_tcl_server_path_quartus_runs():
    result = runner.invoke(app, ["tcl-server-path", "quartus"])
    assert result.exit_code == 0
    out = result.stdout.replace("\n", "").replace("\r", "")
    assert "quartus_server.tcl" in out


def test_tcl_server_path_anlogic_runs():
    result = runner.invoke(app, ["tcl-server-path", "anlogic"])
    assert result.exit_code == 0
    out = result.stdout.replace("\n", "").replace("\r", "")
    assert "anlogic_server.tcl" in out


def test_tcl_server_path_rejects_unknown_backend():
    result = runner.invoke(app, ["tcl-server-path", "nonsense"])
    assert result.exit_code != 0
    assert "Unknown backend" in result.stdout


def test_help_lists_all_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout
    for cmd in ("version", "backends", "setup", "doctor", "run", "tcl-server-path"):
        assert cmd in out, f"missing {cmd} in help"


def test_doctor_runs_without_crashing(tmp_path, monkeypatch):
    # Point the config path at a tmp file so doctor doesn't read the host's
    # real config. We patch DEFAULT_CONFIG_PATH inside the cli module because
    # the env var is only read at module-import time.
    cfg_path = tmp_path / "fpga-mcp" / "config.json"
    monkeypatch.setattr("fpga_mcp.cli.DEFAULT_CONFIG_PATH", cfg_path)
    result = runner.invoke(app, ["doctor"])
    # doctor exits 0 only if everything is OK; on a fresh box it exits 1
    # because the config doesn't exist. Either way, must not crash.
    assert result.exit_code in (0, 1)
    assert "fpga-mcp doctor" in result.stdout


def test_setup_writes_config(tmp_path, monkeypatch):
    cfg_path = tmp_path / "fpga-mcp" / "config.json"
    monkeypatch.setattr("fpga_mcp.cli.DEFAULT_CONFIG_PATH", cfg_path)
    result = runner.invoke(app, ["setup", "--skip-register"])
    assert result.exit_code == 0
    assert "Setup complete" in result.stdout
    # The config file should now exist.
    assert cfg_path.exists()
