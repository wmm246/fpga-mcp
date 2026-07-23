"""fpga-mcp CLI.

Typer-based entrypoint exposed via the `fpga-mcp` / `fpga-mcp`
console scripts. Commands:

    fpga-mcp setup         # guided one-command onboarding
    fpga-mcp doctor [--fix]  # diagnose / self-heal
    fpga-mcp run           # start the MCP server over stdio
    fpga-mcp backends      # list detected backends
    fpga-mcp version       # print version

Everything is non-interactive when stdin is not a TTY — the prompts fall
back to sensible defaults, so this CLI is also CI-friendly.
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fpga_mcp import __version__
from fpga_mcp._client_registry import (
    register_in_all_clients,
)
from fpga_mcp.config import Config, DEFAULT_CONFIG_PATH
from fpga_mcp.detect import detect_all, platform_label
from fpga_mcp.transports._tcl_client import TclClient, TclClientError

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="fpga-mcp — open multi-vendor MCP for FPGA EDA flows.",
)
log = logging.getLogger("fpga_mcp.cli")
console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _tcp_probe(host: str, port: int, timeout: float = 1.0) -> tuple[bool, str]:
    """Cheap liveness probe: try to open a TCP socket."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "reachable"
    except OSError as exc:
        return False, f"unreachable ({exc})"


def _tcl_server_check(host: str, port: int) -> tuple[bool, str]:
    """Try the fpga-mcp Tcl banner handshake."""
    client = TclClient(host=host, port=port, connect_timeout=2.0)
    try:
        client.connect()
        client.disconnect()
        return True, "responds"
    except (TclClientError, OSError) as exc:
        return False, f"no banner ({exc})"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the installed version and exit."""
    console.print(f"fpga-mcp {__version__} ({platform_label()})")


@app.command()
def backends() -> None:
    """Show which EDA tools were detected on this machine."""
    table = Table(title="Detected EDA backends")
    table.add_column("Backend")
    table.add_column("Binary")
    table.add_column("Detail")
    for d in detect_all():
        table.add_row(
            d.name,
            str(d.binary) if d.binary else "(not found)",
            d.detail,
            style="green" if d.found else "red",
        )
    console.print(table)


@app.command()
def setup(
    backend: str = typer.Option(
        "",
        "--backend",
        "-b",
        help="Active backend to set in the config (vivado/quartus/anlogic). "
        "Empty = pick the first detected one.",
    ),
    skip_register: bool = typer.Option(
        False,
        "--skip-register",
        help="Skip registering the MCP in AI editors.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Guided one-command onboarding: detect tools, write config, register in AI clients."""
    _set_logging(verbose)
    console.rule("[bold cyan]fpga-mcp setup[/]")
    console.print(f"Platform: [dim]{platform_label()}[/]")

    detected = detect_all()
    found = {d.name: d for d in detected if d.found}
    if not found:
        console.print(
            "[yellow]No EDA tools detected on PATH or in common install "
            "dirs.[/] You can still proceed — the MCP server will start, "
            "and you can run the matching Tcl TCP server later."
        )

    # Decide active backend.
    if backend:
        if backend not in {"vivado", "quartus", "anlogic"}:
            console.print(f"[red]Unknown backend: {backend}[/]")
            raise typer.Exit(code=2)
        active = backend
    elif found:
        active = next(iter(found))
    else:
        active = "vivado"
    console.print(f"Active backend: [bold]{active}[/]")

    # Build a fresh Config.
    cfg = Config(active_backend=active)
    for d in detected:
        if not d.found or d.binary is None:
            continue
        bin_str = str(d.binary)
        if d.name == "vivado":
            cfg.backends.vivado_path = bin_str
        elif d.name == "quartus":
            cfg.backends.quartus_path = bin_str
        elif d.name == "anlogic":
            cfg.backends.anlogic_td_path = bin_str

    cfg_path = cfg.save(DEFAULT_CONFIG_PATH)
    console.print(f"Wrote config: [bold]{cfg_path}[/]")

    if not skip_register:
        console.rule("[bold cyan]Registering in AI clients[/]")
        results = register_in_all_clients(command="fpga-mcp")
        for client, status in results:
            console.print(f"  [bold]{client}[/]: {status}")

    # Final connectivity check.
    console.rule("[bold cyan]Connectivity check[/]")
    table = Table()
    table.add_column("Backend")
    table.add_column("Port")
    table.add_column("Status")
    table.add_row(
        "vivado",
        str(cfg.backends.vivado_port),
        _tcl_server_check(cfg.backends.vivado_host, cfg.backends.vivado_port)[1],
    )
    table.add_row(
        "quartus",
        str(cfg.backends.quartus_port),
        _tcl_server_check(cfg.backends.quartus_host, cfg.backends.quartus_port)[1],
    )
    table.add_row(
        "anlogic",
        str(cfg.backends.anlogic_port),
        _tcl_server_check(cfg.backends.anlogic_host, cfg.backends.anlogic_port)[1],
    )
    console.print(table)

    console.print()
    console.print(
        "[green]Setup complete.[/] Start a backend Tcl server next, e.g.:\n"
        "  [dim]vivado -mode tcl -source tcl/vivado_server.tcl[/]\n"
        "  [dim]quartus_sh -t tcl/quartus_server.tcl[/]\n"
        "  [dim]td -tcl  (then `source tcl/anlogic_server.tcl`)[/]\n"
        "Then ask your AI client to drive your FPGA flow."
    )


