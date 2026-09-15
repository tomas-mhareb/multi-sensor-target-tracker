"""Plot ground-truth trajectories from a run directory.

This is a debugging instrument, not the dashboard. Its job is to make it possible to
see at a glance whether the simulator did what the scenario asked, which is far
faster than reading several thousand CSV rows. The dashboard comes at V0.7.

Usage:
    python -m mstt.viz.plot_truth --run data/runs/A_single_cv
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

# Select a non-interactive backend before pyplot is imported, so the script works
# unchanged over SSH, inside Docker, and in CI where no display is available.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402


def load_truth(path: Path) -> dict[int, list[tuple[float, float]]]:
    """Read truth.csv into per-target lists of (x_m, y_m)."""
    tracks: dict[int, list[tuple[float, float]]] = defaultdict(list)
    with path.open() as handle:
        for row in csv.DictReader(handle):
            tracks[int(row["target_id"])].append((float(row["x_m"]), float(row["y_m"])))
    return dict(tracks)


def plot_truth(run_dir: Path, output: Path | None = None) -> Path:
    truth_path = run_dir / "truth.csv"
    if not truth_path.is_file():
        raise FileNotFoundError(f"no truth.csv in {run_dir}")

    tracks = load_truth(truth_path)
    output = output or run_dir / "truth.png"

    fig, ax = plt.subplots(figsize=(8, 6))
    for target_id in sorted(tracks):
        xs, ys = zip(*tracks[target_id], strict=True)
        ax.plot(xs, ys, linewidth=1.5, label=f"target {target_id}")
        ax.plot(xs[0], ys[0], marker="o", markersize=6, color=ax.lines[-1].get_color())

    ax.plot(0, 0, marker="^", markersize=10, color="black", label="surveillance site")

    ax.set_xlabel("x — East (m)")
    ax.set_ylabel("y — North (m)")
    ax.set_title(f"Ground truth — {run_dir.name}")
    # Equal aspect so a 45-degree heading looks like 45 degrees. Without this,
    # trajectories are visually sheared and heading errors become invisible.
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(output, dpi=140)
    plt.close(fig)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot ground-truth trajectories.")
    parser.add_argument("--run", required=True, type=Path, help="Run directory.")
    parser.add_argument("--out", type=Path, default=None, help="Output PNG path.")
    args = parser.parse_args(argv)

    written = plot_truth(args.run, args.out)
    print(f"wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
