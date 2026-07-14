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
block, so no image is needed there; `viz github` emits that block for you (see
GitHub delivery below).

## matplotlib authoring

A matplotlib script runs as Python in a subprocess, like a diagrams script.
Read the output path and format from the environment and pass them to
`savefig`:

```python
import os
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot([1, 2, 3], [1, 4, 9])
fig.savefig(f"{os.environ['VIZ_OUT']}.{os.environ['VIZ_FORMAT']}")
```

The engine forces the headless `Agg` backend (`MPLBACKEND=Agg`) in the
subprocess, so the script needs no `matplotlib.use(...)` call and never opens a
window. PNG and SVG are both supported, and both are self-contained.

```bash
viz render --engine matplotlib --input chart.py --format png --out chart.png
```

## graphviz authoring

A Graphviz DOT graph is plain text (a `.dot` file), rendered by the `dot`
binary. Like mermaid, it is data — no Python, no environment contract; the CLI's
`--out` and `--format` control the output directly:

```bash
viz render --engine graphviz --input graph.dot --format svg --out graph.svg
```

The engine needs the Graphviz `dot` binary — the same one the diagrams engine
requires. PNG and SVG are both supported.

## GitHub delivery

`viz github` chooses the embed that renders on GitHub for the current repo:

- **Mermaid source → a native block.** The source is wrapped in a
  ` ```mermaid ` fence and returned as `output`; GitHub renders it directly, so
  nothing is uploaded.
- **A raster on a public repo → a committed URL.** The image is committed to an
  orphan `assets` branch and returned as its
  `https://raw.githubusercontent.com/<owner>/<repo>/assets/viz/<hash>.png` URL.
  The commit is built with git plumbing against a temporary index, so it leaves
  the working tree, index, and HEAD untouched, and the asset is named by its
  content hash so identical images dedupe. Delivery does not push: it prints the
  `git push origin assets` command, and the URL resolves only after that push.
- **Anything else → the local file.** A private repository, a non-GitHub
  remote, or a visibility that `gh` cannot confirm falls back to the local path
  plus guidance to drag the image into the web editor. A private repo's raw
  content is not served to GitHub's image proxy, so a committed URL would not
  render there.

Delivery never reads a token or session cookie. Repository visibility is read
with `gh repo view`, which carries its own authentication; the push, and any
credentials it needs, stay the user's own step.

## Security: trusted local source only

The diagrams and matplotlib engines run their source files as Python. Feed them
only source authored locally, in the current session. A future delivery path
that accepts such a source from an untrusted author — a GitHub pull request, for
instance — must sandbox execution first; running it directly is a
remote-code-execution surface.

The mermaid and graphviz engines are different: their source is data — Mermaid
text rendered by mermaidx, a DOT graph rendered by the `dot` binary — never
executed, so they carry no code-execution surface. The distinction matters when
a later slice renders source that did not originate locally.
