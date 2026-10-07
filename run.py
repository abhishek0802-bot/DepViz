"""
run.py

Single-command orchestrator for the DepViz pipeline.
Runs extract.py -> analyze.py -> visualize.py in sequence as subprocesses,
using the same Python interpreter that launched this script.

Usage:
    python run.py <repository_path>

Example:
    python run.py data/raw/fastapi/fastapi
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

EXTRACT_SCRIPT = PROJECT_ROOT / "src" / "extract.py"
ANALYZE_SCRIPT = PROJECT_ROOT / "src" / "analyze.py"
VISUALIZE_SCRIPT = PROJECT_ROOT / "src" / "visualize.py"

GRAPH_JSON = PROJECT_ROOT / "data" / "processed" / "graph.json"
ANALYSIS_JSON = PROJECT_ROOT / "data" / "processed" / "analysis.json"
OUTPUT_HTML = PROJECT_ROOT / "output" / "graph.html"


def run_stage(stage_label: str, cmd: list) -> None:
    print(stage_label)
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"[error] stage failed: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Run the complete DepViz pipeline: extract -> analyze -> visualize."
    )
    parser.add_argument(
        "repository_path",
        help="Path to the target Python repository (e.g. data/raw/fastapi/fastapi)",
    )
    args = parser.parse_args()

    repo_path = Path(args.repository_path)
    if not repo_path.is_dir():
        print(f"[error] invalid repository path: {repo_path}", file=sys.stderr)
        sys.exit(1)

    python_exe = sys.executable

    run_stage(
        "[1/3] Extracting dependencies...",
        [python_exe, str(EXTRACT_SCRIPT), str(repo_path)],
    )

    run_stage(
        "[2/3] Analyzing dependency graph...",
        [python_exe, str(ANALYZE_SCRIPT)],
    )

    run_stage(
        "[3/3] Generating visualization...",
        [python_exe, str(VISUALIZE_SCRIPT)],
    )

    print("[ok] DepViz pipeline completed successfully.")
    print(f"[ok] Graph: {GRAPH_JSON}")
    print(f"[ok] Analysis: {ANALYSIS_JSON}")
    print(f"[ok] Visualization: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()