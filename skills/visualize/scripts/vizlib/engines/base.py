"""The engine contract.

An engine turns a renderer's own native source — a diagrams script, a Mermaid
document, a DOT graph — into an image file. Engines are looked up by name in
the registry; adding one means implementing this protocol and registering it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class EngineError(Exception):
    """A render could not be produced. The message is surfaced to the caller
    verbatim: a source error, or a missing output the engine expected."""


class MissingDependencyError(EngineError):
    """A required runtime dependency — a binary or a package — is absent. The
    message names the dependency and the command that installs it."""


@dataclass(frozen=True)
class RenderResult:
    """The outcome of a successful render: the engine used, the output format,
    and the absolute path of the file written."""

    engine: str
    format: str
    path: str


def remove_if_present(path: str) -> None:
    """Delete ``path`` if it exists, so a failed render leaves nothing behind.

    Shared by the engines whose ``render`` clears any stale or partial output
    on the failure path."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


@runtime_checkable
class Engine(Protocol):
    """Renders native source to an image file.

    Attributes:
        name: the registry key, e.g. "diagrams".
        formats: the output formats the engine can write, e.g. ("png", "svg").
    """

    name: str
    formats: tuple[str, ...]

    def check_deps(self) -> None:
        """Raise MissingDependencyError, naming the dependency and how to
        install it, when a runtime requirement is absent. Return None when the
        engine is ready to render."""
        ...

    def render(self, source: str, fmt: str, out_path: str) -> RenderResult:
        """Render the source file at ``source`` to ``out_path`` in ``fmt``.

        Return a RenderResult on success. Raise EngineError on failure, leaving
        no partial output file behind."""
        ...
