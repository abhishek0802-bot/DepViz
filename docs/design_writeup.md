# DepViz: An Interactive Graph-Based Tool for Visualizing Software Dependency Structures

### Design and Implementation Write-up

---

# 1. Introduction

Modern software systems are composed of many interdependent files and modules, and understanding how these components relate to one another is essential for maintenance, refactoring, and onboarding new developers. As codebases grow, these relationships become difficult to reason about by reading source code alone. DepViz addresses this by treating a Python codebase as a graph: files are vertices, and import relationships are directed edges. The tool statically analyzes a real-world Python repository, constructs a directed dependency graph, computes graph-theoretic properties, and renders the result as an interactive visualization that a user can explore in a browser.

This project was developed as part of a Graph Visualization course and is intended to demonstrate the practical application of graph theory concepts, visualization design principles, and interaction techniques covered in the syllabus.

# 2. Problem Statement

Developers working with an unfamiliar or large codebase often need to answer questions such as: Which files does this module depend on? Which files are depended on by many others, making them structurally critical? Are there isolated files that aren't connected to the rest of the system? Does the codebase contain circular dependencies? Answering these questions by manually reading source code is slow and error-prone. DepViz addresses this by statically extracting the dependency structure and presenting it as an interactive graph, allowing these questions to be answered visually rather than through manual code inspection.

# 3. Objectives

- Statically extract file-level, repository-internal import relationships from a real Python codebase without executing any of its source code.
- Represent the extracted relationships as a directed graph using NetworkX.
- Compute graph-theoretic properties relevant to software structure: degree distribution, isolated and pendant vertices, and cycle detection.
- Design a visual encoding that maps graph and metadata attributes to visual variables in a principled way.
- Provide an interactive, browser-based visualization that supports exploration through zoom, pan, search, and node selection.
- Package the entire pipeline into a single, reproducible command.

# 4. System Overview

DepViz is a three-stage, command-line pipeline built entirely on the Python standard library, NetworkX, and PyVis. Given the path to a Python repository, it:

1. Parses every `.py` file in the repository using the `ast` module and extracts internal import relationships (`extract.py`).
2. Reconstructs the extracted graph in NetworkX and computes structural statistics, including degree distributions, isolated/pendant vertices, and cycle detection (`analyze.py`).
3. Generates an interactive PyVis HTML visualization with a statistics panel, search, and legend (`visualize.py`).

The three stages are chained by a single orchestrator script, `run.py`, so the entire pipeline runs with one command.

# 5. System Architecture
Each stage writes its output to a fixed location that the next stage consumes, forming a simple, inspectable data pipeline:

- `extract.py` → `data/processed/graph.json`
- `analyze.py` → `data/processed/analysis.json`
- `visualize.py` → `output/graph.html`

Because each stage communicates only through these JSON files, each script can be run and verified independently, and the pipeline has no hidden shared state between stages.

# 6. Data Acquisition and Static Dependency Extraction

The target dataset for this project is the production source package of the FastAPI GitHub repository, located at `data/raw/fastapi/fastapi`. The repository's test suite and documentation were deliberately excluded from the analyzed graph, since the project is concerned with the internal structure of the application code itself, not its supporting tooling.

Extraction is performed entirely through static analysis using Python's built-in `ast` module. `extract.py` recursively scans the target directory for `.py` files, while explicitly skipping `.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, `.pytest_cache`, `dist`, and `build` directories, since these do not represent source code relevant to the project's own structure.

For each source file, the file is parsed with `ast.parse()` — the file is never imported or executed, which avoids any risk of running arbitrary or unsafe code from the analyzed repository. The parser walks the resulting syntax tree and extracts both `import module` and `from module import name` statements, including relative imports (`from . import x`, `from ..pkg import y`). Each import target is resolved against an index of the repository's own files, built from each file's dotted module path; imports that cannot be resolved to a file inside the repository (standard-library or third-party packages) are not added as graph edges, since the project's scope is repository-internal structure only.

Repeated imports between the same pair of files are collapsed into a single directed edge, with the number of originating import statements recorded as `import_count` — this value is later used as a proxy for coupling strength between two files.

# 7. Graph Representation

The dependency structure is represented as a directed graph, `G = (V, E)`, where:

- Each vertex `v ∈ V` corresponds to one Python file in the analyzed repository, identified by its repository-relative path.
- Each directed edge `(A, B) ∈ E` indicates that file `A` imports file `B`, i.e., `A` depends on `B`.

This directionality is semantically important: it distinguishes "the files I depend on" from "the files that depend on me," which is the basis for the in-degree/out-degree analysis described next. The extracted graph is serialized to `data/processed/graph.json` using a stable schema (`metadata`, `nodes`, `edges`) so it can be consumed independently by the analysis and visualization stages.

