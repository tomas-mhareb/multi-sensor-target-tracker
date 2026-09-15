"""Tests for Cartesian/polar conversion and angle wrapping.

These guard Risk 1 from the project risk list: frame and unit convention errors,
which do not crash but produce confidently mirrored results.
"""

import math

import numpy as np
import pytest

from mstt.sensors.geometry import (
    angular_difference,
    cartesian_to_polar,
    cross_range_error_m,
    polar_to_cartesian,
    wrap_angle,
)


def test_matches_the_worked_example_in_conventions():
    """docs/conventions.md section 7 fixes this case. The doc and code must agree.

    A value of 26.57 degrees here would mean compass bearing had crept in, which is
    exactly the silent convention bug the conventions document exists to prevent.
    """
    range_m, bearing_rad = cartesian_to_polar(100.0, 200.0)

    assert range_m == pytest.approx(223.6068, abs=1e-4)
    assert math.degrees(bearing_rad) == pytest.approx(63.4349, abs=1e-4)


@pytest.mark.parametrize(
    ("x_m", "y_m", "expected_deg", "label"),
    [
        (100.0, 0.0, 0.0, "East"),
        (0.0, 100.0, 90.0, "North"),
        (-100.0, 0.0, 180.0, "West"),
        (0.0, -100.0, -90.0, "South"),
        (100.0, 100.0, 45.0, "North-East"),
        (-100.0, -100.0, -135.0, "South-West"),
    ],
)
def test_bearing_covers_all_four_quadrants(x_m, y_m, expected_deg, label):
    """arctan(y/x) fails three of these; arctan2 must handle all of them."""
    _, bearing_rad = cartesian_to_polar(x_m, y_m)

    assert math.degrees(bearing_rad) == pytest.approx(expected_deg, abs=1e-9), label


def test_round_trip_is_identity_over_the_whole_plane():
    """Cartesian to polar and back must return the original point.

    Seeded so a failure is reproducible rather than an intermittent mystery.
    """
    rng = np.random.default_rng(20260915)
    points = rng.uniform(-5000.0, 5000.0, size=(2000, 2))

    range_m, bearing_rad = cartesian_to_polar(points[:, 0], points[:, 1])
    x_back, y_back = polar_to_cartesian(range_m, bearing_rad)

    np.testing.assert_allclose(x_back, points[:, 0], rtol=0, atol=1e-9)
    np.testing.assert_allclose(y_back, points[:, 1], rtol=0, atol=1e-9)


def test_round_trip_at_the_origin():
    """Zero range is degenerate but must not raise; bearing is arbitrary there."""
    range_m, _ = cartesian_to_polar(0.0, 0.0)
    assert range_m == 0.0


def test_negative_range_rejected():
    """A negative range would silently mirror the target to the opposite bearing."""
    with pytest.raises(ValueError, match="non-negative"):
        polar_to_cartesian(-10.0, 0.0)


@pytest.mark.parametrize(
    ("input_deg", "expected_deg"),
    [
        (0.0, 0.0),
        (90.0, 90.0),
        (180.0, 180.0),
        (181.0, -179.0),
        (360.0, 0.0),
        (450.0, 90.0),
        (-450.0, -90.0),
        (720.0 + 45.0, 45.0),
    ],
)
def test_wrap_angle_removes_whole_revolutions(input_deg, expected_deg):
    result_deg = math.degrees(wrap_angle(math.radians(input_deg)))

    assert result_deg == pytest.approx(expected_deg, abs=1e-9)


def test_wrap_angle_result_always_within_pi():
    rng = np.random.default_rng(7)
    angles = rng.uniform(-50.0, 50.0, size=5000)

    wrapped = wrap_angle(angles)

    assert np.all(wrapped >= -math.pi - 1e-12)
    assert np.all(wrapped <= math.pi + 1e-12)


def test_angular_difference_across_the_discontinuity():
    """The Kalman innovation case, and the reason wrapping is not optional.

    Two bearings four degrees apart that straddle the +/-180 boundary must differ by
    four degrees. Subtracting naively gives 356, which fed to a filter as an error
    would destroy the track in one update.
    """
    a = math.radians(178.0)
    b = math.radians(-178.0)

    naive_deg = math.degrees(a - b)
    wrapped_deg = math.degrees(angular_difference(a, b))

    assert naive_deg == pytest.approx(356.0, abs=1e-9), "documents the failure mode"
    assert wrapped_deg == pytest.approx(-4.0, abs=1e-9)
    assert abs(wrapped_deg) <= 180.0


def test_angular_difference_is_antisymmetric():
    rng = np.random.default_rng(11)
    a, b = rng.uniform(-math.pi, math.pi, size=(2, 500))

    forward = angular_difference(a, b)
    backward = angular_difference(b, a)

    # Exactly +/-pi is its own negation under wrapping, so compare magnitudes there.
    np.testing.assert_allclose(np.abs(forward), np.abs(backward), atol=1e-12)


def test_cross_range_error_grows_linearly_with_range():
    """The wedge: a fixed angular error subtends more metres further out."""
    sigma_rad = math.radians(1.0)

    assert cross_range_error_m(100.0, sigma_rad) == pytest.approx(1.7453, abs=1e-4)
    assert cross_range_error_m(1000.0, sigma_rad) == pytest.approx(17.4533, abs=1e-4)
    assert cross_range_error_m(2000.0, sigma_rad) == pytest.approx(
        2.0 * cross_range_error_m(1000.0, sigma_rad)
    )


def test_cross_range_error_exceeds_range_error_at_long_range():
    """Justifies ADR-003: the camera repairs the axis the radar is worst at."""
    range_noise_m, bearing_sigma_rad = 2.0, math.radians(1.0)

    assert cross_range_error_m(100.0, bearing_sigma_rad) < range_noise_m
    assert cross_range_error_m(5000.0, bearing_sigma_rad) > 40.0 * range_noise_m


def test_functions_accept_arrays():
    """Vectorized use by the analysis tooling must give the same answers."""
    xs = np.array([100.0, 0.0, -100.0])
    ys = np.array([0.0, 100.0, 0.0])

    range_m, bearing_rad = cartesian_to_polar(xs, ys)

    np.testing.assert_allclose(range_m, [100.0, 100.0, 100.0])
    np.testing.assert_allclose(np.degrees(bearing_rad), [0.0, 90.0, 180.0])
