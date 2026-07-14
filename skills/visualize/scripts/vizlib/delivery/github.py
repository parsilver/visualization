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

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable

_RAW_HOST = "https://raw.githubusercontent.com"

# A git ref name we are willing to write and put in a URL: the safe subset of
# git's ref rules, with the sequences that let a name escape its ref namespace
# (`..`, leading `-`/`/`, trailing `/`, `//`) rejected outright.
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class GitHubDeliveryError(Exception):
    """A GitHub delivery step failed — a git command, or the environment it
    needs. The message is surfaced to the caller verbatim."""


Runner = Callable[..., str]


def _run(args: list[str], cwd: str, *, check: bool = True, extra_env: dict | None = None) -> str:
    """Run a subprocess in ``cwd`` and return its stdout.

    ``shell=False`` (args is a list), so no argument is shell-interpreted. With
    ``check`` set, a non-zero exit raises GitHubDeliveryError; with it clear,
    the caller inspects the (possibly empty) stdout — used for existence probes.
    ``extra_env`` is layered over the current environment."""
    env = {**os.environ, **extra_env} if extra_env else None
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)
    if check and proc.returncode != 0:
        raise GitHubDeliveryError(
            f"command failed: {' '.join(args)}\n{proc.stderr.strip()}"
        )
    return proc.stdout

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


def _validate_branch(branch: str) -> None:
    """Raise ValueError unless ``branch`` is a safe ref name.

    The name is written to ``refs/heads/`` and embedded in a URL, so anything
    that could escape the ref namespace or the URL path is rejected."""
    if (
        not branch
        or branch != branch.strip()
        or ".." in branch
        or "//" in branch
        or branch.startswith("-")
        or branch.startswith("/")
        or branch.endswith("/")
        or _BRANCH_RE.match(branch) is None
    ):
        raise ValueError(f"invalid branch name: {branch!r}")


def _rev_parse(ref: str, cwd: str, run: Runner) -> str | None:
    """Return the commit SHA ``ref`` resolves to, or None when it does not
    exist — the probe that decides orphan-start vs. append."""
    out = run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd, check=False,
    ).strip()
    return out or None


def _checked_out_branch(cwd: str, run: Runner) -> str | None:
    """The full ref of the branch HEAD points at (``refs/heads/…``), or None
    when HEAD is detached — used to refuse moving the branch under HEAD."""
    ref = run(["git", "symbolic-ref", "--quiet", "HEAD"], cwd, check=False).strip()
    return ref or None


def _identity_env(cwd: str, run: Runner) -> dict:
    """A committer identity for ``commit-tree`` when the repo has none.

    Returns an empty dict when ``user.name``/``user.email`` are configured, so
    the repo's own identity wins; otherwise a neutral fallback so the commit
    does not fail on an unconfigured machine."""
    name = run(["git", "config", "user.name"], cwd, check=False).strip()
    email = run(["git", "config", "user.email"], cwd, check=False).strip()
    if name and email:
        return {}
    return {
        "GIT_AUTHOR_NAME": "viz", "GIT_AUTHOR_EMAIL": "viz@localhost",
        "GIT_COMMITTER_NAME": "viz", "GIT_COMMITTER_EMAIL": "viz@localhost",
    }


def commit_image_to_branch(
    image_path: str, branch: str, cwd: str, *, run: Runner = _run
) -> str:
    """Commit the image at ``image_path`` onto ``branch`` and return its tree path.

    The commit is built with git plumbing against a temporary index, so the
    working tree, the real index, and HEAD are all left untouched — only the
    ``refs/heads/<branch>`` ref moves. That guarantee holds only while
    ``branch`` is not the checked-out branch, so committing onto the checked-out
    branch is refused rather than moving HEAD under a static index. When the
    branch already exists the new commit is appended to it; otherwise it starts
    an orphan branch. The image is stored at ``viz/<blob-sha><ext>``: the
    filename is git's own content hash, so identical images dedupe; only the
    extension is caller-supplied, and it is a single constrained path component.

    Does not push. Raises ValueError for an unsafe branch name, and
    GitHubDeliveryError for a failed git command or a checked-out target branch."""
    _validate_branch(branch)
    if _checked_out_branch(cwd, run) == f"refs/heads/{branch}":
        raise GitHubDeliveryError(
            f"the '{branch}' branch is currently checked out; switch to another "
            "branch before delivering, so the commit does not move HEAD."
        )
    blob = run(["git", "hash-object", "-w", "--", image_path], cwd).strip()
    ext = os.path.splitext(image_path)[1]
    tree_path = f"viz/{blob}{ext}"
    parent = _rev_parse(f"refs/heads/{branch}", cwd, run)

    with tempfile.TemporaryDirectory() as tmp:
        index_env = {"GIT_INDEX_FILE": os.path.join(tmp, "index")}
        if parent is not None:
            run(["git", "read-tree", parent], cwd, extra_env=index_env)
        run(
            ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},{tree_path}"],
            cwd, extra_env=index_env,
        )
        tree = run(["git", "write-tree"], cwd, extra_env=index_env).strip()

    message = f"add {tree_path}"
    commit_args = ["git", "commit-tree", tree, "-m", message]
    if parent is not None:
        commit_args += ["-p", parent]
    commit = run(commit_args, cwd, extra_env=_identity_env(cwd, run)).strip()
    run(["git", "update-ref", f"refs/heads/{branch}", commit], cwd)
    return tree_path


