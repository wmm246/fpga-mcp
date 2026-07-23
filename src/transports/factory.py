"""Backend factory.

Single import point for picking the right transport by name. Backends are
imported lazily so a missing optional dependency for one vendor does not
break the others.
"""

from __future__ import annotations

from fpga_mcp.config import Config
from fpga_mcp.transports.base import EDABackend, BackendError

_REGISTRY: dict[str, type[EDABackend]] = {}


def register(name: str, cls: type[EDABackend]) -> None:
    _REGISTRY[name] = cls


def list_backends() -> list[str]:
    # Always make sure the built-ins are registered.
    _ensure_builtin_registered()
    return sorted(_REGISTRY)


def get_backend(name: str | None, config: Config) -> EDABackend:
    """Instantiate the named backend (or the config's active backend)."""
    _ensure_builtin_registered()
    name = name or config.active_backend
    if name not in _REGISTRY:
        raise BackendError(f"unknown backend '{name}'. Available: {', '.join(list_backends())}")
    return _REGISTRY[name](config)


def _ensure_builtin_registered() -> None:
    # Idempotent: imports populate the registry on first call.
    from fpga_mcp.transports import anlogic as _anlogic  # noqa: F401
    from fpga_mcp.transports import quartus as _quartus  # noqa: F401
    from fpga_mcp.transports import vivado as _vivado  # noqa: F401
