"""Local-file delivery.

The engine has already written the image to disk; local delivery confirms it
exists and reports its absolute path — the form every other surface (GitHub,
docs, a Claude Code response) consumes.
"""
from __future__ import annotations

import os

from ..engines.base import RenderResult


def deliver(result: RenderResult) -> str:
    """Return the absolute path of the rendered file.

    The engine has already confirmed the file exists before returning its
    RenderResult, so local delivery only normalizes the path to absolute."""
    return os.path.abspath(result.path)
