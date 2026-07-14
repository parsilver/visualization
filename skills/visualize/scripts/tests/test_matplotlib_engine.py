"""Tests for the matplotlib engine: real renders plus dependency and failure paths."""
import os
import textwrap

import pytest

from vizlib.engines.base import EngineError, MissingDependencyError, RenderResult
from vizlib.engines import matplotlib_engine
from vizlib.engines.matplotlib_engine import MatplotlibEngine

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

CHART_SRC = textwrap.dedent(
    """
    import os
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 4, 9])
    fig.savefig(f"{os.environ['VIZ_OUT']}.{os.environ['VIZ_FORMAT']}")
    """
)


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def test_renders_png_magic_bytes(tmp_path):
    src = _write(tmp_path, "chart.py", CHART_SRC)
    out = str(tmp_path / "out.png")
    result = MatplotlibEngine().render(src, "png", out)
    assert isinstance(result, RenderResult)
    assert result.engine == "matplotlib"
    assert result.path == out
    data = open(out, "rb").read()
    assert data[:8] == PNG_MAGIC
    assert len(data) > 8


def test_renders_svg(tmp_path):
    src = _write(tmp_path, "chart.py", CHART_SRC)
    out = str(tmp_path / "out.svg")
    MatplotlibEngine().render(src, "svg", out)
    assert os.path.exists(out)
    assert "<svg" in open(out, encoding="utf-8").read()


def test_missing_matplotlib_returns_error_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(matplotlib_engine.importlib.util, "find_spec", lambda name: None)
    src = _write(tmp_path, "chart.py", CHART_SRC)
    out = str(tmp_path / "out.png")
    with pytest.raises(MissingDependencyError):
        MatplotlibEngine().render(src, "png", out)
    assert not os.path.exists(out)


def test_missing_matplotlib_error_names_install(monkeypatch):
    monkeypatch.setattr(matplotlib_engine.importlib.util, "find_spec", lambda name: None)
    with pytest.raises(MissingDependencyError) as exc:
        MatplotlibEngine().check_deps()
    msg = str(exc.value).lower()
    assert "matplotlib" in msg
    assert "pip install" in msg


def test_bad_source_surfaces_stderr_no_file(tmp_path):
    src = _write(tmp_path, "bad.py", "raise RuntimeError('boom-xyz')\n")
    out = str(tmp_path / "out.png")
    with pytest.raises(EngineError) as exc:
        MatplotlibEngine().render(src, "png", out)
    assert "boom-xyz" in str(exc.value)
    assert not os.path.exists(out)


def test_source_without_savefig_errors_no_file(tmp_path):
    # A source that runs cleanly but writes no output file.
    src = _write(tmp_path, "nofile.py", "x = 1 + 1\n")
    out = str(tmp_path / "out.png")
    with pytest.raises(EngineError) as exc:
        MatplotlibEngine().render(src, "png", out)
    assert "savefig" in str(exc.value).lower()
    assert not os.path.exists(out)


def test_unsupported_format_no_file(tmp_path):
    src = _write(tmp_path, "chart.py", CHART_SRC)
    out = str(tmp_path / "out.pdf")
    with pytest.raises(EngineError) as exc:
        MatplotlibEngine().render(src, "pdf", out)
    msg = str(exc.value)
    assert "pdf" in msg
    assert "png" in msg and "svg" in msg  # lists the supported formats
    assert not os.path.exists(out)


def test_forces_agg_backend(tmp_path):
    # The engine forces MPLBACKEND=Agg in the subprocess so no display is
    # required; the source asserts it sees that environment, then renders.
    # This goes RED if the engine stops setting MPLBACKEND, independent of
    # whatever backend the host machine would default to.
    src = _write(
        tmp_path,
        "agg.py",
        textwrap.dedent(
            """
            import os
            assert os.environ["MPLBACKEND"] == "Agg", os.environ.get("MPLBACKEND")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots()
            ax.plot([0, 1], [0, 1])
            fig.savefig(f"{os.environ['VIZ_OUT']}.{os.environ['VIZ_FORMAT']}")
            """
        ),
    )
    out = str(tmp_path / "agg.png")
    result = MatplotlibEngine().render(src, "png", out)
    assert result.path == out
    assert open(out, "rb").read(8) == PNG_MAGIC
