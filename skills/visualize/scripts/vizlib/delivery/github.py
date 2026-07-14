"""GitHub delivery.

Puts a rendered diagram where a GitHub reader will see it, choosing the embed
that actually renders for the target repository:

- Mermaid source becomes a native fenced ``mermaid`` block — GitHub renders it
  directly, so no image is produced or uploaded.
- Any other image on a **public** repository is committed to an orphan
  ``assets`` branch and delivered as its ``raw.githubusercontent.com`` URL.
- A private repository, a non-GitHub remote, or a visibility that cannot be
  confirmed falls back to the local file plus guidance to place it by hand: a
  private repo's raw content is not served to GitHub's image proxy, so a
  committed URL would never render there.

The commit is made with git plumbing against a temporary index, so it never
disturbs the working tree, index, or HEAD. Delivery never runs ``git push`` and
never reads a token or session cookie — it prints the push command for the user
to run, and the URL resolves once that push lands.
"""
from __future__ import annotations

import re

_RAW_HOST = "https://raw.githubusercontent.com"

_REMOTE_RE = re.compile(
    r"^(?:https?://|git@|ssh://git@)github\.com[:/]"
    r"(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def mermaid_block(source: str) -> str:
    """Wrap Mermaid ``source`` in a fenced ``mermaid`` block for GitHub.

    Surrounding blank lines are trimmed; inner blank lines are preserved. The
    source is copied verbatim — it is never rendered or executed."""
    body = source.strip("\n")
    return f"```mermaid\n{body}\n```"


def parse_github_remote(url: str) -> tuple[str, str] | None:
    """Return ``(owner, repo)`` for a GitHub remote ``url``, or None.

    Handles the HTTPS, SSH (``git@github.com:``), and ``ssh://`` forms, with or
    without a trailing ``.git``. A non-GitHub host returns None so the caller
    takes the local-file fallback rather than building an unusable URL."""
    match = _REMOTE_RE.match(url.strip())
    if match is None:
        return None
    return match.group("owner"), match.group("repo")


def raw_url(owner: str, repo: str, branch: str, path: str) -> str:
    """Build the ``raw.githubusercontent.com`` URL for ``path`` on ``branch``.

    The URL resolves only once the branch is pushed to the remote and only for
    a public repository."""
    return f"{_RAW_HOST}/{owner}/{repo}/{branch}/{path}"
