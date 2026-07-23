"""EDA backend transports.

Each module in this package implements one vendor's flow driver. The shared
contract is :class:`fpga_mcp.transports.base.EDABackend`.
"""

from __future__ import annotations

from fpga_mcp.transports.base import (
    BackendError,
    BackendNotConnectedError,
    EDABackend,
    Project,
    ProjectHandle,
    RunResult,
    TimingReport,
    UtilizationReport,
)
from fpga_mcp.transports.factory import get_backend, list_backends

__all__ = [
    "BackendError",
    "BackendNotConnectedError",
    "EDABackend",
    "Project",
    "ProjectHandle",
    "RunResult",
    "TimingReport",
    "UtilizationReport",
    "get_backend",
    "list_backends",
]
