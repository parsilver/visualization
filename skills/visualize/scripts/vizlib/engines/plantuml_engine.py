"""The PlantUML engine.

Renders a PlantUML document — the declarative PlantUML diagram language — to an
image by piping the source through the ``plantuml`` command:
``plantuml -t<format> -pipe`` reads the diagram on stdin and writes the image on
stdout, so the engine controls the exact output path.

PlantUML source is not executed as a program, so this engine has no
arbitrary-code-execution surface. Its preprocessor, however, can ``!include``
local files and fetch URLs — a file-disclosure/SSRF surface that Mermaid text
and DOT do not have — so the engine is trusted-local-source only. A future
delivery path that accepts PlantUML from an untrusted author must restrict the
preprocessor (e.g. via ``PLANTUML_SECURITY_PROFILE``), not only sandbox Python.
"""
from __future__ import annotations

import os
import shutil
import subprocess

from .base import EngineError, MissingDependencyError, RenderResult, remove_if_present

_INSTALL_HINT = (
    "the plantuml engine needs the 'plantuml' command. install PlantUML "
    "(macOS: 'brew install plantuml'; Debian/Ubuntu: 'apt-get install plantuml')."
)


class PlantumlEngine:
    """Renders a PlantUML document to PNG or SVG through the ``plantuml`` command.

    The source is piped to ``plantuml -pipe``; the CLI's ``--out`` / ``--format``
    control the output directly, with no environment-variable contract (the
    mermaid model).
    """

    name = "plantuml"
    formats = ("png", "svg")

    def check_deps(self) -> None:
        """Raise MissingDependencyError, naming PlantUML and how to install it,
        when the ``plantuml`` command is absent."""
        if shutil.which("plantuml") is None:
            raise MissingDependencyError(f"the 'plantuml' command not found — {_INSTALL_HINT}")

    def render(self, source: str, fmt: str, out_path: str) -> RenderResult:
        """Render the PlantUML source file at ``source`` to ``out_path`` in ``fmt``.

        Pipes the source through ``plantuml`` and writes the captured image to
        ``out_path`` only on a clean exit. Any stale output is cleared before the
        run, so on any failure no file survives at ``out_path`` — plantuml's
        error image is never written as a false success."""
        self.check_deps()
        if fmt not in self.formats:
            raise EngineError(
                f"plantuml cannot render format {fmt!r}; supported: {', '.join(self.formats)}"
            )

        out_path = os.path.abspath(out_path)
        if not os.path.isfile(source):
            raise EngineError(f"plantuml source file not found: {source}")
        with open(source, "rb") as f:
            source_bytes = f.read()
        remove_if_present(out_path)
        proc = subprocess.run(
            ["plantuml", f"-t{fmt}", "-pipe", "-failfast2"],
            input=source_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            raise EngineError(
                f"plantuml failed (exit {proc.returncode}):\n"
                f"{proc.stderr.decode(errors='replace').strip()}"
            )
        if not proc.stdout:
            raise EngineError(f"plantuml produced no output for {out_path}.")
        with open(out_path, "wb") as f:
            f.write(proc.stdout)
        return RenderResult(engine=self.name, format=fmt, path=out_path)
