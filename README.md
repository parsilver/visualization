# visualization

A Claude Code plugin that renders diagrams and charts to PNG/SVG for use in
GitHub issues and pull requests, Claude Code responses, documentation, and
local files. Rendering runs locally and offline.

## Renderers

Supported now:

- mingrammer/diagrams — cloud and infrastructure architecture with vendor icons

Planned:

- Mermaid, Matplotlib, Graphviz DOT, PlantUML

## Usage

Install from this repository as a marketplace, then render with the bundled
`viz` CLI. The skill at `skills/visualize/SKILL.md` documents the workflow;
`skills/visualize/references/engines.md` documents the engine contract.
