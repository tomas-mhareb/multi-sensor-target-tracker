"""Plot a scenario run: ground truth with the sensor measurements overlaid.

The point of this plot is to make the sensor model visible. Truth is a clean line;
measurements are a scatter of noise around it, punctuated by gaps where the radar
missed and by clutter that corresponds to nothing. Seeing that is what motivates the
Kalman filter in V0.3 -- the estimate should follow the line, not the scatter.

Usage:
    python -m mstt.viz.plot_run --run data/runs/B_single_noisy
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

from mstt.io.measurement_jsonl import (  # noqa: E402
    FALSE_ALARM_TARGET_ID,
    read_measurements_jsonl,
)
from mstt.sensors.geometry import polar_to_cartesian  # noqa: E402


def load_truth(path: Path) -> dict[int, list[tuple[float, float]]]:
    tracks: dict[int, list[tuple[float, float]]] = defaultdict(list)
    with path.open() as handle:
        for row in csv.DictReader(handle):
            tracks[int(row["target_id"])].append((float(row["x_m"]), float(row["y_m"])))
    return dict(tracks)


def load_labels(path: Path) -> dict[int, int]:
    """Read the evaluation key: which target produced each measurement.

    Used here only to colour the plot. The tracking engine never reads this file --
    distinguishing a real detection from clutter is precisely the job it has to do.
    """
    if not path.is_file():
        return {}
    with path.open() as handle:
        return {int(r["meas_id"]): int(r["target_id"]) for r in csv.DictReader(handle)}


def plot_run(run_dir: Path, output: Path | None = None) -> Path:
    truth_path = run_dir / "truth.csv"
    if not truth_path.is_file():
        raise FileNotFoundError(f"no truth.csv in {run_dir}")

    summary = json.loads((run_dir / "run_summary.json").read_text())
    sensor_positions = {k: tuple(v) for k, v in summary.get("sensor_positions", {}).items()}
    labels = load_labels(run_dir / "measurement_truth.csv")
    output = output or run_dir / "run.png"

    fig, ax = plt.subplots(figsize=(9, 7))

    detections_xy: list[tuple[float, float]] = []
    clutter_xy: list[tuple[float, float]] = []

    measurements_path = run_dir / "measurements.jsonl"
    if measurements_path.is_file():
        for m in read_measurements_jsonl(measurements_path):
            sx, sy = sensor_positions.get(m.sensor_id, (0.0, 0.0))
            dx, dy = polar_to_cartesian(m.values["range_m"], m.values["bearing_rad"])
            point = (sx + float(dx), sy + float(dy))
            if labels.get(m.meas_id, FALSE_ALARM_TARGET_ID) == FALSE_ALARM_TARGET_ID:
                clutter_xy.append(point)
            else:
                detections_xy.append(point)

    if clutter_xy:
        ax.scatter(
            *zip(*clutter_xy, strict=True),
            s=9,
            c="#d62728",
            alpha=0.35,
            marker="x",
            linewidths=0.8,
            label=f"false alarms ({len(clutter_xy)})",
        )
    if detections_xy:
        ax.scatter(
            *zip(*detections_xy, strict=True),
            s=9,
            c="#7f7f7f",
            alpha=0.55,
            label=f"radar detections ({len(detections_xy)})",
        )

    truth_points: list[tuple[float, float]] = []
    for target_id, points in sorted(load_truth(truth_path).items()):
        truth_points.extend(points)
        xs, ys = zip(*points, strict=True)
        ax.plot(
            xs,
            ys,
            linewidth=2.0,
            color="#1f77b4",
            zorder=3,
            label=f"ground truth (target {target_id})",
        )
        ax.plot(xs[0], ys[0], marker="o", markersize=7, color="#1f77b4", zorder=4)

    for sensor_id, (sx, sy) in sensor_positions.items():
        ax.plot(sx, sy, marker="^", markersize=12, color="black", zorder=5, label=sensor_id)

    _add_zoom_inset(ax, truth_points, detections_xy, clutter_xy)

    ax.set_xlabel("x — East (m)")
    ax.set_ylabel("y — North (m)")
    detected = summary.get("detection_rate")
    subtitle = f"  ·  detection rate {detected:.1%}" if detected is not None else ""
    ax.set_title(f"{summary.get('scenario_name', run_dir.name)}{subtitle}")
    # Equal aspect so the noise cloud's shape is honest: the radar's error region is
    # a wedge, wider across the line of sight than along it, and a stretched axis
    # would hide exactly that.
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=9)
    fig.tight_layout()
    fig.savefig(output, dpi=140)
    plt.close(fig)
    return output


def _add_zoom_inset(ax, truth_points, detections_xy, clutter_xy, half_width_m=40.0):
    """Inset a close view of the trajectory midpoint.

    At full scale the measurement scatter is invisible: 2 m of range noise against an
    800 m trajectory is a quarter of a percent. The inset is what actually shows the
    sensor model, and it is where the wedge becomes visible -- the cloud is wider
    across the line of sight than along it.
    """
    if not truth_points or not detections_xy:
        return

    cx, cy = truth_points[len(truth_points) // 2]
    inset = ax.inset_axes([0.62, 0.04, 0.36, 0.36])

    for points, style in (
        (clutter_xy, {"s": 14, "c": "#d62728", "marker": "x", "linewidths": 0.9}),
        (detections_xy, {"s": 14, "c": "#7f7f7f", "alpha": 0.75}),
    ):
        inside = [
            p for p in points if abs(p[0] - cx) <= half_width_m and abs(p[1] - cy) <= half_width_m
        ]
        if inside:
            inset.scatter(*zip(*inside, strict=True), zorder=2, **style)

    txs, tys = zip(*truth_points, strict=True)
    inset.plot(txs, tys, linewidth=2.0, color="#1f77b4", zorder=3)

    inset.set_xlim(cx - half_width_m, cx + half_width_m)
    inset.set_ylim(cy - half_width_m, cy + half_width_m)
    inset.set_aspect("equal")
    inset.set_xticklabels([])
    inset.set_yticklabels([])
    inset.tick_params(length=0)
    inset.set_title(f"zoom: {2 * half_width_m:g} m across", fontsize=8, pad=3)
    ax.indicate_inset_zoom(inset, edgecolor="black", alpha=0.6, linewidth=1.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot a run: truth plus measurements.")
    parser.add_argument("--run", required=True, type=Path, help="Run directory.")
    parser.add_argument("--out", type=Path, default=None, help="Output PNG path.")
    args = parser.parse_args(argv)

    print(f"wrote {plot_run(args.run, args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
