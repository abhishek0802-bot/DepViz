# DepViz

## An Interactive Graph-Based Tool for Visualizing Software Dependency Structures

DepViz statically analyzes a Python repository's internal import structure and renders it as an interactive, graph-theoretically grounded visualization — without executing the analyzed code.

---

## Overview

Understanding how files in a codebase depend on one another is difficult to do by reading source code alone, especially as a project grows. DepViz treats a Python repository as a directed graph — files are vertices, and import statements are directed edges — and makes that structure explorable.

Given the path to a Python repository, DepViz:

1. Statically parses `.py` files using Python's built-in `ast` module without executing repository code.
2. Resolves repository-internal import relationships into a directed dependency graph using NetworkX.
3. Computes graph-theoretic properties including degree distribution, isolated and pendant vertices, and cycle detection.
4. Generates an interactive PyVis HTML visualization with search, hover, zoom, pan, node selection, and a statistics panel.

The entire pipeline runs with a single command.

---

## Features

- Static, execution-free dependency extraction using Python's `ast` module
- Repository-internal import resolution for absolute and relative imports
- Directed dependency graph built with NetworkX
- Graph-theoretic analysis:
  - In-degree
  - Out-degree
  - Isolated vertices
  - Pendant vertices
  - Degree distribution
  - Top nodes by degree
  - DAG/cycle detection
  - Import-count-based coupling
- Interactive PyVis visualization with:
  - Force-directed ForceAtlas2 layout
  - Node size mapped to in-degree
  - Node color mapped to folder/package
  - Directed edges showing dependency direction
  - Edge thickness mapped to import count
  - Hover tooltips
  - Search box
  - Zoom and pan
  - Node selection
  - Statistics panel
  - Legend
- Single-command pipeline orchestration through `run.py`

---

## Architecture

```mermaid
flowchart TD
    A[GitHub Python Repository] --> B[run.py]
    B --> C[extract.py]
    C --> D[graph.json]
    D --> E[analyze.py]
    E --> F[analysis.json]
    D --> G[visualize.py]
    F --> G
    G --> H[graph.html]