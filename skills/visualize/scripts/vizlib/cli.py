"""The ``viz`` command line.

``viz render`` turns an engine's native source file into an image. This module
owns argument parsing; the render dispatch is wired alongside the delivery
layer.
"""
from __future__ import annotations

import argparse


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
