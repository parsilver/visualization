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


# --- Orphan-branch commit (real throwaway repo, no network) -----------------

PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-image-payload"


def _init_repo(path, remote="https://github.com/o/r.git"):
    """Initialise a git repo at ``path`` with one commit and an origin remote."""
    def g(*args):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
    g("init", "-b", "main")
    g("config", "user.email", "dev@example.com")
    g("config", "user.name", "Dev")
    (path / "README.md").write_text("seed\n")
    g("add", "README.md")
    g("commit", "-m", "seed")
    g("remote", "add", "origin", remote)


def _git(path, *args):
    return subprocess.run(
        ["git", *args], cwd=path, check=True, capture_output=True, text=True
    ).stdout


def _fake_gh(visibility_out):
    """A runner that fakes only the ``gh repo view`` visibility probe and runs
    every real git command for effect — so a dispatch test needs no
    gh-authenticated repo but still exercises the actual plumbing."""
    def run(args, cwd, *, check=True, extra_env=None):
        if args[:2] == ["gh", "repo"]:
            return visibility_out
        return github._run(args, cwd, check=check, extra_env=extra_env)
    return run


def test_commit_creates_orphan_branch_with_file(tmp_path):
    _init_repo(tmp_path)
    img = tmp_path / "diagram.png"
    img.write_bytes(PNG_BYTES)
    blob = _git(tmp_path, "hash-object", str(img)).strip()

    tree_path = github.commit_image_to_branch(str(img), "assets", str(tmp_path))

    assert tree_path == f"viz/{blob}.png"
    # the branch exists and holds the file with the original bytes
    _git(tmp_path, "rev-parse", "--verify", "refs/heads/assets")
    stored = subprocess.run(
        ["git", "cat-file", "-p", f"assets:{tree_path}"],
        cwd=tmp_path, check=True, capture_output=True,
    ).stdout
    assert stored == PNG_BYTES


def test_commit_leaves_working_tree_and_head_untouched(tmp_path):
    _init_repo(tmp_path)
    head_before = _git(tmp_path, "rev-parse", "HEAD").strip()
    branch_before = _git(tmp_path, "rev-parse", "--abbrev-ref", "HEAD").strip()
    img = tmp_path / "diagram.png"
    img.write_bytes(PNG_BYTES)

    github.commit_image_to_branch(str(img), "assets", str(tmp_path))

    assert _git(tmp_path, "rev-parse", "HEAD").strip() == head_before
    assert _git(tmp_path, "rev-parse", "--abbrev-ref", "HEAD").strip() == branch_before
    # working tree clean apart from the untracked image we wrote
    status = _git(tmp_path, "status", "--porcelain").strip().splitlines()
    assert status == ["?? diagram.png"]
    # the real index is untouched
    assert _git(tmp_path, "diff", "--cached", "--name-only").strip() == ""


def test_commit_second_image_appends_to_branch(tmp_path):
    _init_repo(tmp_path)
    img1 = tmp_path / "a.png"
    img1.write_bytes(PNG_BYTES)
    img2 = tmp_path / "b.png"
    img2.write_bytes(b"\x89PNG\r\n\x1a\nsecond-payload")

    path1 = github.commit_image_to_branch(str(img1), "assets", str(tmp_path))
    path2 = github.commit_image_to_branch(str(img2), "assets", str(tmp_path))

    assert path1 != path2
    # both files live on the branch, and it has two commits (append, no clobber)
    tree = _git(tmp_path, "ls-tree", "-r", "--name-only", "assets").split()
    assert path1 in tree and path2 in tree
    assert _git(tmp_path, "rev-list", "--count", "assets").strip() == "2"


def test_commit_never_pushes_only_plumbing(tmp_path):
    _init_repo(tmp_path)
    img = tmp_path / "diagram.png"
    img.write_bytes(PNG_BYTES)
    allowed = {
        "hash-object", "read-tree", "update-index", "write-tree",
        "commit-tree", "update-ref", "rev-parse", "config",
    }
    seen = []

    def recording_run(args, cwd, *, check=True, extra_env=None):
        assert args[0] == "git", f"non-git command: {args}"
        assert args[1] != "push", "delivery must never push"
        assert args[1] in allowed, f"unexpected git subcommand: {args[1]}"
        seen.append(args[1])
        return github._run(args, cwd, check=check, extra_env=extra_env)

    github.commit_image_to_branch(str(img), "assets", str(tmp_path), run=recording_run)
    assert "commit-tree" in seen and "update-ref" in seen


