---
name: visualize
description: >-
  Render a diagram, architecture, chart, or workflow as a PNG or SVG image
  instead of describing it in text. Use when the user asks to draw, diagram,
  visualize, or "show as an image" a system architecture, infrastructure, or
  cloud design, or mentions mingrammer/diagrams. Produces an image file whose
  path can be placed in a GitHub issue, a response, documentation, or saved
  locally.
---

# visualize

Turn a description of a system into an image. This skill renders an engine's
own native source to a PNG or SVG file with the bundled `viz` CLI, which runs
locally and offline.

## Which engine

- **diagrams** (mingrammer/diagrams) — a cloud or infrastructure architecture
  drawn with real vendor icons (AWS, GCP, Azure, Kubernetes, on-prem). The
  only engine in this release; more follow.

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

## A missing dependency

The diagrams engine needs the Graphviz `dot` binary and the `diagrams`
package. If either is absent the command exits non-zero and prints how to
install them — it never reports a false success.

## The engine contract

For the `Engine` protocol, the environment-variable output contract, the
trusted-source boundary, and how to add an engine, see
[references/engines.md](references/engines.md).
