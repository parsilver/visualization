"""End-to-end tests for `viz render`: real render, unknown engine, missing dependency."""
import json
import os
import subprocess
import textwrap

from vizlib import cli
from vizlib.engines import diagrams_engine

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

DIAGRAM_SRC = textwrap.dedent(
    """
    import os
    from diagrams import Diagram
    from diagrams.aws.compute import EC2
    from diagrams.aws.database import RDS

    with Diagram("web", filename=os.environ["VIZ_OUT"],
                 outformat=os.environ["VIZ_FORMAT"], show=False):
        EC2("app") >> RDS("db")
    """
)


def test_render_diagrams_writes_png_prints_path(tmp_path, capsys):
    src = tmp_path / "src.py"
    src.write_text(DIAGRAM_SRC)
    out = str(tmp_path / "g.png")
    code = cli.main(["render", "--engine", "diagrams", "--input", str(src), "--out", out])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["engine"] == "diagrams"
    assert printed["format"] == "png"
    assert os.path.exists(printed["path"])
    assert open(printed["path"], "rb").read(8) == PNG_MAGIC


def test_render_infers_format_from_out_extension(tmp_path, capsys):
    # no --format given -> the format is taken from the --out extension
    src = tmp_path / "src.py"
    src.write_text(DIAGRAM_SRC)
    out = str(tmp_path / "g.svg")
    code = cli.main(["render", "--engine", "diagrams", "--input", str(src), "--out", out])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["format"] == "svg"
    assert printed["path"] == out
    assert os.path.exists(out)
    assert "<svg" in open(out, encoding="utf-8").read()


def test_unknown_engine_exit_nonzero_lists_engines(tmp_path, capsys):
    code = cli.main(
        ["render", "--engine", "nope", "--input", "x.py", "--out", str(tmp_path / "o.png")]
    )
    assert code != 0
    err = capsys.readouterr().err
    assert "nope" in err
    assert "diagrams" in err  # lists the registered engines
    assert "mermaid" in err


def test_missing_dep_exit_nonzero_no_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(diagrams_engine.shutil, "which", lambda name: None)
    src = tmp_path / "src.py"
    src.write_text(DIAGRAM_SRC)
    out = str(tmp_path / "g.png")
    code = cli.main(["render", "--engine", "diagrams", "--input", str(src), "--out", out])
    assert code != 0
    assert not os.path.exists(out)
    assert "graphviz" in capsys.readouterr().err.lower()


MERMAID_SRC = "flowchart TD\n  A[Start] --> B{OK?}\n  B -->|yes| C[Done]\n"


def test_render_mermaid_writes_svg(tmp_path, capsys):
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    out = str(tmp_path / "m.svg")
    code = cli.main(["render", "--engine", "mermaid", "--input", str(src), "--out", out])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["engine"] == "mermaid"
    assert printed["format"] == "svg"
    assert "<svg" in open(out, encoding="utf-8").read()


def test_render_mermaid_writes_png(tmp_path, capsys):
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    out = str(tmp_path / "m.png")
    code = cli.main(["render", "--engine", "mermaid", "--input", str(src), "--out", out])
    assert code == 0
    assert open(out, "rb").read(8) == PNG_MAGIC


def test_render_missing_mermaidx_exits_nonzero_with_install(tmp_path, monkeypatch, capsys):
    from vizlib.engines import mermaid_engine

    monkeypatch.setattr(mermaid_engine.importlib.util, "find_spec", lambda name: None)
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    out = str(tmp_path / "m.svg")
    code = cli.main(["render", "--engine", "mermaid", "--input", str(src), "--out", out])
    assert code != 0
    err = capsys.readouterr().err.lower()
    assert "mermaidx" in err
    assert not os.path.exists(out)


# --- viz github -------------------------------------------------------------

def _github_repo(path):
    def g(*args):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
    g("init", "-b", "main")
    g("config", "user.email", "dev@example.com")
    g("config", "user.name", "Dev")
    g("remote", "add", "origin", "https://github.com/o/r.git")


def test_github_mermaid_prints_block_json(tmp_path, capsys):
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    code = cli.main(["github", "--engine", "mermaid", "--input", str(src)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["strategy"] == "mermaid-block"
    assert out["output"].startswith("```mermaid")
    assert "flowchart TD" in out["output"]
    assert out["guidance"] is None


def test_github_raster_public_prints_url(tmp_path, monkeypatch, capsys):
    from vizlib.delivery import github as gh

    _github_repo(tmp_path)
    monkeypatch.setattr(gh, "repo_visibility", lambda cwd, run=gh._run: "public")
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    out = str(tmp_path / "d.png")
    code = cli.main(
        ["github", "--engine", "mermaid", "--input", str(src), "--mode", "raster", "--out", out]
    )
    assert code == 0
    res = json.loads(capsys.readouterr().out)
    assert res["strategy"] == "raster-url"
    assert res["output"].startswith("https://raw.githubusercontent.com/o/r/assets/viz/")
    assert "git push origin assets" in res["guidance"]


def test_github_raster_private_prints_guidance(tmp_path, monkeypatch, capsys):
    from vizlib.delivery import github as gh

    _github_repo(tmp_path)
    monkeypatch.setattr(gh, "repo_visibility", lambda cwd, run=gh._run: "private")
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    out = str(tmp_path / "d.png")
    code = cli.main(
        ["github", "--engine", "mermaid", "--input", str(src), "--mode", "raster", "--out", out]
    )
    assert code == 0
    res = json.loads(capsys.readouterr().out)
    assert res["strategy"] == "local-guidance"
    assert "drag" in res["guidance"].lower()


def test_github_raster_requires_out(tmp_path, capsys):
    src = tmp_path / "s.py"
    src.write_text("x = 1\n")
    code = cli.main(["github", "--engine", "diagrams", "--input", str(src)])
    assert code != 0
    assert "out" in capsys.readouterr().err.lower()


def test_github_block_missing_input_exits_clean(tmp_path, capsys):
    code = cli.main(["github", "--engine", "mermaid", "--input", str(tmp_path / "nope.mmd")])
    assert code != 0
    assert "not found" in capsys.readouterr().err.lower()
