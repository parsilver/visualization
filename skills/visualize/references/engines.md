# Engines

How the renderer is extended, and how to author source for each engine.

## The `Engine` protocol

An engine is any object with:

- `name: str` — the registry key, e.g. `"diagrams"`.
- `formats: tuple[str, ...]` — the output formats it can write.
- `check_deps() -> None` — raise `MissingDependencyError`, naming the missing
  dependency and how to install it, when a runtime requirement is absent;
  return `None` when ready.
- `render(source: str, fmt: str, out_path: str) -> RenderResult` — render the
  source file to `out_path`, returning `RenderResult(engine, format, path)`.
  Raise `EngineError` on failure and leave no partial output file behind.

The protocol lives in `scripts/vizlib/engines/base.py`.

## Adding an engine

1. Add `scripts/vizlib/engines/<name>_engine.py` with a class that implements
   the protocol above.
2. Register it in `scripts/vizlib/cli.py`, inside `_default_registry`.
3. Add contract tests under `scripts/tests/`: a real render asserting the
   output's magic bytes, a missing-dependency path, and a bad-source path.

## The output contract

The CLI owns the output path. It passes two environment variables to the
render step:

- `VIZ_OUT` — the output path without its extension.
- `VIZ_FORMAT` — the requested format.

An engine writes its image to `<VIZ_OUT>.<VIZ_FORMAT>`, and the CLI confirms
that file exists before reporting success.

## diagrams authoring

A diagrams script runs as Python in a subprocess. Read the output path and
format from the environment:

```python
import os
from diagrams import Diagram
from diagrams.aws.compute import EC2

with Diagram("name", filename=os.environ["VIZ_OUT"],
             outformat=os.environ["VIZ_FORMAT"], show=False):
    EC2("web")
```

`filename` takes no extension — diagrams appends the format. Pass `show=False`
so no viewer opens.

## mermaid authoring

The mermaid engine takes plain Mermaid text (a `.mmd` file) and renders it with
mermaidx, in-process. There is no environment-variable contract — the CLI's
`--out` and `--format` control the output directly:

```bash
viz render --engine mermaid --input diagram.mmd --format svg --out diagram.svg
```

On GitHub, a Mermaid diagram renders natively from a ` ```mermaid ` fenced
block, so no image is needed there; a later change adds a GitHub delivery path
that emits the block instead of a raster.

## Security: trusted local source only

The diagrams engine runs its source file as Python. Feed it only source
authored locally, in the current session. A future delivery path that accepts
a diagrams source from an untrusted author — a GitHub pull request, for
instance — must sandbox execution first; running such source directly is a
remote-code-execution surface.

The mermaid engine is different: its source is data, rendered by mermaidx and
never executed, so it carries no code-execution surface. The distinction
matters when a later slice renders source that did not originate locally.
