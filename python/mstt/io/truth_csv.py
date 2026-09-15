"""Writer for the ground-truth CSV defined in docs/conventions.md section 6.1."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from mstt.sim.world import WorldState

TRUTH_COLUMNS = ("t_s", "target_id", "x_m", "y_m", "vx_mps", "vy_mps")
"""Column order of truth.csv. Fixed by docs/conventions.md; do not reorder."""

FLOAT_PRECISION = 6
"""Decimal places for every floating-point field.

Fixed-width formatting is what makes SYS-003 mechanically checkable: two runs of the
same configuration either produce byte-identical files or they do not. Variable-width
repr formatting would let insignificant final-digit differences masquerade as
non-determinism, and would hide real drift behind noise.
"""


def write_truth_csv(path: Path | str, states: Iterable[WorldState]) -> int:
    """Write ground-truth states to CSV, creating parent directories as needed.

    Rows are emitted in simulation-time order, and within a timestep in ascending
    target-id order, so that the file is deterministic regardless of the order the
    simulator happens to hold targets in.

    Args:
        path: Destination file.
        states: World states, in ascending time order.

    Returns:
        The number of data rows written, excluding the header.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fmt = f"{{:.{FLOAT_PRECISION}f}}"
    rows_written = 0

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(TRUTH_COLUMNS)

        for state in states:
            for target in sorted(state.targets, key=lambda t: t.target_id):
                writer.writerow(
                    [
                        fmt.format(state.t_s),
                        target.target_id,
                        fmt.format(target.x_m),
                        fmt.format(target.y_m),
                        fmt.format(target.vx_mps),
                        fmt.format(target.vy_mps),
                    ]
                )
                rows_written += 1

    return rows_written
