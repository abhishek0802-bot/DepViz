"""
src/visualize.py

Loads data/processed/graph.json, rebuilds the dependency graph in NetworkX,
and generates an interactive PyVis HTML visualization at output/graph.html.
Also reads data/processed/analysis.json (if available) to display a live
statistics panel.

Visual mapping:
    - Python file/module      -> node
    - Folder/package          -> node color (deterministic)
    - In-degree               -> node size
    - Import relationship     -> directed edge
    - import_count            -> edge width

Usage:
    python src/visualize.py
    python src/visualize.py --input data/processed/graph.json --output output/graph.html
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import networkx as nx
from pyvis.network import Network

ISOLATED_NODE_SIZE = 8
BASE_NODE_SIZE = 14
SIZE_PER_IN_DEGREE = 6

MIN_EDGE_WIDTH = 1
WIDTH_PER_IMPORT = 1.5
MAX_EDGE_WIDTH = 10

FOLDER_PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080",
    "#9a6324", "#808000", "#000075", "#e6beff", "#aaffc3",
]


def load_graph_data(input_path: Path) -> dict:
    if not input_path.is_file():
        print(f"[error] input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with input_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"[error] malformed JSON in {input_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    if "nodes" not in data or "edges" not in data:
        print(f"[error] {input_path} is missing required 'nodes'/'edges' keys", file=sys.stderr)
        sys.exit(1)

    return data


def build_graph(data: dict) -> nx.DiGraph:
    G = nx.DiGraph()

    for node in data["nodes"]:
        node_id = node["id"]
        G.add_node(
            node_id,
            filename=node.get("filename", node_id),
            folder=node.get("folder", ""),
            path=node.get("path", node_id),
        )

    for edge in data["edges"]:
        src, dst = edge["source"], edge["target"]
        if src not in G:
            G.add_node(src, filename=src, folder="", path=src)
        if dst not in G:
            G.add_node(dst, filename=dst, folder="", path=dst)
        G.add_edge(src, dst, import_count=edge.get("import_count", 1))

    return G


def fallback_stats(G: nx.DiGraph) -> dict:
    """Recompute minimal stats directly from the graph if analysis.json is unavailable."""
    total_degree = {n: G.in_degree(n) + G.out_degree(n) for n in G.nodes}
    isolated = sum(1 for d in total_degree.values() if d == 0)
    pendant = sum(1 for d in total_degree.values() if d == 1)
    is_dag = nx.is_directed_acyclic_graph(G)
    cycle_count = 0 if is_dag else len(list(nx.simple_cycles(G)))

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "isolated_node_count": isolated,
        "pendant_node_count": pendant,
        "is_dag": is_dag,
        "cycle_count": cycle_count,
    }


def load_analysis_data(analysis_path: Path, G: nx.DiGraph) -> dict:
    """Read analysis.json; fall back to recomputed stats if missing/malformed."""
    if not analysis_path.is_file():
        print(f"[warn] {analysis_path} not found; computing stats directly from graph", file=sys.stderr)
        return fallback_stats(G)

    try:
        with analysis_path.open("r", encoding="utf-8") as f:
            analysis = json.load(f)
        deg = analysis["degree_analysis"]
        cyc = analysis["cycle_analysis"]
        return {
            "total_nodes": deg["total_nodes"],
            "total_edges": deg["total_edges"],
            "isolated_node_count": deg["isolated_node_count"],
            "pendant_node_count": deg["pendant_node_count"],
            "is_dag": cyc["is_dag"],
            "cycle_count": cyc["cycle_count"],
        }
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"[warn] could not parse {analysis_path} ({exc}); computing stats directly from graph", file=sys.stderr)
        return fallback_stats(G)


def folder_color_map(G: nx.DiGraph) -> dict:
    """Deterministic folder -> color, stable across runs."""
    folders = sorted({G.nodes[n].get("folder", "") for n in G.nodes})
    color_map = {}
    for folder in folders:
        digest = hashlib.md5(folder.encode("utf-8")).hexdigest()
        index = int(digest, 16) % len(FOLDER_PALETTE)
        color_map[folder] = FOLDER_PALETTE[index]
    return color_map


def node_size(in_degree: int) -> float:
    if in_degree == 0:
        return ISOLATED_NODE_SIZE
    return BASE_NODE_SIZE + (in_degree * SIZE_PER_IN_DEGREE)


def edge_width(import_count: int) -> float:
    width = MIN_EDGE_WIDTH + (import_count * WIDTH_PER_IMPORT)
    return min(width, MAX_EDGE_WIDTH)


def build_network(G: nx.DiGraph) -> Network:
    net = Network(
        height="850px",
        width="100%",
        directed=True,
        bgcolor="#1e1e1e",
        font_color="#f0f0f0",
    )

    color_map = folder_color_map(G)
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())

    for node_id, attrs in G.nodes(data=True):
        folder = attrs.get("folder", "")
        filename = attrs.get("filename", node_id)
        path = attrs.get("path", node_id)
        in_deg = in_degrees.get(node_id, 0)
        out_deg = out_degrees.get(node_id, 0)

        tooltip = (
            f"filename: {filename}\n"
            f"path: {path}\n"
            f"folder: {folder or '(root)'}\n"
            f"in-degree: {in_deg}\n"
            f"out-degree: {out_deg}"
        )

        net.add_node(
            node_id,
            label=filename,
            title=tooltip,
            color=color_map.get(folder, "#cccccc"),
            size=node_size(in_deg),
            shape="dot",
        )

    for src, dst, attrs in G.edges(data=True):
        import_count = attrs.get("import_count", 1)
        net.add_edge(
            src,
            dst,
            width=edge_width(import_count),
            title=f"import_count: {import_count}",
            arrows="to",
            color={"color": "#888888", "highlight": "#ffcc00"},
        )

    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -60,
          "centralGravity": 0.01,
          "springLength": 120,
          "springConstant": 0.08,
          "damping": 0.4,
          "avoidOverlap": 0.5
        },
        "solver": "forceAtlas2Based",
        "stabilization": {
          "enabled": true,
          "iterations": 300
        },
        "minVelocity": 0.75
      },
      "interaction": {
        "hover": true,
        "zoomView": true,
        "dragView": true,
        "selectable": true,
        "tooltipDelay": 150
      },
      "edges": {
        "smooth": {
          "type": "continuous"
        }
      }
    }
    """)

    return net


