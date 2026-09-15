"""Command-line entry point for the ground-truth simulator.

Usage:
    python -m mstt.sim.run --scenario config/scenarios/A_single_cv.yaml

Writes truth.csv into a per-scenario run directory under data/runs/, following the
layout in docs/conventions.md section 6.2.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mstt.io.truth_csv import write_truth_csv
from mstt.sim.scenario import Scenario, ScenarioError

DEFAULT_RUN_ROOT = Path("data/runs")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mstt-sim",
        description="Generate ground-truth target trajectories from a scenario file.",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        type=Path,
        help="Path to a scenario YAML file.",
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
    truth_path = out_dir / "truth.csv"

    world = scenario.build_world()
    rows = write_truth_csv(truth_path, world.run())

    print(f"scenario   : {scenario.name}")
    print(f"targets    : {len(scenario.targets)}")
    print(
        f"duration   : {scenario.simulation.duration_s:g} s "
        f"@ {scenario.simulation.timestep_s:g} s timestep"
    )
    print(f"timesteps  : {world.step_count}")
    print(f"truth rows : {rows}")
    print(f"written    : {truth_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
