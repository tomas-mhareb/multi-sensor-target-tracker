"""Verify the committed golden vectors still match the Python implementation.

This is one half of the cross-language contract in ADR-008. The C++ tests assert that
the C++ implementation matches these vectors; this asserts that the Python
implementation still does. Both halves give `golden == Python` and `C++ == golden`,
and therefore `C++ == Python`.

Checking only the C++ half leaves a hole: change geometry.py without regenerating, and
the C++ test still passes because C++ still matches the old file, while Python now
disagrees with both.

Comparison is numerical with a tolerance, not byte equality. An earlier version of this
check compared the regenerated file byte for byte and failed in CI: numpy's hypot
differs by one unit in the last place between Apple's libm and glibc, so
561.30624241630869 on macOS is 561.30624241630858 on Linux. IEEE-754 does not require
bit-identical results for transcendental functions across implementations, and a check
that demands them tests the C library rather than this project. The tolerance below is
ten orders of magnitude larger than a ULP difference and ten orders smaller than any
convention error, which is the distinction that matters.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from mstt.sensors.geometry import cartesian_to_polar, wrap_angle

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = REPO_ROOT / "tests" / "data" / "golden" / "geometry.csv"

TOLERANCE = 1e-12
"""Matches kCrossLanguageTolerance in tests/unit/test_frames.cpp.

The two must agree: a tolerance tighter here than in C++ would fail on differences the
C++ side accepts, and looser would let a real divergence through on one side only.
"""


def load_rows() -> list[dict[str, str]]:
    assert GOLDEN.is_file(), f"golden vectors missing at {GOLDEN}"
    with GOLDEN.open() as handle:
        return list(csv.DictReader(handle))


def test_golden_file_is_present_and_substantial():
    """A truncated or empty file would make every check below vacuously pass."""
    rows = load_rows()

    assert len(rows) > 100
    assert {r["case"] for r in rows} == {"to_polar", "wrap_angle"}


def test_to_polar_vectors_match_the_current_implementation():
    checked = 0
    for row in load_rows():
        if row["case"] != "to_polar":
            continue

        x_m, y_m = float(row["in_a"]), float(row["in_b"])
        expected_range, expected_bearing = float(row["out_a"]), float(row["out_b"])
        range_m, bearing_rad = cartesian_to_polar(x_m, y_m)

        assert float(range_m) == pytest.approx(expected_range, rel=TOLERANCE, abs=TOLERANCE), (
            f"range at ({x_m}, {y_m})"
        )
        assert float(bearing_rad) == pytest.approx(expected_bearing, abs=TOLERANCE), (
            f"bearing at ({x_m}, {y_m})"
        )
        checked += 1

    assert checked > 100


def test_wrap_angle_vectors_match_the_current_implementation():
    checked = 0
    for row in load_rows():
        if row["case"] != "wrap_angle":
            continue

        angle_rad = float(row["in_a"])
        assert float(wrap_angle(angle_rad)) == pytest.approx(float(row["out_a"]), abs=TOLERANCE), (
            f"wrap of {angle_rad}"
        )
        checked += 1

    assert checked > 50


def test_golden_vectors_include_the_quadrants_arctan_gets_wrong():
    """The file is only useful if it covers the cases that would expose a bug.

    A golden set of first-quadrant points would agree between any two
    implementations, correct or not.
    """
    points = {(float(r["in_a"]), float(r["in_b"])) for r in load_rows() if r["case"] == "to_polar"}

    assert (-1.0, 0.0) in points, "due West: arctan(y/x) reports this as due East"
    assert (0.0, -1.0) in points, "due South: arctan(y/x) divides by zero"
    assert (-1.0, -1.0) in points, "South-West: arctan(y/x) reports +45 instead of -135"


def test_golden_wrap_angles_span_the_discontinuity():
    angles = [float(r["in_a"]) for r in load_rows() if r["case"] == "wrap_angle"]

    assert any(math.isclose(a, math.pi) for a in angles)
    assert any(math.isclose(a, -math.pi) for a in angles)
    assert max(angles) > 2 * math.pi, "must include angles beyond one revolution"