UI_TEMPLATE = """
<div style="position:fixed; top:0; left:0; right:0; z-index:1000;
            background:#2b2b2b; color:#f0f0f0; padding:10px 18px;
            font-family:sans-serif; display:flex; align-items:center;
            justify-content:space-between; border-bottom:1px solid #444;
            box-shadow:0 2px 6px rgba(0,0,0,0.4);">
  <div>
    <div style="font-size:17px; font-weight:bold;">DepViz</div>
    <div style="font-size:12px; color:#aaaaaa;">Interactive Software Dependency Visualization</div>
  </div>
  <div style="display:flex; gap:18px; font-size:13px;">
    <div><span style="color:#aaaaaa;">Nodes:</span> __TOTAL_NODES__</div>
    <div><span style="color:#aaaaaa;">Edges:</span> __TOTAL_EDGES__</div>
    <div><span style="color:#aaaaaa;">Isolated:</span> __ISOLATED_COUNT__</div>
    <div><span style="color:#aaaaaa;">Pendant:</span> __PENDANT_COUNT__</div>
    <div><span style="color:#aaaaaa;">DAG:</span> __IS_DAG__</div>
    <div><span style="color:#aaaaaa;">Cycles:</span> __CYCLE_COUNT__</div>
  </div>
</div>

<div style="position:fixed; top:66px; left:14px; z-index:1000;
            background:#2b2b2b; color:#f0f0f0; padding:8px 10px;
            border-radius:8px; font-family:sans-serif; font-size:13px;
            box-shadow:0 2px 6px rgba(0,0,0,0.4);">
  <input id="depviz-search" type="text" placeholder="Search filename or path..."
         style="padding:4px 8px; width:200px; border-radius:4px; border:none;">
  <button id="depviz-search-btn" style="padding:4px 10px; margin-left:4px;
          border-radius:4px; border:none; cursor:pointer;">Find</button>
  <div id="depviz-search-result" style="margin-top:6px; font-size:12px; color:#cccccc;"></div>
</div>

<div style="position:fixed; bottom:12px; right:12px; z-index:1000;
            background:#2b2b2b; color:#f0f0f0; padding:10px 14px;
            border-radius:8px; font-family:sans-serif; font-size:12px; line-height:1.6;
            box-shadow:0 2px 6px rgba(0,0,0,0.4); max-width:260px;">
  <strong>Legend</strong><br>
  Node size = in-degree (how many files depend on it)<br>
  Node color = folder/package<br>
  Edge direction (arrow) = dependency direction (A &rarr; B means A depends on B)<br>
  Edge thickness = import_count (coupling strength)
</div>

<script type="text/javascript">
  (function () {
    function runSearch() {
      var query = document.getElementById('depviz-search').value.trim().toLowerCase();
      var resultBox = document.getElementById('depviz-search-result');
      if (!query) {
        resultBox.innerText = "";
        return;
      }

      var allNodes = nodes.get();
      var matches = allNodes.filter(function (n) {
        var label = (n.label || "").toLowerCase();
        var title = (n.title || "").toLowerCase();
        return label.indexOf(query) !== -1 || title.indexOf(query) !== -1;
      });

      if (matches.length === 0) {
        resultBox.innerText = "No match found.";
        return;
      }

      var matchIds = matches.map(function (n) { return n.id; });
      network.selectNodes(matchIds);
      network.focus(matchIds[0], { scale: 1.5, animation: true });
      resultBox.innerText = matches.length + " match(es) found and selected.";
    }

    document.getElementById('depviz-search-btn').addEventListener('click', runSearch);
    document.getElementById('depviz-search').addEventListener('keyup', function (e) {
      if (e.key === 'Enter') runSearch();
    });
  })();
</script>
"""


