"""
src/extract.py

Statically extracts a repository-internal, directed Python import-dependency
graph using the ast module, and writes it to data/processed/graph.json.

Usage:
    python src/extract.py data/raw/<repository>
"""

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path

IGNORED_DIRS = {
    ".git", ".venv", "venv", "__pycache__",
    "node_modules", ".pytest_cache", "dist", "build",
}


def find_python_files(repo_root: Path):
    files = []
    for path in repo_root.rglob("*.py"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def module_dotted_name(rel_path: Path):
    """Return (dotted_name, is_init) for a repo-relative .py path."""
    parts = list(rel_path.parts)
    if parts[-1] == "__init__.py":
        mod_parts = parts[:-1]
        is_init = True
    else:
        mod_parts = parts[:-1] + [Path(parts[-1]).stem]
        is_init = False
    return ".".join(mod_parts), is_init


def build_module_index(py_files, repo_root: Path):
    """dotted module/package name -> repo-relative posix path."""
    index = {}
    for f in py_files:
        rel = f.relative_to(repo_root)
        dotted, _ = module_dotted_name(rel)
        if dotted:
            index[dotted] = rel.as_posix()
    return index


def resolve_absolute(dotted, index):
    if dotted in index:
        return index[dotted]
    return None


def resolve_from_import(module, alias_name, level, current_dotted, is_init, index):
    """Resolve a `from X import Y` statement to a repo-relative path, or None."""
    base_parts = current_dotted.split(".") if current_dotted else []
    if not is_init:
        base_parts = base_parts[:-1]  # containing package of a regular module

    if level > 0:
        # relative import: level 1 = current package, level 2 = parent, etc.
        cut = len(base_parts) - (level - 1)
        target_parts = base_parts[: max(cut, 0)]
        if module:
            target_parts = target_parts + module.split(".")
    else:
        if not module:
            return None
        target_parts = module.split(".")

    dotted = ".".join(target_parts)

    # Case 1: "from pkg.mod import name" where pkg.mod is the file itself
    resolved = resolve_absolute(dotted, index)
    if resolved:
        return resolved

    # Case 2: "from pkg import submodule" where submodule is the actual file
    if alias_name:
        candidate = ".".join(target_parts + [alias_name])
        resolved = resolve_absolute(candidate, index)
        if resolved:
            return resolved

    return None


def extract_edges_from_file(file_path: Path, rel_path: Path, index):
    """Return a list of resolved target paths this file depends on."""
    targets = []
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError) as exc:
        print(f"[warn] skipped {rel_path}: {exc}", file=sys.stderr)
        return targets

    current_dotted, is_init = module_dotted_name(rel_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = resolve_absolute(alias.name, index)
                if resolved:
                    targets.append(resolved)

        elif isinstance(node, ast.ImportFrom):
            if node.names and node.names[0].name != "*":
                for alias in node.names:
                    resolved = resolve_from_import(
                        node.module, alias.name, node.level,
                        current_dotted, is_init, index,
                    )
                    if resolved:
                        targets.append(resolved)
            else:
                resolved = resolve_from_import(
                    node.module, None, node.level,
                    current_dotted, is_init, index,
                )
                if resolved:
                    targets.append(resolved)

    return targets


def build_graph(repo_root: Path):
    py_files = find_python_files(repo_root)
    index = build_module_index(py_files, repo_root)

    edge_counter = Counter()
    nodes = {}

    for f in py_files:
        rel = f.relative_to(repo_root).as_posix()
        nodes[rel] = {
            "id": rel,
            "path": rel,
            "filename": Path(rel).name,
            "folder": str(Path(rel).parent) if Path(rel).parent != Path(".") else "",
        }

    for f in py_files:
        rel = f.relative_to(repo_root).as_posix()
        for target in extract_edges_from_file(f, Path(rel), index):
            if target != rel:
                edge_counter[(rel, target)] += 1

    edges = [
        {"source": src, "target": dst, "import_count": count}
        for (src, dst), count in edge_counter.items()
    ]

    metadata = {
        "repository_path": str(repo_root),
        "python_file_count": len(py_files),
        "node_count": len(nodes),
        "edge_count": len(edges),
    }

    return {
        "metadata": metadata,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract DepViz dependency graph.")
    parser.add_argument("repo_path", help="Path to the target Python repository")
    parser.add_argument(
        "-o", "--output",
        default="data/processed/graph.json",
        help="Output JSON path (default: data/processed/graph.json)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_path).resolve()
    if not repo_root.is_dir():
        print(f"[error] invalid repository path: {repo_root}", file=sys.stderr)
        sys.exit(1)

    graph_data = build_graph(repo_root)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(graph_data, indent=2), encoding="utf-8")

    print(f"[ok] wrote {out_path} "
          f"({graph_data['metadata']['node_count']} nodes, "
          f"{graph_data['metadata']['edge_count']} edges)")


if __name__ == "__main__":
    main()