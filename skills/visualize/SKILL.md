---
name: visualize
description: >-
  Render a diagram, architecture, chart, or workflow as a PNG or SVG image
  instead of describing it in text. Use when the user asks to draw, diagram,
  visualize, or "show as an image" a system architecture, infrastructure,
  cloud design, flowchart, or sequence diagram, or mentions mingrammer/diagrams
  or Mermaid. Produces an image file whose
  path can be placed in a GitHub issue, a response, documentation, or saved
  locally.
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

## A missing dependency

The diagrams engine needs the Graphviz `dot` binary and the `diagrams`
package. If either is absent the command exits non-zero and prints how to
install them — it never reports a false success.

## The engine contract

For the `Engine` protocol, the environment-variable output contract, the
trusted-source boundary, and how to add an engine, see
[references/engines.md](references/engines.md).