# 8. Graph-Theoretic Analysis

`analyze.py` reconstructs the graph from `graph.json` using NetworkX and computes the following properties, directly applying the graph-theory vocabulary introduced early in the course syllabus:

- **In-degree**: the number of files that depend on a given file. A file with high in-degree is structurally significant, since many other files rely on it.
- **Out-degree**: the number of files a given file depends on.
- **Isolated vertices**: files with total degree zero — neither importing, nor imported by, any other file in the repository.
- **Pendant vertices**: files with total degree one — minimally connected to the rest of the structure.
- **Degree distribution**: the frequency of each in-degree and out-degree value across all vertices, giving a sense of how dependency load is spread across the codebase.
- **DAG and cycle detection**: `networkx.is_directed_acyclic_graph()` determines whether the graph contains any circular dependencies; if not, `networkx.simple_cycles()` enumerates them.
- **Edge coupling**: using the `import_count` attribute on each edge, the strongest dependency relationships (the file pairs with the most import statements between them) are identified.

These results are written to `data/processed/analysis.json`, which is consumed directly by the visualization stage to populate its statistics panel.

# 9. Visual Encoding and Design

The visualization applies a deliberate, consistent mapping from data and graph attributes to visual variables, built with PyVis:

| Data Attribute | Visual Variable |
|---|---|
| Python file/module | Node |
| Folder/package | Node color (deterministic, hash-based assignment) |
| In-degree | Node size |
| Import relationship | Directed edge |
| `import_count` | Edge thickness |
| — | Node position (force-directed ForceAtlas2 layout) |

Node size scales with in-degree so that structurally important files (those depended on by many others) are immediately visually distinguishable from peripheral ones. Isolated vertices (in-degree zero) are rendered at a smaller, fixed size — visible, but visually de-emphasized relative to connected nodes, reflecting their reduced structural role without hiding them from the graph. Edge thickness scales with `import_count`, giving a direct visual read of coupling strength between two files. Directed arrows on every edge make the dependency direction explicit, which is essential since `A → B` and `B → A` have distinct meanings in this graph.

# 10. Gestalt Principles

Two Gestalt principles are applied directly in the visual design:

- **Similarity**: files belonging to the same folder/package are assigned the same node color, using a deterministic hash of the folder name. This allows a viewer to visually group files by package membership at a glance, without needing to read every label.
- **Proximity**: the force-directed layout naturally pulls connected nodes closer together and pushes disconnected or loosely connected nodes apart, so that files which interact frequently tend to cluster spatially. This is a byproduct of the physics simulation rather than an explicit grouping instruction, but it produces a layout where structurally related files tend to appear near one another.

# 11. Interaction Design

In line with the course's emphasis on interaction as a core component of visual analytics, DepViz implements the following interaction techniques, all functioning within the single generated HTML file:

- **Zoom and pan**: standard PyVis/vis.js canvas navigation, allowing the user to move between an overview of the full graph and close inspection of a specific region.
- **Hover (details-on-demand)**: hovering over a node reveals its filename, full path, folder, in-degree, and out-degree. Hovering over an edge reveals its `import_count`.
- **Node selection**: clicking a node highlights it and its connections within the canvas.
- **Search**: a search box allows the user to type a filename or path fragment; matching nodes are selected and the view focuses on the first match, letting the user locate a specific file without manually scanning the graph.

These interactions allow a user to move from a high-level overview of the dependency structure to specific file-level detail, which is the core workflow the tool is designed to support.

# 12. Visualization of Groups

The "Visualization of Groups" concept from the syllabus is addressed through folder/package-based grouping. Rather than a formal tree or dendrogram layout, grouping is expressed through two complementary visual cues: color (every file in the same folder shares a color) and spatial clustering (the force-directed layout tends to position related, interconnected files near each other). Together, these allow a viewer to visually identify which package a cluster of nodes belongs to without needing an explicit hierarchical layout structure.

# 13. Implementation Details

The project is implemented entirely in Python, using only the standard library plus NetworkX 3.7 and PyVis 0.3.2 — no additional frameworks, databases, or machine learning components were introduced, in keeping with the project's fixed technology constraint.

- **`src/extract.py`**: performs AST-based static parsing and repository-internal import resolution, producing `data/processed/graph.json`.
- **`src/analyze.py`**: reconstructs the graph and computes all graph-theoretic statistics described in Section 8, producing `data/processed/analysis.json`.
- **`src/visualize.py`**: builds the PyVis network with the visual mapping described in Section 9, and post-processes the generated HTML to inject a statistics panel (populated from `analysis.json`), a search box, and a legend, producing `output/graph.html`.
- **`run.py`**: a thin orchestrator that invokes the three stages above as subprocesses, in order, using the active Python interpreter. It halts immediately and reports a non-zero exit code if any stage fails, so that a broken intermediate step cannot silently produce a misleading final visualization.

