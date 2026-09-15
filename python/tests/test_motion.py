"""Tests for the constant-velocity motion model."""

import numpy as np
import pytest

from mstt.sim.motion import (
    IDX_VX,
    IDX_VY,
    IDX_X,
    IDX_Y,
    STATE_DIM,
    constant_velocity_transition,
    propagate,
)


def test_transition_matrix_structure():
    """F is the identity plus exactly two dt terms coupling position to velocity."""
    dt_s = 0.25
    transition = constant_velocity_transition(dt_s)

    expected = np.array(
        [
            [1.0, 0.0, dt_s, 0.0],
            [0.0, 1.0, 0.0, dt_s],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    np.testing.assert_array_equal(transition, expected)


def test_propagate_matches_hand_computed_position():
    """One step of a known state gives the position we can work out on paper.

    Starting at (10, 20) moving at (3, -4) m/s for 0.5 s:
        x = 10 + 3 * 0.5  = 11.5
        y = 20 + -4 * 0.5 = 18.0
    Velocity is unchanged, which is the defining property of the model.
    """
    state = np.array([10.0, 20.0, 3.0, -4.0])
    result = propagate(state, constant_velocity_transition(0.5))

    np.testing.assert_allclose(result, [11.5, 18.0, 3.0, -4.0], rtol=0, atol=1e-12)


def test_velocity_is_invariant_over_many_steps():
    """Velocity must not drift, however many times F is applied."""
    transition = constant_velocity_transition(0.1)
    state = np.array([0.0, 0.0, 8.0, 4.0])

    for _ in range(1000):
        state = propagate(state, transition)

    assert state[IDX_VX] == pytest.approx(8.0, abs=1e-12)
    assert state[IDX_VY] == pytest.approx(4.0, abs=1e-12)


def test_repeated_application_equals_single_step_of_total_time():
    """N steps of dt must agree with one step of N*dt, since the model is linear.

    This is a useful self-consistency property: it holds only if F is built
    correctly, and it catches sign or transpose errors that a single step might not.
    """
    n_steps, dt_s = 20, 0.05
    start = np.array([-5.0, 12.0, 2.5, 7.5])

    stepwise = start.copy()
    small_step = constant_velocity_transition(dt_s)
    for _ in range(n_steps):
        stepwise = propagate(stepwise, small_step)

    one_shot = propagate(start, constant_velocity_transition(n_steps * dt_s))

    np.testing.assert_allclose(stepwise, one_shot, rtol=0, atol=1e-9)


@pytest.mark.parametrize("bad_dt", [0.0, -0.1, -1.0])
def test_non_positive_timestep_rejected(bad_dt):
    """A zero or negative timestep is a malformed scenario, not an edge case."""
    with pytest.raises(ValueError, match="strictly positive"):
        constant_velocity_transition(bad_dt)


def test_propagate_rejects_wrong_state_shape():
    with pytest.raises(ValueError, match=f"shape \\({STATE_DIM},\\)"):
        propagate(np.zeros(3), constant_velocity_transition(0.1))


def test_propagate_does_not_mutate_input():
    """Returning a new array prevents state aliasing across targets or timesteps."""
    state = np.array([1.0, 2.0, 3.0, 4.0])
    original = state.copy()

    propagate(state, constant_velocity_transition(0.1))

    np.testing.assert_array_equal(state, original)
    assert IDX_X == 0 and IDX_Y == 1 and IDX_VX == 2 and IDX_VY == 3
