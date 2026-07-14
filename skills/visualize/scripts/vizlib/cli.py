"""The ``viz`` command line.

``viz render`` turns an engine's native source file into an image and reports
where it landed. This module owns argument parsing and the render dispatch; it
is the composition root that registers the shipped engines.
"""
from __future__ import annotations

import argparse
import json
import sys

from .delivery import local as local_delivery
from .engines.base import EngineError
from .engines.diagrams_engine import DiagramsEngine
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
    render.add_argument("--out", required=True, help="Output image path.")
    render.add_argument("--format", default="png", help="Output format (default: png).")
    return parser


def _default_registry() -> Registry:
    """Build the registry with the engines shipped in this plugin."""
    registry = Registry()
    registry.register(DiagramsEngine())
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
        result = engine.render(args.input, args.format, args.out)
    except EngineError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    path = local_delivery.deliver(result)
    print(json.dumps({"engine": result.engine, "format": result.format, "path": path}))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "render":
        return run_render(args, _default_registry())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
