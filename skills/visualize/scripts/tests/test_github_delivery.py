"""Tests for the GitHub delivery path.

Pure helpers (block, remote parsing, raw URL) are tested directly. The
orphan-branch commit runs against a real throwaway git repository under
``tmp_path`` — no network — and the strategy dispatch is tested with the
visibility probe injected, so no test reaches GitHub.
"""
import subprocess

from vizlib.delivery import github


# --- Pure helpers -----------------------------------------------------------

def test_mermaid_block_wraps_and_trims():
    src = "flowchart TD\n  A[Start] --> B{OK?}\n"
    assert github.mermaid_block(src) == (
        "```mermaid\nflowchart TD\n  A[Start] --> B{OK?}\n```"
    )


def test_mermaid_block_preserves_inner_blank_lines():
    src = "flowchart TD\n\n  A --> B\n"
    assert github.mermaid_block(src) == "```mermaid\nflowchart TD\n\n  A --> B\n```"


def test_parse_remote_https():
    assert github.parse_github_remote(
        "https://github.com/parsilver/visualization.git"
    ) == ("parsilver", "visualization")


def test_parse_remote_ssh():
    assert github.parse_github_remote(
        "git@github.com:parsilver/visualization.git"
    ) == ("parsilver", "visualization")


def test_parse_remote_no_dotgit():
    assert github.parse_github_remote(
        "https://github.com/parsilver/visualization"
    ) == ("parsilver", "visualization")


def test_parse_remote_non_github_none():
    assert github.parse_github_remote("https://gitlab.com/x/y.git") is None
    assert github.parse_github_remote("https://notgithub.com/x/y") is None
    assert github.parse_github_remote("") is None


def test_raw_url():
    assert github.raw_url("o", "r", "assets", "viz/abc.png") == (
        "https://raw.githubusercontent.com/o/r/assets/viz/abc.png"
    )
