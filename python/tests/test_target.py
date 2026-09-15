"""Tests for the ground-truth Target representation."""

import math

import numpy as np
import pytest

from mstt.sim.motion import constant_velocity_transition
from mstt.sim.target import Target


def test_from_position_velocity_populates_state_in_convention_order():
    """State element order is fixed by docs/conventions.md: x, y, vx, vy."""
    target = Target.from_position_velocity(7, position_m=(100.0, 200.0), velocity_mps=(8.0, 4.0))

    np.testing.assert_array_equal(target.state, [100.0, 200.0, 8.0, 4.0])
    assert target.target_id == 7
    assert (target.x_m, target.y_m) == (100.0, 200.0)
    assert (target.vx_mps, target.vy_mps) == (8.0, 4.0)


def test_speed_and_heading_match_the_worked_example():
    """A 3-4-5 triangle gives speed 5; heading follows the convention in section 2.

    Heading is measured counter-clockwise from East, so a target moving (3, 4)
    heads at atan2(4, 3) = 53.13 degrees. Compass convention would give 36.87,
    and a value of 36.87 here would indicate a convention bug.
    """
    target = Target.from_position_velocity(1, (0.0, 0.0), (3.0, 4.0))

    assert target.speed_mps == pytest.approx(5.0)
    assert math.degrees(target.heading_rad) == pytest.approx(53.130102, abs=1e-6)


def test_heading_of_stationary_target_is_defined():
    """A stationary target is legitimate and must not raise."""
    assert Target.from_position_velocity(1, (5.0, 5.0), (0.0, 0.0)).heading_rad == 0.0


def test_advanced_returns_a_new_target_and_preserves_id():
    target = Target.from_position_velocity(3, (0.0, 0.0), (10.0, 0.0))

    moved = target.advanced(constant_velocity_transition(2.0))

    assert moved.target_id == 3
    assert moved.x_m == pytest.approx(20.0)
    assert target.x_m == pytest.approx(0.0), "the original target must be unchanged"
    assert moved is not target


def test_malformed_state_rejected_at_construction():
    with pytest.raises(ValueError, match="shape"):
        Target(target_id=1, state=np.zeros(3))