def inject_ui(html_path: Path, stats: dict) -> None:
    """Insert stats panel + search box + legend into the PyVis-generated HTML."""
    html = html_path.read_text(encoding="utf-8")

    ui = (
        UI_TEMPLATE
        .replace("__TOTAL_NODES__", str(stats["total_nodes"]))
        .replace("__TOTAL_EDGES__", str(stats["total_edges"]))
        .replace("__ISOLATED_COUNT__", str(stats["isolated_node_count"]))
        .replace("__PENDANT_COUNT__", str(stats["pendant_node_count"]))
        .replace("__IS_DAG__", "Yes" if stats["is_dag"] else "No")
        .replace("__CYCLE_COUNT__", str(stats["cycle_count"]))
    )

    if "</body>" in html:
        html = html.replace("</body>", ui + "\n</body>")
    else:
        html += ui
    html_path.write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate DepViz interactive visualization.")
    parser.add_argument(
        "--input",
        default="data/processed/graph.json",
        help="Path to input graph.json (default: data/processed/graph.json)",
    )
    parser.add_argument(
        "--analysis",
        default="data/processed/analysis.json",
        help="Path to analysis.json (default: data/processed/analysis.json)",
    )
    parser.add_argument(
        "--output",
        default="output/graph.html",
        help="Path to output HTML file (default: output/graph.html)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    analysis_path = Path(args.analysis)
    output_path = Path(args.output)

    data = load_graph_data(input_path)
    G = build_graph(data)

    if G.number_of_nodes() == 0:
        print("[error] graph has no nodes; nothing to visualize", file=sys.stderr)
        sys.exit(1)

    stats = load_analysis_data(analysis_path, G)

    net = build_network(G)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    net.write_html(str(output_path), notebook=False)
    inject_ui(output_path, stats)

    print(
        f"[ok] wrote {output_path} "
        f"({G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
        f"isolated={stats['isolated_node_count']}, pendant={stats['pendant_node_count']}, "
        f"DAG={stats['is_dag']}, cycles={stats['cycle_count']})"
    )


if __name__ == "__main__":
    main()