# syntax=docker/dockerfile:1.7
#
# Container image for fpga-mcp.
#
# This image ships the MCP server only — it does NOT include Vivado,
# Quartus or TangDynasty (those are gigabyte-sized commercial EDA tools
# that can't be redistributed). Run this container on a host that has the
# EDA tool installed, or alongside a sidecar that does.
#
# The container's job is to:
#   - Run `fpga-mcp run` (stdio MCP server) so an MCP client can connect.
#   - Optionally reach a Tcl TCP server running on the host or in another
#     container via FPGA_MCP_VIVADO_HOST / _QUARTUS_HOST / _ANLOGIC_HOST.
#
# Build:
#   docker build -t fpga-mcp:dev .
#
# Run as a stdio MCP server (Claude Desktop / Cursor / etc. typically
# launch it via stdio):
#   docker run --rm -i fpga-mcp:dev
#
# Run with a Tcl server on the host network:
#   docker run --rm --network=host \
#     -e FPGA_MCP_VIVADO_HOST=127.0.0.1 \
#     -e FPGA_MCP_VIVADO_PORT=9999 \
#     fpga-mcp:dev
#
# Run a one-off CLI command:
#   docker run --rm fpga-mcp:dev version
#   docker run --rm fpga-mcp:dev backends
#   docker run --rm fpga-mcp:dev doctor

ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim AS builder

# Build deps for any C extensions in our deps tree (none today, but keep
# the layer in case a future dep needs gcc).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy just the packaging metadata first so this layer caches across
# source-only changes.
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY tcl/ ./tcl/
COPY methodology/ ./methodology/

# Build a wheel. --no-deps so we don't pull deps into the build artifacts;
# we install them separately in the runtime stage for clarity.
RUN python -m pip install --no-cache-dir --upgrade pip build hatchling \
    && python -m build --wheel --no-isolation

# -----------------------------------------------------------------------------
# Runtime stage — slim image with just the runtime deps + the wheel.
# -----------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

LABEL org.opencontainers.image.title="fpga-mcp"
LABEL org.opencontainers.image.description="Open multi-vendor MCP server for Vivado, Quartus and Anlogic FPGA toolchains"
LABEL org.opencontainers.image.source="https://github.com/wmm246/fpga-mcp"
LABEL org.opencontainers.image.licenses="MIT"

# Runtime deps only — no build tools, no EDA tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        # typer/rich work fine without these but tput helps `fpga-mcp doctor`
        # format output on real terminals.
        ncurses-base \
    && rm -rf /var/lib/apt/lists/*

# Copy the wheel from the builder stage and install.
COPY --from=builder /build/dist/*.whl /tmp/

RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /tmp/*.whl \
    && rm /tmp/*.whl

# Non-root user — the MCP server shouldn't need root.
RUN useradd --create-home --uid 1000 fpga
USER fpga
WORKDIR /home/fpga

# Default entrypoint: stdio MCP server.
# Override with `docker run fpga-mcp:dev <command>` for one-off CLI invocations.
ENTRYPOINT ["fpga-mcp"]
CMD ["run"]

# Smoke check: if the image can't print its version, something's broken.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD fpga-mcp version || exit 1
