# Security Policy

`fpga-mcp` runs entirely on your local machine and never sends your RTL,
project files, bitstreams, or FPGA design data over the network. This page
covers the security model and how to report vulnerabilities.

## Supported versions

`fpga-mcp` is pre-1.0 software. Security fixes are applied to the latest
`main` and the most recent tagged release only.

| Version | Supported |
|---------|-----------|
| `0.1.x` (latest tag) | ✅ |
| `main` branch        | ✅ (latest fixes land here first) |
| Older tags           | ❌ — please upgrade |

## Trust model

### What runs where

- **The MCP server** (`fpga-mcp run`) runs locally as your user. It listens
  on a local stdio pipe to the MCP client (Claude Desktop, Cursor, etc.)
  and on TCP ports `9999` (Vivado), `9998` (Quartus), `9997` (Anlogic) for
  the EDA tool's Tcl server. **No listening port is exposed to the public
  internet by default.**
- **The Tcl TCP server** (`tcl/<vendor>_server.tcl`) runs inside the EDA
  tool's Tcl shell on the same host. It speaks a newline-delimited JSON
  protocol defined in `tcl/_omni_protocol.tcl`.
- **The MCP client** (Claude Desktop, Cursor, etc.) connects to `fpga-mcp`
  over stdio. The AI agent's tool calls flow: client → stdio → MCP server →
  TCP → Tcl server → Vivado/Quartus/TangDynasty.

### What stays on your machine

- Your **RTL source code**, constraint files, testbenches and any other
  file referenced by a tool call.
- Your **project metadata** (`.xpr` / `.qpf` / project paths, part numbers,
  top-level module names).
- Your **synthesis / implementation / timing reports**.
- Your **bitstreams** and probe files (`.bit` / `.ltx` / `.sof`).
- The **Tcl commands** the AI sends to the EDA tool.

`fpga-mcp` does **not**:

- Phone home, telemetry, or analytics.
- Upload any design artifact to any external server.
- Embed any model or call any AI inference service. (The MCP client —
  Claude / Cursor / etc. — does that. fpga-mcp is purely the tool layer
  between the client and the EDA tool.)
- Auto-update itself or download anything at runtime.

### What does leave your machine

- The MCP client (Claude Desktop, Cursor, etc.) may send tool **inputs**
  and **outputs** to its own inference backend as part of normal MCP
  operation. **This is the client's responsibility, not fpga-mcp's.**
  Review your MCP client's privacy policy. If your design is sensitive,
  consider a client that runs the model locally (e.g. Ollama + an MCP
  bridge) or air-gap the workstation.
- The `setup --register` flow writes a config snippet into your MCP
  client's config file (e.g. `~/Library/Application Support/Claude/claude_desktop_config.json`
  on macOS, `~/.cursor/mcp.json` for Cursor). **It does not upload anything
  to the client vendor.** The snippet only tells the client how to launch
  `fpga-mcp` locally.

### What `exec_tcl` lets the AI do

`exec_tcl` is the universal escape hatch — it lets the AI run **any Tcl**
inside the EDA tool. This means:

- File I/O within the Tcl interpreter's permissions (which run as your user).
- `exec` of arbitrary shell commands from within Tcl, if the vendor's Tcl
  supports it (Vivado's does).

Treat the AI's reach via `exec_tcl` as equivalent to the EDA tool itself.
Run fpga-mcp on a workstation where that level of access is acceptable.
If you want to constrain it, set up OS-level sandboxing (sandbox-exec on
macOS, AppArmor on Linux, etc.) around the EDA tool's process.

## Reporting a vulnerability

If you find a security issue, **please do not open a public GitHub issue**.

Report it privately instead:

1. **Preferred:** use GitHub's private vulnerability reporting:
   - Go to <https://github.com/wmm246/fpga-mcp/security/advisories/new>
   - Fill in the advisory form. GitHub will notify the maintainers
     privately.

2. **Alternative:** email the maintainer directly at
   `security@<your-domain>` (replace with a real address once the project
   has a dedicated security contact).

Please include:

- A description of the issue and its impact.
- Affected versions (tag or commit).
- Reproduction steps (commands, configs, sample payloads).
- Suggested fix if you have one.

### Response timeline

We aim to:

- Acknowledge within **72 hours**.
- Provide an initial assessment within **7 days**.
- Coordinate a fix and disclosure timeline with you.

Once a fix is ready, we'll cut a patch release and publish a GitHub Security
Advisory with credit (unless you'd prefer to remain anonymous).

## Hardening recommendations

For sensitive designs:

1. **Bind the Tcl servers to localhost only.** The default `tcl/*_server.tcl`
   scripts listen on `127.0.0.1`. Verify this before running on a
   multi-user host.
2. **Run the EDA tool inside a sandbox** (sandbox-exec / AppArmor /
   firejail) so a malicious `exec_tcl` payload can't escape.
3. **Don't `fpga-mcp setup --register` on a shared host** — the config
   snippet written to the MCP client contains a path to your local
   `fpga-mcp` binary.
4. **Audit tool calls in your MCP client.** Claude Desktop, Cursor, etc.
   show every tool invocation — review what the AI is sending before
   approving.
5. **Pin to a specific tag in your MCP client config:**
   ```jsonc
   { "mcpServers": { "fpga-mcp": { "command": "/path/to/venv/bin/fpga-mcp",
                                    "args": ["run"] } } }
   ```
   Avoid `pip install -U fpga-mcp` auto-bumping in production.
