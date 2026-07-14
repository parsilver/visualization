"""Tests for the mermaid engine: real renders plus dependency and failure paths."""
import os

import pytest

from vizlib.engines.base import EngineError, MissingDependencyError, RenderResult
from vizlib.engines import mermaid_engine
from vizlib.engines.mermaid_engine import MermaidEngine

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MERMAID_SRC = "flowchart TD\n  A[Start] --> B{OK?}\n  B -->|yes| C[Done]\n"


def _write(tmp_path, body=MERMAID_SRC, name="d.mmd"):
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def test_renders_svg(tmp_path):
    out = str(tmp_path / "out.svg")
    result = MermaidEngine().render(_write(tmp_path), "svg", out)
    assert isinstance(result, RenderResult)
    assert result.path == out
    assert "<svg" in open(out, encoding="utf-8").read()


def test_renders_png(tmp_path):
    out = str(tmp_path / "out.png")
    MermaidEngine().render(_write(tmp_path), "png", out)
    assert open(out, "rb").read(8) == PNG_MAGIC


def test_bad_source_raises_no_file(tmp_path):
    src = _write(tmp_path, body="this is not valid mermaid @@@\n")
    out = str(tmp_path / "out.svg")
    with pytest.raises(EngineError):
        MermaidEngine().render(src, "svg", out)
    assert not os.path.exists(out)


def test_missing_mermaidx_names_install(monkeypatch):
    monkeypatch.setattr(mermaid_engine.importlib.util, "find_spec", lambda name: None)
    with pytest.raises(MissingDependencyError) as exc:
        MermaidEngine().check_deps()
    assert "mermaidx" in str(exc.value)


def test_render_missing_input_raises_engine_error_no_traceback(tmp_path):
    # a non-existent input must surface as EngineError (clean), not a raw FileNotFoundError
    out = str(tmp_path / "out.svg")
    with pytest.raises(EngineError):
        MermaidEngine().render(str(tmp_path / "nope.mmd"), "svg", out)
    assert not os.path.exists(out)
