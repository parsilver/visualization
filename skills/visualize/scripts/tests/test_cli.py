"""End-to-end tests for `viz render`: real render, unknown engine, missing dependency."""
import json
import os
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


def test_unknown_engine_exit_nonzero_lists_engines(tmp_path, capsys):
    code = cli.main(
        ["render", "--engine", "nope", "--input", "x.py", "--out", str(tmp_path / "o.png")]
    )
    assert code != 0
    err = capsys.readouterr().err
    assert "nope" in err
    assert "diagrams" in err  # lists the registered engine


def test_missing_dep_exit_nonzero_no_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(diagrams_engine.shutil, "which", lambda name: None)
    src = tmp_path / "src.py"
    src.write_text(DIAGRAM_SRC)
    out = str(tmp_path / "g.png")
    code = cli.main(["render", "--engine", "diagrams", "--input", str(src), "--out", out])
    assert code != 0
    assert not os.path.exists(out)
    assert "graphviz" in capsys.readouterr().err.lower()
