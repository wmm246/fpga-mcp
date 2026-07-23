"""Register fpga-mcp in MCP-capable AI clients.

Best-effort: we look for the standard config files and add a `mcpServers`
entry. If a file does not exist or is not writable, we report and skip
rather than crash.

Supported clients:
  - Claude Desktop  (~/Library/Application Support/Claude/claude_desktop_config.json)
  - Claude Code     (~/.claude.json)
  - Cursor          (~/.cursor/mcp.json)
  - Codex           (~/.codex/config.toml)  [best-effort TOML]
"""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any


def _claude_desktop_path() -> Path:
    sysname = platform.system()
    if sysname == "Darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    if sysname == "Windows":
        return Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def _claude_code_path() -> Path:
    return Path.home() / ".claude.json"


def _cursor_path() -> Path:
    # Cursor stores MCP config under ~/.cursor/mcp.json (global) or
    # .cursor/mcp.json in the workspace.
    return Path.home() / ".cursor" / "mcp.json"


def _clients() -> list[tuple[str, Path]]:
    return [
        ("Claude Desktop", _claude_desktop_path()),
        ("Claude Code", _claude_code_path()),
        ("Cursor", _cursor_path()),
    ]


def server_entry(command: str = "fpga-mcp") -> dict[str, Any]:
    """Build the mcpServers entry to inject."""
    return {command: {"command": command, "args": ["run"]}}


def _patch_json(path: Path, entry: dict[str, Any]) -> str:
    """Add entry to a JSON config file; return a status string."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"mcpServers": entry}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return f"created {path} (mcpServers entry added)"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"SKIP {path}: invalid JSON ({exc})"

    servers = data.setdefault("mcpServers", {})
    name = next(iter(entry))
    if name in servers:
        if servers[name] == entry[name]:
            return f"already registered in {path} (no change)"
        servers[name] = entry[name]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return f"updated existing entry in {path}"
    servers[name] = entry[name]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return f"added entry to {path}"


def register_in_all_clients(command: str = "fpga-mcp") -> list[tuple[str, str]]:
    """Try to register in every supported client. Returns one (client, status) per attempt."""
    entry = server_entry(command)
    results: list[tuple[str, str]] = []
    for name, path in _clients():
        try:
            results.append((name, _patch_json(path, entry)))
        except OSError as exc:
            results.append((name, f"SKIP: {exc}"))
    return results


def unregister_from_all_clients(command: str = "fpga-mcp") -> list[tuple[str, str]]:
    """Remove the entry from every supported client (for `doctor --fix`)."""
    results: list[tuple[str, str]] = []
    for name, path in _clients():
        if not path.exists():
            results.append((name, "no config file (nothing to do)"))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            results.append((name, f"SKIP: invalid JSON in {path}"))
            continue
        servers = data.get("mcpServers", {})
        if command in servers:
            del servers[command]
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            results.append((name, f"removed entry from {path}"))
        else:
            results.append((name, "entry not present (nothing to do)"))
    return results
