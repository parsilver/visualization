"""The engine registry: the extension point of the renderer.

A new engine registers here and the CLI can dispatch to it with no other
change. An unknown name fails loudly, listing what is registered so the caller
can correct the request.
"""
from __future__ import annotations

from .engines.base import Engine


class UnknownEngineError(Exception):
    """Raised when a name has no registered engine. The message lists the
    registered names."""


class Registry:
    """A name-to-Engine map with explicit registration and lookup."""

    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}

    def register(self, engine: Engine) -> None:
        """Register ``engine`` under its ``name``. A duplicate name is a
        programming error and raises ValueError."""
        if engine.name in self._engines:
            raise ValueError(f"engine already registered: {engine.name}")
        self._engines[engine.name] = engine

    def get(self, name: str) -> Engine:
        """Return the engine registered under ``name``, or raise
        UnknownEngineError listing the registered names."""
        try:
            return self._engines[name]
        except KeyError:
            known = ", ".join(self.names()) or "(none)"
            raise UnknownEngineError(
                f"unknown engine: {name!r}. registered engines: {known}"
            ) from None

    def names(self) -> list[str]:
        """The registered engine names, sorted."""
        return sorted(self._engines)
