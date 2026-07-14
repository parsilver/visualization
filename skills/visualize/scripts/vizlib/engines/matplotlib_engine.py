"""The matplotlib engine.

Renders a matplotlib script — Python that builds a figure with the
``matplotlib`` library — to an image. The script runs in a subprocess, so a
failure is captured cleanly and never pollutes this process or matplotlib's
global pyplot state; the engine passes the output base path and format through
the ``VIZ_OUT`` and ``VIZ_FORMAT`` environment variables, and forces the
headless ``Agg`` backend with ``MPLBACKEND`` so a render never needs a display.

Trusted local source only. The script is executed as Python. A later delivery
slice must not feed this engine a matplotlib source authored by an untrusted
party without sandboxing — executing that would be a remote-code-execution
surface. The mermaid engine, whose source is data, carries no such surface;
this engine, like diagrams, does.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

from .base import EngineError, MissingDependencyError, RenderResult, remove_if_present

_INSTALL_HINT = (
    "the matplotlib engine needs the 'matplotlib' package ('pip install matplotlib')."
)


class MatplotlibEngine:
    """Renders a matplotlib script to PNG or SVG.

    The script builds a figure and writes it with ``savefig`` to the path the
    CLI chose, read from ``VIZ_OUT`` / ``VIZ_FORMAT``. Both formats are
    self-contained, so either moves between machines intact.
    """

    name = "matplotlib"
    formats = ("png", "svg")

    def check_deps(self) -> None:
        """Raise MissingDependencyError, naming matplotlib and how to install
        it, when the ``matplotlib`` package is absent."""
        if importlib.util.find_spec("matplotlib") is None:
            raise MissingDependencyError(f"the 'matplotlib' package not found — {_INSTALL_HINT}")

    def render(self, source: str, fmt: str, out_path: str) -> RenderResult:
        """Run the matplotlib script at ``source`` and return its rendered image.

        The script reads ``VIZ_OUT`` (the output path without extension) and
        ``VIZ_FORMAT`` and passes them to ``savefig``. The subprocess runs with
        the headless ``Agg`` backend forced, so no display is required. On any
        failure the engine leaves no partial output file behind.
        """
        self.check_deps()
        if fmt not in self.formats:
            raise EngineError(
                f"matplotlib cannot render format {fmt!r}; supported: {', '.join(self.formats)}"
            )

        base = os.path.splitext(os.path.abspath(out_path))[0]
        expected = f"{base}.{fmt}"
        remove_if_present(expected)

        env = {**os.environ, "VIZ_OUT": base, "VIZ_FORMAT": fmt, "MPLBACKEND": "Agg"}
        proc = subprocess.run(
            [sys.executable, os.path.abspath(source)],
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            remove_if_present(expected)
            raise EngineError(
                f"matplotlib source failed (exit {proc.returncode}):\n{proc.stderr.strip()}"
            )
        if not os.path.exists(expected):
            raise EngineError(
                f"matplotlib source ran but produced no file at {expected}. the source must "
                "call savefig to '<VIZ_OUT>.<VIZ_FORMAT>' (read from the environment)."
            )
        return RenderResult(engine=self.name, format=fmt, path=expected)
