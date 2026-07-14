"""Tests for the diagrams engine: real renders plus dependency and failure paths."""
import os
import textwrap

import pytest

from vizlib.engines.base import EngineError, MissingDependencyError, RenderResult
from vizlib.engines import diagrams_engine
from vizlib.engines.diagrams_engine import DiagramsEngine

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


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def test_renders_png_magic_bytes(tmp_path):
    src = _write(tmp_path, "src.py", DIAGRAM_SRC)
    out = str(tmp_path / "out.png")
    result = DiagramsEngine().render(src, "png", out)
    assert isinstance(result, RenderResult)
    assert result.path == out
    data = open(out, "rb").read()
    assert data[:8] == PNG_MAGIC
    assert len(data) > 8


def test_renders_svg(tmp_path):
    src = _write(tmp_path, "src.py", DIAGRAM_SRC)
    out = str(tmp_path / "out.svg")
    DiagramsEngine().render(src, "svg", out)
    assert os.path.exists(out)
    assert "<svg" in open(out, encoding="utf-8").read()


def test_missing_graphviz_returns_error_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams_engine.shutil, "which", lambda name: None)
    src = _write(tmp_path, "src.py", DIAGRAM_SRC)
    out = str(tmp_path / "out.png")
    with pytest.raises(MissingDependencyError):
        DiagramsEngine().render(src, "png", out)
    assert not os.path.exists(out)


def test_missing_graphviz_error_names_install(monkeypatch):
    monkeypatch.setattr(diagrams_engine.shutil, "which", lambda name: None)
    with pytest.raises(MissingDependencyError) as exc:
        DiagramsEngine().check_deps()
    assert "graphviz" in str(exc.value).lower()


def test_bad_source_surfaces_stderr_no_file(tmp_path):
    src = _write(tmp_path, "bad.py", "raise RuntimeError('boom-xyz')\n")
    out = str(tmp_path / "out.png")
    with pytest.raises(EngineError) as exc:
        DiagramsEngine().render(src, "png", out)
    assert "boom-xyz" in str(exc.value)
    assert not os.path.exists(out)
