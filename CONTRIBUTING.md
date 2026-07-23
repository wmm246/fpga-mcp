# Contributing to fpga-mcp

Thanks for considering a contribution! `fpga-mcp` is community-driven and MIT
licensed — patches, new tools, new vendor backends, methodology prompts,
docs and tests are all welcome.

This guide walks through:

- [Setup](#setup) — get a dev env in under a minute
- [Layout](#layout) — where things live
- [Adding a new tool](#adding-a-new-tool) — the 99% case
- [Adding a new vendor](#adding-a-new-vendor) — bigger projects
- [Adding a methodology prompt](#adding-a-methodology-prompt)
- [Tests](#tests) — what we expect every PR to ship
- [Style](#style) — code, commit messages, branches
- [Releasing](#releasing) — how the maintainers cut a release

---

## Setup

`fpga-mcp` needs Python ≥ 3.10. You **do not** need Vivado, Quartus or
TangDynasty installed to hack on it — the test suite ships with an in-process
mock Tcl server for all three vendors.

```bash
git clone https://github.com/wmm246/fpga-mcp
cd fpga-mcp
pip install -e '.[dev]'   # editable install, brings in pytest/ruff/build
pytest                   # 69 tests should pass
ruff check src tests     # clean
fpga-mcp version         # smoke check
```

Optional, for actually driving hardware:

```bash
# Pick the one(s) you have:
vivado -mode tcl -source tcl/vivado_server.tcl
quartus_sh -t tcl/quartus_server.tcl
td -tcl                  # then inside TD: source tcl/anlogic_server.tcl
```

---

## Layout

```
src/fpga_mcp/
├── server.py            # FastMCP entry point
├── cli.py               # Typer CLI: setup / doctor / run / version / ...
├── session.py           # BackendManager — multi-vendor switching
├── config.py            # Config + env overrides (FPGA_MCP_*)
├── detect.py            # Find Vivado/Quartus/TD binaries on PATH
├── prompts.py           # Register methodology/*.md as MCP prompts
├── _client_registry.py  # Auto-register in Claude/Cursor/Cline/Codex
├── transports/
│   ├── base.py          # EDABackend Protocol (vendor-agnostic contract)
│   ├── _base_tcp.py     # Shared TCP/Tcl plumbing + _safe_tcl wrapper
│   ├── _tcl_client.py   # Wire-format client (newline-delimited JSON)
│   ├── _tcl_helpers.py  # Tcl string/list quoting
│   ├── vivado.py
│   ├── quartus.py
│   └── anlogic.py
└── tool_defs/           # ← where 99% of new tools land
    ├── __init__.py      # ToolSpec / ArgSpec / register_all / factory
    ├── _handlers.py     # Python handlers for the 22 common tools
    ├── common.py        # 22 high-level vendor-agnostic specs
    ├── vivado.py        # 343 Vivado specs
    ├── quartus.py       # 167 Quartus specs
    └── anlogic.py       # 157 Anlogic specs

tcl/                     # Tcl TCP server scripts (run inside each EDA tool)
methodology/             # Markdown workflows → MCP prompts
tests/                   # 69 tests; mocks for all three vendors
.github/                 # CI, issue/PR templates
```

---

## Adding a new tool

The catalogue is **declarative**. A tool = one `ToolSpec(...)` line in the
right `tool_defs/<vendor>.py`. No boilerplate, no separate function file.

### The 30-second recipe

1. Pick the file by vendor:
   - `common.py` if it's vendor-agnostic and **calls backend Python** (e.g.
     `current_project`, `run_synthesis`). These get a `handler=` callback
     from `_handlers.py`.
   - `<vendor>.py` if it's a Tcl wrapper (the vast majority).
2. Add a line:

   ```python
   _t(
       "viv_my_new_thing",                  # tool name (must be unique)
       "my_new_thing -mode {mode} -input {path}",  # Tcl template
       "Run my_new_thing with the given mode and input.",
       "custom_category",                   # free-form string
       args=[                               # optional: richer arg metadata
           ArgSpec("mode", "One of fast/normal.", default="normal"),
           ArgSpec("path", "Input file path."),
       ],
       notes="Added in #123.",              # optional
   )
   ```

3. Naming conventions (enforced by tests):
   - Vivado tools: `viv_*` prefix.
   - Quartus tools: `q_*` prefix.
   - Anlogic tools: `a_*` prefix.
   - Common tools: no prefix.

4. Template syntax: `{name}` is a placeholder. Use `{{` and `}}` for literal
   Tcl braces:

   ```python
   _t("viv_foreach_clock",
      "foreach c [get_clocks] {{puts $c}}",   # {{ }} are literal braces
      "Print every clock.",
      "netlist")
   ```

5. Run the catalogue invariant tests:

   ```bash
   pytest tests/test_tool_defs.py
   ```

   These already check:
   - Total ≥ 500 specs.
   - No duplicate names across all four catalogues.
   - Prefix conventions per file.
   - Every spec has a non-empty template **or** a handler.
   - Every spec has summary + category.

6. Add an end-to-end test if the tool has non-trivial parsing. Look at
   `test_vivado_backend.py` / `test_quartus_backend.py` / `test_anlogic_backend.py`
   for the mock Tcl server pattern.

That's it. The MCP server picks up the new tool automatically — no
registration, no wiring.

---

## Adding a new vendor

This is bigger work. Roughly in order:

1. **Backend Python class** — `src/fpga_mcp/transports/<vendor>.py`:
   ```python
   class FooBackend(EDABackend):
       name = "foo"
       # Implement every method of the EDABackend Protocol from
       # transports/base.py.
   ```
   Reuse `_BaseTCPBackend` from `_base_tcp.py` for the TCP plumbing. The
   only vendor-specific code should be: port number, banner name, and the
   Tcl command strings for `create_project`, `add_sources`,
   `run_synthesis`, etc.

2. **Tcl server script** — `tcl/<vendor>_server.tcl`:
   - Source `_omni_protocol.tcl` for the shared JSON-over-TCP RPC.
   - Optionally vendor-specific helpers.
   - The script is what gets `source`d inside the vendor's Tcl shell.

3. **Tool catalogue** — `src/fpga_mcp/tool_defs/<vendor>.py`:
   - Use `_t()` helper, set `vendor="foo"`.
   - Pick a prefix (e.g. `f_`) and use it consistently.

4. **Wire into the framework**:
   - `config.py`: add `foo_*` config knobs (host, port, paths) +
     env vars `FPGA_MCP_FOO_*`.
   - `detect.py`: add detection for the vendor's binary on `PATH`.
   - `session.py`: register the backend in `BackendManager`.
   - `cli.py`: extend `tcl-server-path` and `backends` commands.

5. **Tests** — `tests/test_<vendor>_backend.py`:
   - Mock Tcl server with handlers for every command your backend sends.
   - End-to-end test for `create_project`, `add_sources`, `run_synthesis`,
     `report_timing`, `report_utilization`, `exec_tcl`, `disconnect`.

6. **Docs**:
   - README: add the vendor to the comparison table, tool surface table,
     and architecture tree.
   - CHANGELOG: note the new vendor under `### Added`.
   - Methodology prompts: review `methodology/*.md` and check if any
     vendor-specific callouts are needed.

---

## Adding a methodology prompt

Methodology prompts are plain markdown in `methodology/`. They're auto-loaded
by `prompts.py` — no registration.

1. Drop a new `methodology/<name>.md`:
   ```markdown
   # <Title>

   Use this when …

   ## Prerequisites
   …

   ## Steps
   1. …
   2. …

   ## Exit criteria
   - …
   ```

2. Add a test in `tests/test_server.py` (extend the
   `test_server_lists_methodology_prompts` set list).

3. Reference it from `README.md` if user-facing.

---

## Tests

Every PR must keep the suite green. We aim for **every backend** and
**every Python handler** to have at least one happy-path test.

```bash
pytest -ra                # all 69 tests
pytest tests/test_tool_defs.py    # catalogue invariants
pytest tests/test_vivado_backend.py
pytest tests/test_quartus_backend.py
pytest tests/test_anlogic_backend.py
pytest tests/test_cli.py
```

Adding a tool = at least verify the catalogue invariants still pass. Adding
a vendor = end-to-end mock tests for every backend method. Adding a Python
handler in `_handlers.py` = a stub-backend dispatch test in
`test_tool_defs.py` (see `test_factory_dispatches_to_handler_when_set`).

CI runs the full matrix on every push and PR:

- 3 OS (ubuntu / windows / macos) × 3 Python (3.10 / 3.11 / 3.12)
- `ruff check` + `pytest` + `build` (sdist + wheel)

---

## Style

### Python

Enforced by `ruff`. `ruff check .` and `ruff format .` are authoritative.

- Line length 100.
- Target Python 3.10 (use `from __future__ import annotations` for
  PEP 604 syntax like `int | None`).
- Type hints encouraged but not mandatory for new specs in tool_defs.
- Use the `_t()` helper when adding tool specs — it defaults
  `vendor=` correctly per file.

### Tcl

- Match the style of the existing `tcl/*.tcl` files.
- Always `catch` external commands and return a structured error to the
  RPC layer (see `_omni_protocol.tcl`).
- Never `puts` to stdout from inside a tool call — use the RPC return
  channel.

### Commit messages

Use the [Conventional Commits](https://www.conventionalcommits.org/) style
prefix optionally, but always:

- Subject line ≤ 72 chars, imperative mood ("Add …", not "Added …").
- Body explains the **why**, not just the **what** (the diff shows what).
- Reference issues with `Fixes #123` / `Closes #123`.

Example:

```
Add viv_report_clock_interaction for CDC audits

SynthPilot exposes this; fpga-mcp was missing it. Adds the tool to the
vivado catalogue under the timing category, with an integration test that
verifies the parsed output structure.

Fixes #42.
```

### Branches

- `main` is always releasable. CI must be green.
- Branch from `main`, open a PR back to `main`.
- Branch naming: `feat/<short>`, `fix/<short>`, `docs/<short>`,
  `vendor/<short>`, `test/<short>`.

---

## Releasing

Maintainers only. The flow is fully automated — no manual `twine upload`.

1. Make sure `main` is clean, CI is green, `pyproject.toml` `version` is
   bumped (semantic versioning: `0.X.Y`).
2. Tag and push:

   ```bash
   git tag v0.X.Y
   git push origin v0.X.Y
   ```

3. The `release` job in `.github/workflows/ci.yml` will:
   - Download the sdist + wheel built by the `build` job.
   - `twine upload --skip-existing dist/*` to PyPI (uses the
     `PYPI_API_TOKEN` secret + the `pypi` environment).
   - Create a GitHub Release with auto-generated release notes via
     `softprops/action-gh-release@v2`.

4. Pre-release tags: any tag containing `rc` or `beta` (e.g. `v0.2.0rc1`)
   is auto-marked as a GitHub pre-release.

5. Update `CHANGELOG.md`'s `[Unreleased]` section accordingly, and start
   a new `[Unreleased]` block above it.

---

## Questions

- Open an issue with the `question` label, or
- Start a [Discussion](https://github.com/wmm246/fpga-mcp/discussions).

Thanks again for helping make `fpga-mcp` better!
