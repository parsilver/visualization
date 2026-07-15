# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Raster GitHub delivery bases the `assets` commit on the `refs/remotes/origin/assets` remote-tracking ref when no local `assets` branch exists, so delivering from a fresh clone appends to the published history instead of starting a divergent root that rejects the push.

## [0.1.0] - 2026-07-15

The first release: a local, offline renderer that turns each engine's own native
source into a PNG or SVG, and delivers it to GitHub or a local file, with
guidance for placing it in a Claude response or documentation.

### Added

- A `viz` CLI and a pluggable engine registry — adding an engine is a new module plus one registry entry.
- Five rendering engines:
  - **diagrams** (mingrammer/diagrams) — cloud and infrastructure architecture with vendor icons.
  - **mermaid** — flowchart, sequence, state, ER, and class diagrams, via mermaidx (no headless browser).
  - **matplotlib** — line, bar, scatter, and other charts from a matplotlib script.
  - **graphviz** — graphs from the DOT language, via the `dot` binary.
  - **plantuml** — sequence, class, activity, and other UML diagrams, via the `plantuml` command.
- GitHub delivery (`viz github`): a native Mermaid block where possible, or a raster committed to an `assets` branch and served as a `raw.githubusercontent.com` URL for public repositories. It never handles account credentials.
- Guidance for delivering a rendered diagram to a Claude response (a self-contained SVG in an Artifact) and to documentation (a rendered file plus a relative Markdown reference).

[Unreleased]: https://github.com/parsilver/visualization/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/parsilver/visualization/releases/tag/v0.1.0
