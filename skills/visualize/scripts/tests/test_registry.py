"""Contract tests for the engine registry and the CLI argument surface."""
import pytest

from vizlib.registry import Registry, UnknownEngineError
from vizlib.engines.base import RenderResult
from vizlib.cli import build_parser


class _FakeEngine:
    """A stand-in engine so the registry can be tested without a real one."""

    name = "fake"
    formats = ("png",)

    def check_deps(self) -> None:
        return None

    def render(self, source, fmt, out_path):
        return RenderResult(engine=self.name, format=fmt, path=out_path)


def test_register_and_get_engine():
    reg = Registry()
    eng = _FakeEngine()
    reg.register(eng)
    assert reg.get("fake") is eng
    assert reg.names() == ["fake"]


def test_unknown_engine_lists_registered():
    reg = Registry()
    reg.register(_FakeEngine())
    with pytest.raises(UnknownEngineError) as exc:
        reg.get("nope")
    msg = str(exc.value)
    assert "nope" in msg
    assert "fake" in msg  # the error lists what IS registered


def test_cli_render_requires_engine_input_and_out():
    parser = build_parser()
    # each required flag missing in turn -> argparse exits (SystemExit)
    for argv in (
        ["render", "--input", "s.py", "--out", "o"],            # no --engine
        ["render", "--engine", "diagrams", "--out", "o"],       # no --input
        ["render", "--engine", "diagrams", "--input", "s.py"],  # no --out
    ):
        with pytest.raises(SystemExit):
            parser.parse_args(argv)
