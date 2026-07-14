"""Tests for the graphviz engine: real renders plus dependency and failure paths."""
import os

import pytest

from vizlib.engines.base import EngineError, MissingDependencyError, RenderResult
from vizlib.engines import graphviz_engine
from vizlib.engines.graphviz_engine import GraphvizEngine

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

DOT_SRC = "digraph { a -> b; b -> c; }\n"


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def test_renders_png_magic_bytes(tmp_path):
    src = _write(tmp_path, "g.dot", DOT_SRC)
    out = str(tmp_path / "out.png")
    result = GraphvizEngine().render(src, "png", out)
    assert isinstance(result, RenderResult)
    assert result.engine == "graphviz"
    assert result.path == out
    data = open(out, "rb").read()
    assert data[:8] == PNG_MAGIC
    assert len(data) > 8


def test_renders_svg(tmp_path):
    src = _write(tmp_path, "g.dot", DOT_SRC)
    out = str(tmp_path / "out.svg")
    GraphvizEngine().render(src, "svg", out)
    assert os.path.exists(out)
    assert "<svg" in open(out, encoding="utf-8").read()


def test_missing_dot_returns_error_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(graphviz_engine.shutil, "which", lambda name: None)
    src = _write(tmp_path, "g.dot", DOT_SRC)
    out = str(tmp_path / "out.png")
    with pytest.raises(MissingDependencyError):
        GraphvizEngine().render(src, "png", out)
    assert not os.path.exists(out)


def test_missing_dot_error_names_install(monkeypatch):
    monkeypatch.setattr(graphviz_engine.shutil, "which", lambda name: None)
    with pytest.raises(MissingDependencyError) as exc:
        GraphvizEngine().check_deps()
    assert "graphviz" in str(exc.value).lower()


def test_missing_source_file_no_file(tmp_path):
    out = str(tmp_path / "out.png")
    with pytest.raises(EngineError) as exc:
        GraphvizEngine().render(str(tmp_path / "nope.dot"), "png", out)
    # the engine's own wording, so a missing-dot error cannot satisfy this
    assert "source file not found" in str(exc.value).lower()
    assert not os.path.exists(out)


def test_bad_source_surfaces_stderr_no_file(tmp_path):
    src = _write(tmp_path, "bad.dot", "not a graph {{{\n")
    out = str(tmp_path / "out.png")
    with pytest.raises(EngineError) as exc:
        GraphvizEngine().render(src, "png", out)
    msg = str(exc.value)
    # the contract: a non-zero exit surfaces dot's own (non-empty) error text,
    # asserted without coupling to a specific dot version's wording
    assert "exit" in msg.lower()
    assert msg.split(":\n", 1)[-1].strip()
    assert not os.path.exists(out)


def test_unsupported_format_no_file(tmp_path):
    src = _write(tmp_path, "g.dot", DOT_SRC)
    out = str(tmp_path / "out.pdf")
    with pytest.raises(EngineError) as exc:
        GraphvizEngine().render(src, "pdf", out)
    msg = str(exc.value)
    assert "pdf" in msg
    assert "png" in msg and "svg" in msg  # lists the supported formats
    assert not os.path.exists(out)
