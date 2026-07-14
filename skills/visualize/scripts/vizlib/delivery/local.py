"""Local-file delivery.

The engine has already written the image to disk; local delivery confirms it
exists and reports its absolute path — the form every other surface (GitHub,
docs, a Claude Code response) consumes.
"""
from __future__ import annotations

import os

from ..engines.base import RenderResult


def deliver(result: RenderResult) -> str:
    """Return the absolute path of the rendered file, confirming it exists."""
    path = os.path.abspath(result.path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"rendered file missing: {path}")
    return path
