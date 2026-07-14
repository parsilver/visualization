"""The ``viz`` command line.

``viz render`` turns an engine's native source file into an image and reports
where it landed. This module owns argument parsing and the render dispatch; it
is the composition root that registers the shipped engines.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .delivery import github as github_delivery
from .delivery import local as local_delivery
from .engines.base import EngineError
from .engines.diagrams_engine import DiagramsEngine
from .engines.matplotlib_engine import MatplotlibEngine
from .engines.mermaid_engine import MermaidEngine
from .registry import Registry, UnknownEngineError


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    ``render`` requires an engine, an input source file, and an output path;
    the format defaults to png.
    """
    parser = argparse.ArgumentParser(
        prog="viz",
        description="Render diagrams and charts to image files.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render", help="Render a source file to an image.")
    render.add_argument("--engine", required=True, help="Engine name, e.g. diagrams.")
    render.add_argument(
        "--input", required=True, dest="input", help="Path to the engine's source file."
    )
    render.add_argument(
        "--out", required=True, help="Output image path; its extension sets the format unless --format is given."
    )
    render.add_argument(
        "--format",
        default=None,
        help="Output format; overrides the --out extension. Default: the --out extension, or png.",
    )

    github = sub.add_parser(
        "github", help="Deliver a diagram to GitHub (native block or committed raster URL)."
    )
    github.add_argument("--engine", required=True, help="Engine name, e.g. mermaid.")
    github.add_argument("--input", required=True, dest="input", help="Path to the engine's source file.")
    github.add_argument(
        "--out",
        default=None,
        help="Output image path for the raster mode; its extension sets the format unless --format is given.",
    )
    github.add_argument("--format", default=None, help="Raster output format; overrides the --out extension.")
    github.add_argument(
        "--mode",
        choices=("block", "raster"),
        default=None,
        help="Delivery mode; default: block for mermaid, raster otherwise.",
    )
    github.add_argument("--branch", default="assets", help="Assets branch for the committed raster. Default: assets.")
    return parser


def _resolve_format(fmt: str | None, out_path: str) -> str:
    """The output format: the explicit ``--format`` when given, else the
    ``--out`` extension, else png."""
    if fmt:
        return fmt
    ext = os.path.splitext(out_path)[1].lstrip(".").lower()
    return ext or "png"


def _default_registry() -> Registry:
    """Build the registry with the engines shipped in this plugin."""
    registry = Registry()
    registry.register(DiagramsEngine())
    registry.register(MermaidEngine())
    registry.register(MatplotlibEngine())
    return registry


def run_render(args: argparse.Namespace, registry: Registry) -> int:
    """Render one source through the chosen engine and print a JSON result.

    Returns a process exit code: 0 on success, 2 for an unknown engine, 1 for a
    missing dependency or a render failure.
    """
    try:
        engine = registry.get(args.engine)
    except UnknownEngineError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        result = engine.render(args.input, _resolve_format(args.format, args.out), args.out)
    except EngineError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    path = local_delivery.deliver(result)
    print(json.dumps({"engine": result.engine, "format": result.format, "path": path}))
    return 0


def run_github(args: argparse.Namespace, registry: Registry) -> int:
    """Deliver a diagram to GitHub and print a JSON result.

    The raster mode renders the source first (through the same registry as
    ``render``) and requires ``--out``; the block mode reads the source
    directly. Returns a process exit code: 0 on success, 2 for an unknown
    engine or a bad argument, 1 for a render or delivery failure.
    """
    resolved_mode = args.mode or ("block" if args.engine == "mermaid" else "raster")
    cwd = os.getcwd()
    try:
        if resolved_mode == "raster":
            if not args.out:
                print("raster delivery needs --out", file=sys.stderr)
                return 2
            engine = registry.get(args.engine)
            result = engine.render(args.input, _resolve_format(args.format, args.out), args.out)
            delivered = github_delivery.deliver_github(
                engine=args.engine, cwd=cwd, image_path=result.path,
                branch=args.branch, mode="raster",
            )
        else:
            delivered = github_delivery.deliver_github(
                engine=args.engine, cwd=cwd, source=args.input,
                branch=args.branch, mode="block",
            )
    except UnknownEngineError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (EngineError, github_delivery.GitHubDeliveryError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({
        "strategy": delivered.strategy,
        "output": delivered.output,
        "guidance": delivered.guidance,
    }))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    registry = _default_registry()
    if args.command == "render":
        return run_render(args, registry)
    if args.command == "github":
        return run_github(args, registry)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
