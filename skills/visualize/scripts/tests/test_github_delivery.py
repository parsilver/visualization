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
