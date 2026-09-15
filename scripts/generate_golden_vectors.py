#!/usr/bin/env python3
"""Generate golden vectors that pin the C++ implementation to the Python one.

The simulator produces measurements in Python and the tracker consumes them in C++.
Both must agree exactly on what a bearing means. A convention mismatch between the two
would not crash -- it would produce mirrored tracks and plausible-looking output.

This script writes reference values computed by the Python implementation, which the
C++ unit tests then assert against. It is the same technique used to verify
hand-written flight code against a model: one implementation is the reference, the
other is checked against it, and the check runs on every build.

Values are written at full double precision so that a comparison at 1e-12 is
meaningful rather than limited by the file format.

Regenerate with:
    python scripts/generate_golden_vectors.py

Regenerating is a deliberate act. If a change to the Python implementation makes this
file differ, the C++ tests will fail, and that failure is the point: it means the two
implementations have diverged and one of them is wrong.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from mstt.sensors.geometry import cartesian_to_polar, wrap_angle

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "tests" / "data" / "golden" / "geometry.csv"

FULL_PRECISION = "{:.17g}"
"""17 significant digits round-trips an IEEE-754 double exactly."""


def build_points() -> list[tuple[float, float]]:
    """Hand-picked edge cases first, then a seeded random spread."""
    special: list[tuple[float, float]] = [
        (0.0, 0.0),  # degenerate: bearing undefined at zero range
        (1.0, 0.0),  # East
        (0.0, 1.0),  # North
        (-1.0, 0.0),  # West: the case arctan(y/x) gets wrong
        (0.0, -1.0),  # South: the case arctan(y/x) divides by zero
        (1.0, 1.0),
        (-1.0, -1.0),  # South-West: arctan reports +45 instead of -135
        (-1.0, 1.0),
        (1.0, -1.0),
        (100.0, 200.0),  # the worked example in docs/conventions.md
        (-400.0, 200.0),  # scenario B start
        (1e-9, 1e-9),  # near the origin, where bearing is ill-conditioned
        (1e6, -1e6),  # far field, where float cancellation would show
    ]

    rng = np.random.default_rng(20260915)
    random_points = rng.uniform(-5000.0, 5000.0, size=(200, 2))
    return special + [(float(x), float(y)) for x, y in random_points]


def build_angles() -> list[float]:
    """Angles spanning several revolutions, including the wrap boundaries exactly."""
    boundaries = [0.0, np.pi, -np.pi, np.pi / 2, -np.pi / 2, 2 * np.pi, -2 * np.pi]
    rng = np.random.default_rng(7)
    return boundaries + [float(a) for a in rng.uniform(-20.0, 20.0, size=100)]


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("case", "in_a", "in_b", "out_a", "out_b"))

        for x_m, y_m in build_points():
            range_m, bearing_rad = cartesian_to_polar(x_m, y_m)
            writer.writerow(
                [
                    "to_polar",
                    FULL_PRECISION.format(x_m),
                    FULL_PRECISION.format(y_m),
                    FULL_PRECISION.format(float(range_m)),
                    FULL_PRECISION.format(float(bearing_rad)),
                ]
            )

        for angle_rad in build_angles():
            writer.writerow(
                [
                    "wrap_angle",
                    FULL_PRECISION.format(angle_rad),
                    "0",
                    FULL_PRECISION.format(float(wrap_angle(angle_rad))),
                    "0",
                ]
            )

    rows = sum(1 for _ in OUTPUT.open()) - 1
    print(f"wrote {rows} golden vectors to {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
