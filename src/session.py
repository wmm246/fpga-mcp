"""Backend session manager.

A single place that owns backend instances, tracks the active one, and lets
tools switch between vendors at runtime. The MCP server constructs one
:class:`BackendManager` and shares it with every tool group.
"""

from __future__ import annotations

from fpga_mcp.config import Config
from fpga_mcp.transports.base import (
    BackendError,
    EDABackend,
    ProjectHandle,
)
from fpga_mcp.transports.factory import get_backend, list_backends


class BackendManager:
    """Owns backend instances and tracks the active one.

    Each backend is created lazily on first use so a user without Vivado
    installed can still drive Quartus.
    """

    def __init__(self, config: Config):
        self._config = config
        self._backends: dict[str, EDABackend] = {}
        self._active_name: str = config.active_backend

    # --- selection --------------------------------------------------

    @property
    def active_name(self) -> str:
        return self._active_name

    @property
    def config(self) -> Config:
        return self._config

    def available(self) -> list[str]:
        return list_backends()

    def get(self, name: str | None = None) -> EDABackend:
        """Return (and lazily instantiate) the named backend.

        With no arg, returns the currently-active backend. The backend is
        not connected yet — call ``.connect()`` to verify liveness.
        """
        name = name or self._active_name
        if name not in self._backends:
            self._backends[name] = get_backend(name, self._config)
        return self._backends[name]

    def switch(self, name: str) -> str:
        if name not in list_backends():
            raise BackendError(f"unknown backend '{name}'. Available: {', '.join(list_backends())}")
        old = self._active_name
        self._active_name = name
        self._config.active_backend = name
        return f"switched active backend: {old} -> {name}"

    # --- lifecycle helpers ------------------------------------------

    def ensure_connected(self, name: str | None = None) -> EDABackend:
        backend = self.get(name)
        if not backend.is_connected():
            backend.connect()
        return backend

    def disconnect_all(self) -> None:
        for b in self._backends.values():
            try:
                b.disconnect()
            except Exception:
                pass

    # --- introspection ----------------------------------------------

    def status(self) -> dict[str, dict[str, object]]:
        """Return a snapshot of every backend's connection state."""
        out: dict[str, dict[str, object]] = {}
        for name in list_backends():
            backend = self._backends.get(name)
            try:
                connected = bool(backend and backend.is_connected())
                project: ProjectHandle | None = backend.current_project() if backend else None
            except Exception:
                connected = False
                project = None
            out[name] = {
                "connected": connected,
                "active": name == self._active_name,
                "project": (
                    {
                        "name": project.name,
                        "path": str(project.path),
                        "part": project.part,
                        "top": project.top,
                    }
                    if project
                    else None
                ),
            }
        return out


# A single shared instance for the whole process. Tests create their own
# BackendManager; the CLI / MCP server use this one.
_DEFAULT: BackendManager | None = None


def default_manager(config: Config | None = None) -> BackendManager:
    """Return the process-wide default manager (lazily initialised)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = BackendManager(config or Config.load())
    return _DEFAULT


def reset_default_manager() -> None:
    """Drop the cached default manager. Mainly for tests."""
    global _DEFAULT
    if _DEFAULT is not None:
        _DEFAULT.disconnect_all()
    _DEFAULT = None
