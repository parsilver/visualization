"""Tests for the plantuml engine: real renders plus dependency and failure paths."""
import os

import pytest

from vizlib.engines.base import EngineError, MissingDependencyError, RenderResult
from vizlib.engines import plantuml_engine
from vizlib.engines.plantuml_engine import PlantumlEngine

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

PUML_SRC = "@startuml\nAlice -> Bob: hello\n@enduml\n"
BAD_SRC = "not plantuml at all\n"


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def test_renders_png_magic_bytes(tmp_path):
    src = _write(tmp_path, "d.puml", PUML_SRC)
    out = str(tmp_path / "out.png")
    result = PlantumlEngine().render(src, "png", out)
    assert isinstance(result, RenderResult)
    assert result.engine == "plantuml"
    assert result.path == out
    data = open(out, "rb").read()
    assert data[:8] == PNG_MAGIC
    assert len(data) > 8


def test_renders_svg(tmp_path):
    src = _write(tmp_path, "d.puml", PUML_SRC)
    out = str(tmp_path / "out.svg")
    PlantumlEngine().render(src, "svg", out)
    assert os.path.exists(out)
    assert "<svg" in open(out, encoding="utf-8").read()


def test_missing_plantuml_returns_error_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(plantuml_engine.shutil, "which", lambda name: None)
    src = _write(tmp_path, "d.puml", PUML_SRC)
    out = str(tmp_path / "out.png")
    with pytest.raises(MissingDependencyError):
        PlantumlEngine().render(src, "png", out)
    assert not os.path.exists(out)


def test_missing_plantuml_error_names_install(monkeypatch):
    monkeypatch.setattr(plantuml_engine.shutil, "which", lambda name: None)
    with pytest.raises(MissingDependencyError) as exc:
        PlantumlEngine().check_deps()
    assert "plantuml" in str(exc.value).lower()


def test_missing_source_file_no_file(tmp_path):
    out = str(tmp_path / "out.png")
    with pytest.raises(EngineError) as exc:
        PlantumlEngine().render(str(tmp_path / "nope.puml"), "png", out)
    # the engine's own wording, so a missing-plantuml error cannot satisfy this
    assert "source file not found" in str(exc.value).lower()
    assert not os.path.exists(out)


def test_directory_input_errors_no_file(tmp_path):
    # a directory at the input path is not a readable source; it must surface a
    # clean error, not an uncaught IsADirectoryError
    out = str(tmp_path / "out.png")
    with pytest.raises(EngineError) as exc:
        PlantumlEngine().render(str(tmp_path), "png", out)
    assert "source file not found" in str(exc.value).lower()
    assert not os.path.exists(out)


def test_bad_source_errors_no_file(tmp_path):
    src = _write(tmp_path, "bad.puml", BAD_SRC)
    out = str(tmp_path / "out.png")
    with pytest.raises(EngineError) as exc:
        PlantumlEngine().render(src, "png", out)
    # plantuml exits non-zero on a syntax error; the engine surfaces it and
    # never writes plantuml's ~26KB error image as a false success
    assert "plantuml" in str(exc.value).lower()
    assert not os.path.exists(out)


def test_bad_source_removes_stale_output(tmp_path):
    # a pre-existing output must not survive a failed render
    src = _write(tmp_path, "bad.puml", BAD_SRC)
    out = str(tmp_path / "out.png")
    with open(out, "wb") as f:
        f.write(b"stale-previous-render")
    with pytest.raises(EngineError):
        PlantumlEngine().render(src, "png", out)
    assert not os.path.exists(out)  # the stale file was cleared, not left behind


def test_unsupported_format_no_file(tmp_path):
    src = _write(tmp_path, "d.puml", PUML_SRC)
    out = str(tmp_path / "out.pdf")
    with pytest.raises(EngineError) as exc:
        PlantumlEngine().render(src, "pdf", out)
    msg = str(exc.value)
    assert "pdf" in msg
    assert "png" in msg and "svg" in msg  # lists the supported formats
    assert not os.path.exists(out)