def test_reject_bad_branch_name(tmp_path):
    _init_repo(tmp_path)
    img = tmp_path / "diagram.png"
    img.write_bytes(PNG_BYTES)
    for bad in ["../evil", "a..b", "-x", "with space", "", "no/trailing/"]:
        try:
            github.commit_image_to_branch(str(img), bad, str(tmp_path))
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for branch {bad!r}")


# --- Strategy dispatch ------------------------------------------------------

def _branch_exists(path, branch):
    return subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=path, capture_output=True,
    ).returncode == 0


def test_mermaid_autoselects_block_strategy(tmp_path):
    mmd = tmp_path / "d.mmd"
    mmd.write_text("flowchart TD\n  A --> B\n")

    def boom(*a, **k):  # no subprocess for a block — it is a pure transform
        raise AssertionError("block delivery must not shell out")

    res = github.deliver_github(
        engine="mermaid", source=str(mmd), cwd=str(tmp_path), run=boom
    )
    assert res.strategy == "mermaid-block"
    assert res.output == "```mermaid\nflowchart TD\n  A --> B\n```"
    assert res.guidance is None


def test_public_raster_returns_url_and_push_cmd(tmp_path):
    _init_repo(tmp_path, remote="https://github.com/o/r.git")
    img = tmp_path / "d.png"
    img.write_bytes(PNG_BYTES)
    blob = _git(tmp_path, "hash-object", str(img)).strip()

    res = github.deliver_github(
        engine="diagrams", image_path=str(img), cwd=str(tmp_path),
        run=_fake_gh("PUBLIC\n"),
    )
    assert res.strategy == "raster-url"
    assert res.output == f"https://raw.githubusercontent.com/o/r/assets/viz/{blob}.png"
    assert "git push origin assets" in res.guidance
    assert _branch_exists(tmp_path, "assets")


def test_private_falls_back_to_guidance(tmp_path):
    _init_repo(tmp_path, remote="https://github.com/o/r.git")
    img = tmp_path / "d.png"
    img.write_bytes(PNG_BYTES)

    res = github.deliver_github(
        engine="diagrams", image_path=str(img), cwd=str(tmp_path),
        visibility="private", run=github._run,
    )
    assert res.strategy == "local-guidance"
    assert res.output == str(img)
    guidance = res.guidance.lower()
    assert "drag" in guidance and "web editor" in guidance
    assert not _branch_exists(tmp_path, "assets")  # nothing committed


def test_nongithub_remote_guidance(tmp_path):
    _init_repo(tmp_path, remote="https://gitlab.com/x/y.git")
    img = tmp_path / "d.png"
    img.write_bytes(PNG_BYTES)

    # visibility says public, but a non-GitHub remote still can't yield a raw URL
    res = github.deliver_github(
        engine="diagrams", image_path=str(img), cwd=str(tmp_path),
        visibility="public", run=github._run,
    )
    assert res.strategy == "local-guidance"
    assert not _branch_exists(tmp_path, "assets")


def test_unknown_visibility_guidance(tmp_path):
    _init_repo(tmp_path, remote="https://github.com/o/r.git")
    img = tmp_path / "d.png"
    img.write_bytes(PNG_BYTES)

    # gh returns nothing (unavailable / unauthenticated) -> visibility unknown
    res = github.deliver_github(
        engine="diagrams", image_path=str(img), cwd=str(tmp_path),
        run=_fake_gh(""),
    )
    assert res.strategy == "local-guidance"
    assert not _branch_exists(tmp_path, "assets")


def test_dispatch_uses_only_allowlisted_commands(tmp_path):
    _init_repo(tmp_path, remote="https://github.com/o/r.git")
    img = tmp_path / "d.png"
    img.write_bytes(PNG_BYTES)
    allowed = {
        ("git", "remote"), ("git", "hash-object"), ("git", "read-tree"),
        ("git", "update-index"), ("git", "write-tree"), ("git", "commit-tree"),
        ("git", "update-ref"), ("git", "rev-parse"), ("git", "config"),
        ("gh", "repo"),
    }
    seen = []

    def recorder(args, cwd, *, check=True, extra_env=None):
        pair = (args[0], args[1])
        assert pair != ("git", "push"), "delivery must never push"
        assert pair in allowed, f"unexpected command: {args}"
        seen.append(pair)
        if args[:2] == ["gh", "repo"]:
            return "PUBLIC\n"
        return github._run(args, cwd, check=check, extra_env=extra_env)

    res = github.deliver_github(
        engine="diagrams", image_path=str(img), cwd=str(tmp_path), run=recorder
    )
    assert res.strategy == "raster-url"
    assert ("gh", "repo") in seen and ("git", "commit-tree") in seen