@app.command()
def doctor(
    fix: bool = typer.Option(False, "--fix", help="Attempt automatic repairs."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Diagnose the installation and attempt repairs."""
    _set_logging(verbose)
    console.rule("[bold cyan]fpga-mcp doctor[/]")

    issues: list[str] = []

    # 1. Config file exists?
    if not DEFAULT_CONFIG_PATH.exists():
        issues.append(f"config missing at {DEFAULT_CONFIG_PATH} — run `fpga-mcp setup`.")
        if fix:
            console.print("[yellow]Re-running setup to create config...[/]")
            setup.callback(backend="", skip_register=True, verbose=verbose)
    cfg = Config.load()

    # 2. Each backend tool installed?
    for d in detect_all():
        if not d.found:
            issues.append(f"{d.name} binary not found: {d.detail}")
        else:
            console.print(f"  [green]OK[/]  {d.name}: {d.binary}")

    # 3. Each backend's TCP server reachable?
    for name, host, port in [
        ("vivado", cfg.backends.vivado_host, cfg.backends.vivado_port),
        ("quartus", cfg.backends.quartus_host, cfg.backends.quartus_port),
        ("anlogic", cfg.backends.anlogic_host, cfg.backends.anlogic_port),
    ]:
        ok, msg = _tcl_server_check(host, port)
        flag = "[green]OK[/]" if ok else "[yellow]DOWN[/]"
        console.print(f"  {flag}  {name} TCP server {host}:{port}: {msg}")
        if not ok:
            issues.append(
                f"{name} Tcl server not responding on {host}:{port}. "
                f"Start it with: source tcl/{name}_server.tcl"
            )

    # 4. MCP client registrations present?
    from fpga_mcp._client_registry import _clients

    for client_name, path in _clients():
        if path.exists():
            console.print(f"  [green]OK[/]  {client_name} config: {path}")
        else:
            console.print(
                f"  [dim]--[/]  {client_name} config not present (will be created on first register)"
            )
            if fix:
                register_in_all_clients()
                break

    # Summary
    console.rule("[bold cyan]Summary[/]")
    if not issues:
        console.print("[green]All checks passed.[/]")
        raise typer.Exit(code=0)
    console.print(f"[yellow]{len(issues)} issue(s) found:[/]")
    for i, msg in enumerate(issues, 1):
        console.print(f"  {i}. {msg}")
    if fix:
        console.print("[green]Attempted auto-repairs where possible.[/]")
    raise typer.Exit(code=1 if issues else 0)


@app.command()
def run(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Start the MCP server (stdio transport)."""
    _set_logging(verbose)
    from fpga_mcp.server import run_stdio

    run_stdio()


@app.command()
def tcl_server_path(
    backend: str = typer.Argument(
        ...,
        help="Which vendor's Tcl server script to print.",
    ),
) -> None:
    """Print the absolute path to the bundled Tcl server script for a backend."""
    if backend not in {"vivado", "quartus", "anlogic"}:
        console.print(f"[red]Unknown backend: {backend}[/]")
        raise typer.Exit(code=2)
    # Find via the package directory.
    import fpga_mcp as pkg

    candidates = [
        Path(pkg.__file__).resolve().parent / "tcl" / f"{backend}_server.tcl",
        Path(pkg.__file__).resolve().parents[2] / "tcl" / f"{backend}_server.tcl",
    ]
    for c in candidates:
        if c.exists():
            console.print(str(c))
            return
    console.print(f"[red]Tcl server script for {backend} not found.[/]")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
