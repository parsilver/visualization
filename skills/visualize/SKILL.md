---
name: visualize
description: >-
  Render a diagram, architecture, chart, or workflow as a PNG or SVG image
  instead of describing it in text. Use when the user asks to draw, diagram,
  visualize, or "show as an image" a system architecture, infrastructure,
  cloud design, flowchart, sequence diagram, a data chart (line, bar,
  scatter), a Graphviz DOT graph, or a PlantUML diagram, or mentions
  mingrammer/diagrams, Mermaid, matplotlib, Graphviz, or PlantUML — and also
  when composing a GitHub issue, pull request, comment, or documentation that
  a diagram or chart would make clearer, even without an explicit request to
  draw. Produces an image file, or a Mermaid block for GitHub, whose path or
  text can be placed in a GitHub issue, a response, documentation, or saved
  locally. Not for building interactive or web-embedded chart components.
---

# visualize

Turn a description of a system into an image. This skill renders an engine's
own native source to a PNG or SVG file with the bundled `viz` CLI, which runs
locally and offline.

## Which engine

- **diagrams** (mingrammer/diagrams) — a cloud or infrastructure architecture
  drawn with real vendor icons (AWS, GCP, Azure, Kubernetes, on-prem).
- **mermaid** — a flowchart, sequence, state, ER, or class diagram from Mermaid
  text, rendered with mermaidx (no headless browser). On GitHub, deliver it with
  `viz github` (see [Deliver to GitHub](#deliver-to-github)), which emits the
  native ` ```mermaid ` block GitHub renders directly; render an image file when
  you need one for docs, a local file, or a response.
- **matplotlib** — a data chart (line, bar, scatter, histogram, and the rest of
  matplotlib) from a matplotlib script. Runs the script in a subprocess with a
  headless backend and writes a PNG or SVG.
- **graphviz** — a graph written in the Graphviz DOT language, rendered by the
  `dot` binary to a PNG or SVG. DOT source is data, not executed.
- **plantuml** — a PlantUML diagram (sequence, class, activity, state, and more)
  from PlantUML text, rendered by the `plantuml` command. Source is data, not
  executed.

## Render a diagrams image

1. Write the diagram as a diagrams script — Python using the `diagrams`
   library. The script reads its output path and format from the environment
   so the CLI controls where the image lands:

   ```python
   import os
   from diagrams import Diagram
   from diagrams.aws.compute import EC2
   from diagrams.aws.database import RDS

   with Diagram("web", filename=os.environ["VIZ_OUT"],
                outformat=os.environ["VIZ_FORMAT"], show=False):
       EC2("app") >> RDS("db")
   ```

2. Render it:

   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
     viz render --engine diagrams --input <script.py> --format png --out <path.png>
   ```

   The command prints `{"engine", "format", "path"}` as JSON and writes the
   image to `path`. Use that path to embed or open the image. The format comes
   from `--format`; when it is omitted, it is taken from the `--out` extension
   (else png).

3. Prefer PNG. A diagrams SVG references its icons by local file path, so it
   does not display correctly once moved to another machine.

## Render a Mermaid image

Write the diagram as Mermaid text (a `.mmd` file), then:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
  viz render --engine mermaid --input <diagram.mmd> --format svg --out <path.svg>
```

Mermaid source is plain text — no Python, no environment contract. SVG and PNG
are both supported. For a GitHub issue or pull request, use `viz github` (below)
to emit the fenced block instead of rendering an image.

## Render a matplotlib chart

Write the chart as a matplotlib script — Python using `matplotlib`. Like the
diagrams engine, it reads its output path and format from the environment:

```python
import os
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.bar(["a", "b", "c"], [3, 1, 2])
fig.savefig(f"{os.environ['VIZ_OUT']}.{os.environ['VIZ_FORMAT']}")
```

Render it:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
  viz render --engine matplotlib --input <chart.py> --format png --out <path.png>
```

The engine forces a headless backend, so the script never opens a window and
needs no `matplotlib.use(...)` call. PNG and SVG are both supported and
self-contained.

## Render a Graphviz DOT graph

Write the graph as DOT text (a `.dot` file), then render it with the `dot`
binary — no Python, no environment contract:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
  viz render --engine graphviz --input <graph.dot> --format svg --out <path.svg>
```

DOT source is data, rendered by `dot` and never executed. SVG and PNG are both
supported.

## Render a PlantUML diagram

Write the diagram as PlantUML text (a `.puml` file), then:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
  viz render --engine plantuml --input <diagram.puml> --format svg --out <path.svg>
```

The engine pipes the source to `plantuml`, so a syntax error is reported as an
error rather than written as PlantUML's error image. SVG and PNG are both
supported.

## Deliver to GitHub

`viz github` puts a diagram where a GitHub reader sees it, picking the embed
that renders for the repository:

- **Mermaid source** becomes a native ` ```mermaid ` block — GitHub renders it
  directly, so nothing is uploaded:

  ```bash
  uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
    viz github --engine mermaid --input <diagram.mmd>
  ```

  It prints `{"strategy": "mermaid-block", "output": <block>, "guidance": null}`;
  paste `output` into the issue, pull request, or comment.

- **Any other image on a public repository** is committed to an orphan `assets`
  branch and delivered as its `raw.githubusercontent.com` URL:

  ```bash
  uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
    viz github --engine diagrams --input <script.py> --out <path.png>
  ```

  The commit is local. Delivery prints a `git push origin assets` command in
  `guidance`, and the URL in `output` resolves once you run that push. It never
  pushes for you and never handles a token or session cookie.

- **A private repo, a non-GitHub remote, or an unconfirmed visibility** returns
  the local image path plus guidance to drag the file into the GitHub web
  editor — a private repository's raw content does not render through GitHub's
  image proxy, so a committed URL would not work there.

See [references/engines.md](references/engines.md) for the delivery mechanics.

## Deliver to a Claude response

To show a diagram in a Claude Code response, the surface sets the form.

**In a Claude Artifact**, render to SVG and embed the markup inline:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
  viz render --engine <name> --input <source> --format svg --out <path.svg>
```

Read the file and place its `<svg>…</svg>` directly in the artifact. The artifact
sandbox blocks external URLs, so the SVG must be self-contained — the mermaid,
matplotlib, graphviz, and plantuml engines produce self-contained SVG. The
diagrams engine's SVG references its icons by local file path, so it is not
self-contained; render a PNG for that engine and deliver the file instead.

**In the terminal**, an image cannot display inline. Render to a file and give
the reader the path:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
  viz render --engine <name> --input <source> --out <path.png>
```

## Deliver to documentation

To place a diagram in a Markdown document, render the image into the docs tree
and reference it with a relative link. The CLI creates the output directory if
it does not exist:

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}/skills/visualize/scripts" \
  viz render --engine <name> --input <source> --out docs/assets/<name>.png
```

Then reference it from the document with a path relative to the document:

```markdown
![<alt text>](assets/<name>.png)
```

Prefer PNG for portability: a diagrams SVG references its icons by local path and
does not travel, and some Markdown renderers strip inline SVG. The mermaid,
graphviz, matplotlib, and plantuml engines produce self-contained SVG if you want
vector output for a document that stays in the repository.

## A missing dependency

Each engine checks its own runtime dependencies. The diagrams and graphviz
engines need the Graphviz `dot` binary (the diagrams engine also needs the
`diagrams` package); the matplotlib engine needs the `matplotlib` package; the
plantuml engine needs the `plantuml` command. If a dependency is absent the
command exits non-zero and prints how to install it — it never reports a false
success.

## The engine contract

For the `Engine` protocol, the environment-variable output contract, the
trusted-source boundary, and how to add an engine, see
[references/engines.md](references/engines.md).
