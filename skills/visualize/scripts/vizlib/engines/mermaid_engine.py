"""The Mermaid engine.

Renders Mermaid source — a declarative diagram document — to SVG or PNG with
mermaidx (pure Python, the real Mermaid v11, no headless browser).

Unlike the diagrams engine, Mermaid source is data, not code: it is passed to
the renderer, never executed. There is no subprocess and no code-execution
surface.
"""
from __future__ import annotations

import importlib.util
import os

from .base import EngineError, MissingDependencyError, RenderResult, remove_if_present

_INSTALL_HINT = "the mermaid engine needs the 'mermaidx' package ('pip install mermaidx')."


class MermaidEngine:
    """Renders Mermaid source to SVG or PNG via mermaidx, in-process."""

    name = "mermaid"
    formats = ("svg", "png")

    def check_deps(self) -> None:
        """Raise MissingDependencyError naming mermaidx when it is not installed."""
        if importlib.util.find_spec("mermaidx") is None:
            raise MissingDependencyError(f"the 'mermaidx' package not found — {_INSTALL_HINT}")

    def render(self, source: str, fmt: str, out_path: str) -> RenderResult:
        """Render the Mermaid source file at ``source`` to ``out_path``.

        The source is Mermaid text, rendered in-process. On any failure the
        engine leaves no partial output file behind."""
        self.check_deps()
        if fmt not in self.formats:
            raise EngineError(
                f"mermaid cannot render format {fmt!r}; supported: {', '.join(self.formats)}"
            )
        import mermaidx

        out_path = os.path.abspath(out_path)
        if not os.path.exists(source):
            raise EngineError(f"mermaid source file not found: {source}")
        remove_if_present(out_path)
        try:
            with open(source, encoding="utf-8") as f:
                text = f.read()
            mermaidx.Diagram(text).save(out_path, format=fmt)
        except Exception as exc:  # mermaidx raises on invalid source
            remove_if_present(out_path)
            raise EngineError(f"mermaid source failed to render: {exc}") from exc
        if not os.path.exists(out_path):
            raise EngineError(f"mermaid render produced no file at {out_path}.")
        return RenderResult(engine=self.name, format=fmt, path=out_path)
