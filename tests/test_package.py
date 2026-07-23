"""Ensure the package's __init__ exports the expected surface."""

from __future__ import annotations

import fpga_mcp


def test_version_is_pep440_like():
    assert isinstance(fpga_mcp.__version__, str)
    assert "." in fpga_mcp.__version__


def test_all_export():
    assert fpga_mcp.__all__ == ["__version__"]
