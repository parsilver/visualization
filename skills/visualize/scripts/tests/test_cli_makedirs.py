"""`viz render` / `viz github` tests for the --out parent-directory creation.

Before the fix, `viz render --out <missing-dir>/x.png` reached the engine with a
parent directory that did not exist. The engines write straight to --out and do
not create intermediate directories, so:
  * plantuml_engine raised an *uncaught* FileNotFoundError (full traceback; the
    cli's except only catches EngineError), and
  * mermaid_engine's broad `except Exception` mislabelled the same errno-2 as
    "mermaid source failed to render: [Errno 2] ..." — blaming valid source.

The fix adds `cli._ensure_out_dir(out)`, called in both run_render and
run_github raster mode before the engine renders. These tests pin the fixed
behaviour.
"""
import json
import os
import shutil

import pytest

from vizlib import cli

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MERMAID_SRC = "flowchart TD\n  A[Start] --> B{OK?}\n  B -->|yes| C[Done]\n"
PLANTUML_SRC = "@startuml\nAlice -> Bob: hello\n@enduml\n"


# a render into a nonexistent, nested output dir now succeeds -----------------
# Uses the mermaid engine, which needs no system binary (pure-Python mermaidx).

def test_render_creates_missing_nested_out_dir(tmp_path, capsys):
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    out = str(tmp_path / "build" / "img" / "m.png")
    assert not os.path.exists(os.path.dirname(out))
    code = cli.main(["render", "--engine", "mermaid", "--input", str(src), "--out", out])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["engine"] == "mermaid"
    assert printed["path"] == out
    assert os.path.exists(out)
    assert open(out, "rb").read(8) == PNG_MAGIC


# an --out with no directory component still works ---------------------------
# dirname("m.svg") == "" must be a no-op, not an error.

def test_render_bare_filename_out_still_works(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    out = "m.svg"  # no directory component
    code = cli.main(["render", "--engine", "mermaid", "--input", str(src), "--out", out])
    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["format"] == "svg"
    assert os.path.exists(tmp_path / "m.svg")
    assert "<svg" in open(tmp_path / "m.svg", encoding="utf-8").read()


# an already-existing parent dir must not error ------------------------------

def test_render_existing_out_dir_is_noop(tmp_path, capsys):
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    existing = tmp_path / "out"
    existing.mkdir()
    out = str(existing / "m.svg")
    code = cli.main(["render", "--engine", "mermaid", "--input", str(src), "--out", out])
    assert code == 0
    assert os.path.exists(out)


# an un-creatable parent dir surfaces a clean error + exit 1 (no traceback) ---
# A path component that is a *file* makes os.makedirs raise OSError; the fix
# must catch it and return exit 1 with a message, not raise.

def test_render_uncreatable_out_dir_clean_error(tmp_path, capsys):
    src = tmp_path / "d.mmd"
    src.write_text(MERMAID_SRC)
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory")
    out = str(blocker / "sub" / "m.svg")  # blocker is a file -> makedirs fails
    code = cli.main(["render", "--engine", "mermaid", "--input", str(src), "--out", out])
    assert code == 1
    err = capsys.readouterr().err.lower()
    assert "output directory" in err
    assert not os.path.exists(out)


# the helper itself: unit-level edge cases -----------------------------------

def test_ensure_out_dir_no_dir_component_is_noop():
    assert cli._ensure_out_dir("m.png") is None


def test_ensure_out_dir_creates_missing(tmp_path):
    target = tmp_path / "a" / "b" / "c.png"
    assert cli._ensure_out_dir(str(target)) is None
    assert (tmp_path / "a" / "b").is_dir()


def test_ensure_out_dir_existing_is_noop(tmp_path):
    (tmp_path / "a").mkdir()
    assert cli._ensure_out_dir(str(tmp_path / "a" / "c.png")) is None


def test_ensure_out_dir_returns_message_on_error(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("file")
    msg = cli._ensure_out_dir(str(blocker / "sub" / "c.png"))
    assert msg is not None
    assert "output directory" in msg.lower()


# the previously-crashing plantuml render path no longer emits an uncaught
# traceback. plantuml needs Java + the plantuml binary; skip when absent so the
# suite stays green on minimal hosts.

@pytest.mark.skipif(shutil.which("plantuml") is None, reason="plantuml not installed")
def test_render_plantuml_into_missing_dir_no_traceback(tmp_path, capsys):
    src = tmp_path / "d.puml"
    src.write_text(PLANTUML_SRC)
    out = str(tmp_path / "nested" / "here" / "d.png")
    assert not os.path.exists(os.path.dirname(out))
    code = cli.main(["render", "--engine", "plantuml", "--input", str(src), "--out", out])
    assert code == 0
    assert os.path.exists(out)
    assert open(out, "rb").read(8) == PNG_MAGIC