The full pipeline runs with a single command:

# 14. Experimental Setup

The dataset used for evaluation is the production source package of the FastAPI GitHub repository, analyzed at the path `data/raw/fastapi/fastapi`. Only this source package was analyzed; the repository's test suite and documentation directories were excluded from the target graph, since the goal of the experiment was to examine the internal structure of the application code itself.

The pipeline was run end-to-end via `run.py`, producing `graph.json`, `analysis.json`, and the final `graph.html` visualization in a single invocation.

# 15. Results and Discussion

The analysis of the FastAPI production source package produced the following measured results:

| Metric | Value |
|---|---|
| Python files / graph vertices | 52 |
| Directed dependency edges | 25 |
| Isolated vertices | 28 |
| Pendant vertices | 13 |
| Directed Acyclic Graph (DAG) | True |
| Directed cycles detected | 0 |

The graph is confirmed to be a DAG, with zero directed cycles — indicating that, at the file level, the analyzed package does not contain circular import relationships.This indicates that no circular import relationships were detected at the analyzed file level, which can simplify dependency reasoning and maintenance. The visualization's statistics panel surfaces this result directly to the viewer.

The relatively high proportion of isolated vertices (28 of 52, approximately 54%) indicates that just over half of the files in this package have no repository-internal import relationship with another file in the analyzed source tree, at least as detected through static, repository-internal resolution. This is plausible for a package like FastAPI's, where many files may rely primarily on external/third-party dependencies (which are intentionally excluded from this graph) or are relatively self-contained utility modules.The 13 pendant vertices represent files with exactly one incident dependency edge, making them structurally peripheral in the analyzed graph.

With only 25 edges among 52 vertices, the resulting graph is sparse. This sparsity is reflected in the visualization: most of the canvas is populated by isolated, small, evenly-sized nodes, while a smaller number of connected nodes form the visually denser, more clustered portion of the layout where folder-based coloring and force-directed clustering are most apparent.

# 16. Limitations

- The analysis operates at file/module granularity, not symbol-level semantic analysis — it identifies that file A imports file B, but does not track which specific functions or classes are used.
- Static AST-based analysis cannot detect every dynamic import mechanism (e.g., imports constructed at runtime via string manipulation or `importlib`), so some real dependency relationships may not appear in the graph.
- Only repository-internal dependencies are represented; standard-library and third-party package imports are deliberately excluded, so the graph does not represent the complete set of a file's runtime dependencies.
- The analyzed FastAPI source package produced a sparse graph (25 edges across 52 vertices, with 28 isolated vertices), which limits how much structural insight can be drawn purely from connectivity patterns in this particular dataset.
- Relative import resolution (`from . import x`, `from ..pkg import y`) has practical limitations in edge cases involving unusual package layouts or non-standard project structures.
- As the number of vertices and edges grows substantially beyond this experiment's scale, the force-directed visualization becomes progressively harder to read, since node overlap and edge crossing increase with graph size.

# 17. Future Scope

Reasonable future improvements to DepViz include:

- More robust module resolution, including handling of namespace packages and more complex relative-import edge cases.
- Detection of dynamic import patterns, where feasible, to reduce missed dependency relationships.
- Support for larger repositories, potentially through sampling or incremental rendering strategies to maintain readability.
- Filtering and folder/group collapsing controls, allowing a user to simplify the view on demand — not currently implemented in this version.
- Package-level abstraction, aggregating file-level nodes into package-level nodes as an alternative, higher-level view.
- Richer cycle and coupling analysis, such as ranking cycles by severity or visualizing coupling trends across the whole repository rather than only the top edges.

# 18. Conclusion

DepViz demonstrates a complete, working pipeline that converts a real Python codebase into an interactive, graph-theoretically grounded visualization, using only static analysis — without executing any repository code. By applying core graph theory concepts (degree, isolated and pendant vertices, DAG and cycle detection), explicit visual mapping (color, size, edge thickness), Gestalt principles (similarity, proximity), and interaction techniques (zoom, pan, search, hover, selection), the project directly applies the concepts covered in the Graph Visualization course syllabus to a practical, real-world software engineering problem. The FastAPI case study confirmed the pipeline functions correctly end-to-end and produced a sparse but valid DAG, illustrating both the tool's capability and the natural limitations of file-level, repository-internal static analysis.