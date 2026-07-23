"""Entry point so `python -m fpga_mcp` works."""

from __future__ import annotations

from fpga_mcp.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
