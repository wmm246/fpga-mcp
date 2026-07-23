"""Register methodology markdown files as MCP prompts.

Each ``methodology/*.md`` file is a named expert workflow (akin to the
oh-my-fpga skill pack for SynthPilot). We expose them as MCP prompts so any
MCP-capable AI client can pick one from its ``/`` menu and let the model
execute the workflow using the typed tools in :mod:`fpga_mcp.tools`.

Locating the markdown files
---------------------------
Two locations are searched:

1. The wheel-installed copy at ``fpga_mcp/methodology/`` (production).
2. The repo-root ``methodology/`` directory (development / editable installs).

The first directory that exists wins.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fpga_mcp.session import BackendManager

log = logging.getLogger("fpga_mcp.prompts")


def _methodology_dir() -> Path | None:
    candidates = [
        Path(__file__).resolve().parent / "methodology",  # installed wheel
        Path(__file__).resolve().parents[2] / "methodology",  # dev / editable
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def _discover_workflows() -> list[tuple[str, str, str]]:
    """Return ``(name, description, body)`` triples for every .md file."""
    d = _methodology_dir()
    if d is None:
        log.warning("methodology directory not found; no prompts registered")
        return []
    out: list[tuple[str, str, str]] = []
    for p in sorted(d.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        # First non-blank non-#-line is a decent description.
        desc = ""
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            desc = line
            break
        out.append((p.stem, desc or p.stem, text))
    return out


def register_prompts(mcp, manager: BackendManager) -> None:
    """Register every methodology workflow as an MCP prompt.

    Each prompt takes a single optional ``goal`` argument the AI can use to
    specialise the run (e.g. "WNS ≥ 0.5 ns headroom" for the
    ``timing_closure`` workflow).
    """
    workflows = _discover_workflows()
    if not workflows:
        log.warning("no methodology workflows found")
        return

    backend_hint = (
        f"The active backend is '{manager.active_name}'. "
        f"Switch with `set_backend` if a different vendor is needed."
    )

    def _make_prompt(name: str, desc: str, body: str):
        def _impl(goal: str = "") -> str:
            prefix = (
                f"# Workflow: {name.replace('_', ' ').title()}\n\n"
                f"User goal: {goal or '(unspecified — pick reasonable defaults)'}\n"
                f"{backend_hint}\n\n---\n\n"
            )
            return prefix + body

        _impl.__doc__ = desc
        _impl.__name__ = f"prompt_{name}"
        return _impl

    for name, desc, body in workflows:
        mcp.prompt(name=name, description=desc)(_make_prompt(name, desc, body))
        log.debug("registered prompt: %s", name)
