"""The mingrammer/diagrams engine.

Renders a diagrams script — Python that uses the ``diagrams`` library — to an
image. The script runs in a subprocess, so a failure is captured cleanly and
never pollutes this process; the engine passes the output base path and format
through the ``VIZ_OUT`` and ``VIZ_FORMAT`` environment variables.

Trusted local source only. The script is executed as Python. A later delivery
slice must not feed this engine a diagrams source authored by an untrusted
party without sandboxing — executing that would be a remote-code-execution
surface.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys

from .base import EngineError, MissingDependencyError, RenderResult

_INSTALL_HINT = (
    "the diagrams engine needs the Graphviz binary and the 'diagrams' package. "
    "install Graphviz (macOS: 'brew install graphviz'; Debian/Ubuntu: "
    "'apt-get install graphviz') and the package ('pip install diagrams')."
)


class DiagramsEngine:
    """Renders mingrammer/diagrams source to PNG or SVG.

    PNG is self-contained. SVG references its vendor icons by local file path,
    so an SVG does not move between machines intact — prefer PNG when the image
    leaves this machine.
    """

    name = "diagrams"
    formats = ("png", "svg")

    def check_deps(self) -> None:
        """Raise MissingDependencyError, naming Graphviz, when the ``dot``
        binary or the ``diagrams`` package is absent."""
        missing = []
        if shutil.which("dot") is None:
            missing.append("the Graphviz 'dot' binary")
        if importlib.util.find_spec("diagrams") is None:
            missing.append("the 'diagrams' package")
        if missing:
            raise MissingDependencyError(f"{', '.join(missing)} not found — {_INSTALL_HINT}")

    def render(self, source: str, fmt: str, out_path: str) -> RenderResult:
        """Run the diagrams script at ``source`` and return its rendered image.

        The script reads ``VIZ_OUT`` (the output path without extension) and
        ``VIZ_FORMAT`` and passes them to ``Diagram(...)``. On any failure the
        engine leaves no partial output file behind.
        """
        self.check_deps()
        if fmt not in self.formats:
            raise EngineError(
                f"diagrams cannot render format {fmt!r}; supported: {', '.join(self.formats)}"
            )

        base = os.path.splitext(os.path.abspath(out_path))[0]
        expected = f"{base}.{fmt}"
        self._remove_if_present(expected)

        env = {**os.environ, "VIZ_OUT": base, "VIZ_FORMAT": fmt}
        proc = subprocess.run(
            [sys.executable, os.path.abspath(source)],
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            self._remove_if_present(expected)
            raise EngineError(
                f"diagrams source failed (exit {proc.returncode}):\n{proc.stderr.strip()}"
            )
        if not os.path.exists(expected):
            raise EngineError(
                f"diagrams source ran but produced no file at {expected}. the source "
                "must pass filename=os.environ['VIZ_OUT'] and "
                "outformat=os.environ['VIZ_FORMAT'] to Diagram(...)."
            )
        return RenderResult(engine=self.name, format=fmt, path=expected)

    @staticmethod
    def _remove_if_present(path: str) -> None:
        """Delete ``path`` if it exists, so a failed render leaves nothing."""
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
