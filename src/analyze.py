"""
src/analyze.py

Loads data/processed/graph.json (produced by extract.py), rebuilds the
dependency graph in NetworkX, computes structural statistics, cycle
information, and edge-coupling stats, and writes the result to
data/processed/analysis.json.

Usage:
    python src/analyze.py
    python src/analyze.py --input data/processed/graph.json --output data/processed/analysis.json
"""

import argparse
import json
import sys
from pathlib import Path

import networkx as nx


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


def node_summary(G: nx.DiGraph, node_id: str) -> dict:
    attrs = G.nodes[node_id]
    return {
        "id": node_id,
        "filename": attrs.get("filename", node_id),
        "folder": attrs.get("folder", ""),
    }


def analyze_degrees(G: nx.DiGraph) -> dict:
    total_nodes = G.number_of_nodes()
    total_edges = G.number_of_edges()

    total_degree = {n: G.in_degree(n) + G.out_degree(n) for n in G.nodes}

    isolated_nodes = [n for n, d in total_degree.items() if d == 0]
    pendant_nodes = [n for n, d in total_degree.items() if d == 1]

    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())

    max_in = max(in_degrees.values()) if in_degrees else 0
    max_out = max(out_degrees.values()) if out_degrees else 0

    max_in_nodes = [n for n, d in in_degrees.items() if d == max_in and max_in > 0]
    max_out_nodes = [n for n, d in out_degrees.items() if d == max_out and max_out > 0]

    avg_in_degree = (total_edges / total_nodes) if total_nodes else 0.0
    avg_out_degree = avg_in_degree  # sum(in) == sum(out) == total_edges in a digraph

    in_degree_distribution = {}
    for d in in_degrees.values():
        in_degree_distribution[str(d)] = in_degree_distribution.get(str(d), 0) + 1

    out_degree_distribution = {}
    for d in out_degrees.values():
        out_degree_distribution[str(d)] = out_degree_distribution.get(str(d), 0) + 1

    top_in = sorted(in_degrees.items(), key=lambda kv: kv[1], reverse=True)[:10]
    top_out = sorted(out_degrees.items(), key=lambda kv: kv[1], reverse=True)[:10]

    return {
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "isolated_node_count": len(isolated_nodes),
        "isolated_nodes": [node_summary(G, n) for n in isolated_nodes],
        "pendant_node_count": len(pendant_nodes),
        "pendant_nodes": [node_summary(G, n) for n in pendant_nodes],
        "max_in_degree": max_in,
        "max_in_degree_nodes": [node_summary(G, n) for n in max_in_nodes],
        "max_out_degree": max_out,
        "max_out_degree_nodes": [node_summary(G, n) for n in max_out_nodes],
        "average_in_degree": round(avg_in_degree, 4),
        "average_out_degree": round(avg_out_degree, 4),
        "in_degree_distribution": in_degree_distribution,
        "out_degree_distribution": out_degree_distribution,
        "top_10_by_in_degree": [
            {**node_summary(G, n), "in_degree": d} for n, d in top_in
        ],
        "top_10_by_out_degree": [
            {**node_summary(G, n), "out_degree": d} for n, d in top_out
        ],
    }


def analyze_cycles(G: nx.DiGraph) -> dict:
    is_dag = nx.is_directed_acyclic_graph(G)
    cycles = [] if is_dag else list(nx.simple_cycles(G))

    return {
        "is_dag": is_dag,
        "cycle_count": len(cycles),
        "cycles": [
            [node_summary(G, n) for n in cycle] for cycle in cycles
        ],
    }


def analyze_coupling(G: nx.DiGraph) -> dict:
    edges_with_count = [
        (u, v, d.get("import_count", 1)) for u, v, d in G.edges(data=True)
    ]

    if not edges_with_count:
        return {
            "max_import_count": 0,
            "top_10_strongest_edges": [],
        }

    max_count = max(c for _, _, c in edges_with_count)
    top_edges = sorted(edges_with_count, key=lambda e: e[2], reverse=True)[:10]

    return {
        "max_import_count": max_count,
        "top_10_strongest_edges": [
            {
                "source": node_summary(G, u),
                "target": node_summary(G, v),
                "import_count": c,
            }
            for u, v, c in top_edges
        ],
    }


def run_analysis(data: dict) -> dict:
    G = build_graph(data)

    return {
        "metadata": {
            "source_metadata": data.get("metadata", {}),
            "analyzed_node_count": G.number_of_nodes(),
            "analyzed_edge_count": G.number_of_edges(),
        },
        "degree_analysis": analyze_degrees(G),
        "cycle_analysis": analyze_cycles(G),
        "coupling_analysis": analyze_coupling(G),
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze DepViz dependency graph.")
    parser.add_argument(
        "--input",
        default="data/processed/graph.json",
        help="Path to input graph.json (default: data/processed/graph.json)",
    )
    parser.add_argument(
        "--output",
        default="data/processed/analysis.json",
        help="Path to output analysis.json (default: data/processed/analysis.json)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    data = load_graph_data(input_path)
    report = run_analysis(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    deg = report["degree_analysis"]
    cyc = report["cycle_analysis"]
    print(
        f"[ok] wrote {output_path} "
        f"({deg['total_nodes']} nodes, {deg['total_edges']} edges, "
        f"{deg['isolated_node_count']} isolated, {deg['pendant_node_count']} pendant, "
        f"DAG={cyc['is_dag']}, cycles={cyc['cycle_count']})"
    )


if __name__ == "__main__":
    main()