# --- Strategy dispatch ------------------------------------------------------

_PUSH_GUIDANCE = (
    "Committed to the '{branch}' branch locally. Run 'git push origin {branch}' "
    "to publish it; the URL resolves once the push completes."
)

_LOCAL_GUIDANCE = (
    "This is not a confirmed public GitHub repository, so a "
    "raw.githubusercontent.com URL would not render (private raw content is "
    "blocked for GitHub's image proxy). Drag the image at the path above into "
    "the GitHub web editor to attach it to an issue, pull request, or comment."
)


@dataclass(frozen=True)
class GitHubResult:
    """The outcome of a GitHub delivery.

    Attributes:
        strategy: which path ran — "mermaid-block", "raster-url", or
            "local-guidance".
        output: the block text, the raw URL, or the local image path.
        guidance: the next step for the user (the push command, or how to place
            the image by hand); None when none is needed."""

    strategy: str
    output: str
    guidance: str | None = None


def remote_url(cwd: str, run: Runner = _run) -> str | None:
    """The URL of the ``origin`` remote in ``cwd``, or None when there is none."""
    try:
        out = run(["git", "remote", "get-url", "origin"], cwd, check=False).strip()
    except OSError:
        return None
    return out or None


def repo_visibility(cwd: str, run: Runner = _run) -> str | None:
    """The repo's visibility ("public"/"private"/…) via ``gh``, or None.

    None means the answer could not be confirmed — ``gh`` is absent,
    unauthenticated, or errored — and the caller treats that as not-public."""
    try:
        out = run(
            ["gh", "repo", "view", "--json", "visibility", "-q", ".visibility"],
            cwd, check=False,
        ).strip()
    except OSError:
        return None
    return out.lower() or None


def deliver_github(
    *,
    engine: str,
    cwd: str,
    source: str | None = None,
    image_path: str | None = None,
    branch: str = "assets",
    mode: str | None = None,
    visibility: str | None = None,
    run: Runner = _run,
) -> GitHubResult:
    """Deliver a diagram to GitHub, choosing the embed that renders there.

    ``mode`` forces "block" or "raster"; unset, it is "block" for the mermaid
    engine and "raster" otherwise. Block delivery reads the Mermaid ``source``
    and returns a fenced block. Raster delivery needs a rendered ``image_path``:
    on a confirmed public GitHub repo it commits the image and returns its raw
    URL; on anything else it returns the local path plus placement guidance.
    ``visibility`` overrides the ``gh`` probe (mainly for tests). Never pushes.
    """
    resolved_mode = mode or ("block" if engine == "mermaid" else "raster")

    if resolved_mode == "block":
        if engine != "mermaid":
            raise ValueError(f"a mermaid block needs mermaid source, not {engine!r}")
        if source is None:
            raise ValueError("block delivery needs the mermaid source path")
        if not os.path.exists(source):
            raise GitHubDeliveryError(f"mermaid source file not found: {source}")
        with open(source, encoding="utf-8") as f:
            text = f.read()
        return GitHubResult("mermaid-block", mermaid_block(text))

    if image_path is None:
        raise ValueError("raster delivery needs a rendered image path")
    local = os.path.abspath(image_path)

    remote = remote_url(cwd, run)
    parsed = parse_github_remote(remote) if remote else None
    if parsed is None:
        return GitHubResult("local-guidance", local, _LOCAL_GUIDANCE)

    vis = visibility if visibility is not None else repo_visibility(cwd, run)
    if vis != "public":
        return GitHubResult("local-guidance", local, _LOCAL_GUIDANCE)

    owner, repo = parsed
    tree_path = commit_image_to_branch(image_path, branch, cwd, run=run)
    url = raw_url(owner, repo, branch, tree_path)
    return GitHubResult("raster-url", url, _PUSH_GUIDANCE.format(branch=branch))
