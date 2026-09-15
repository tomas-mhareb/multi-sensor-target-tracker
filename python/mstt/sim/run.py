"""Command-line entry point for the scenario simulator.

Usage:
    python -m mstt.sim.run --scenario config/scenarios/B_single_noisy.yaml

Writes run artifacts into a per-scenario directory under data/runs/, following the
layout in docs/conventions.md section 6.3.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mstt.sim.generate import generate_run, summary_as_dict
from mstt.sim.scenario import Scenario, ScenarioError

DEFAULT_RUN_ROOT = Path("data/runs")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mstt-sim",
        description="Run a scenario: generate ground truth and sensor measurements.",
    )
    parser.add_argument(
        "--scenario", required=True, type=Path, help="Path to a scenario YAML file."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            f"Output directory for run artifacts. Defaults to {DEFAULT_RUN_ROOT}/<scenario name>."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the simulator. Returns a process exit code."""
    args = build_parser().parse_args(argv)

    try:
        scenario = Scenario.from_yaml(args.scenario)
    except ScenarioError as exc:
        # Configuration problems are user errors, not crashes. Report them as a
        # clean message on stderr so the traceback does not obscure the cause.
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_dir = args.out if args.out is not None else DEFAULT_RUN_ROOT / scenario.name

    try:
        summary = generate_run(scenario, out_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    (out_dir / "run_summary.json").write_text(json.dumps(summary_as_dict(summary), indent=2) + "\n")
    _print_summary(scenario, summary, out_dir)
    return 0


def _print_summary(scenario: Scenario, summary, out_dir: Path) -> None:
    print(f"scenario   : {summary.scenario_name}")
    print(f"targets    : {len(scenario.targets)}")
    print(
        f"duration   : {scenario.simulation.duration_s:g} s "
        f"@ {scenario.simulation.timestep_s:g} s timestep "
        f"({summary.timesteps} steps)"
    )
    print(f"truth rows : {summary.truth_rows}")

    if not scenario.sensors:
        print("sensors    : none — ground truth only")
    else:
        names = ", ".join(s.sensor_id for s in scenario.sensors)
        print(f"sensors    : {names}  (seed {summary.seed})")
        print(f"scans      : {summary.scans}")
        print(
            f"detections : {summary.detections} of {summary.detection_opportunities} "
            f"in-range opportunities  ({summary.detection_rate:.1%})"
        )
        print(f"missed     : {summary.missed_detections}")
        print(f"false alarm: {summary.false_alarms}")
        print(f"measurement: {summary.measurements} total")

    print(f"written    : {out_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
