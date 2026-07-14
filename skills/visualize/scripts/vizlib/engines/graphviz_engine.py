"""The Graphviz DOT engine.

Renders a DOT graph — the Graphviz declarative graph language — to an image by
invoking the ``dot`` binary directly: ``dot -T<format> <source> -o <output>``.

DOT source is data, rendered by ``dot`` and never executed, so this engine
carries no code-execution surface — like the mermaid engine, and unlike the
diagrams and matplotlib engines, which run their source as Python. The ``dot``
binary is the same one the diagrams engine already requires, so the engine adds
no new package dependency.
"""
from __future__ import annotations

import os
import shutil
import subprocess

from .base import EngineError, MissingDependencyError, RenderResult, remove_if_present

_INSTALL_HINT = (
    "the graphviz engine needs the Graphviz 'dot' binary. install Graphviz "
    "(macOS: 'brew install graphviz'; Debian/Ubuntu: 'apt-get install graphviz')."
)


class GraphvizEngine:
    """Renders a DOT graph to PNG or SVG through the ``dot`` binary.

    The source is a DOT document; the CLI's ``--out`` / ``--format`` control the
    output directly, with no environment-variable contract (the mermaid model).
    """

    name = "graphviz"
    formats = ("png", "svg")

    def check_deps(self) -> None:
        """Raise MissingDependencyError, naming Graphviz and how to install it,
        when the ``dot`` binary is absent."""
        if shutil.which("dot") is None:
            raise MissingDependencyError(f"the Graphviz 'dot' binary not found — {_INSTALL_HINT}")

    def render(self, source: str, fmt: str, out_path: str) -> RenderResult:
        """Render the DOT source file at ``source`` to ``out_path`` in ``fmt``.

        Runs ``dot`` in a subprocess and writes the image directly to
        ``out_path``. On any failure the engine leaves no partial output file
        behind."""
        self.check_deps()
        if fmt not in self.formats:
            raise EngineError(
                f"graphviz cannot render format {fmt!r}; supported: {', '.join(self.formats)}"
            )

        out_path = os.path.abspath(out_path)
        if not os.path.exists(source):
            raise EngineError(f"graphviz source file not found: {source}")
        remove_if_present(out_path)
        proc = subprocess.run(
            ["dot", f"-T{fmt}", os.path.abspath(source), "-o", out_path],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            remove_if_present(out_path)
            raise EngineError(
                f"graphviz (dot) failed (exit {proc.returncode}):\n{proc.stderr.strip()}"
            )
        if not os.path.exists(out_path):
            raise EngineError(f"graphviz produced no file at {out_path}.")
        return RenderResult(engine=self.name, format=fmt, path=out_path)
