"""Tests for the World simulation loop.

Verifies SYS-002 (at least 10 simultaneous targets) and the timing behaviour that
SYS-003 (bit-identical reruns) depends on.
"""

import pytest

from mstt.sim.target import Target
from mstt.sim.world import World


def make_world(n_targets=1, dt_s=0.1, duration_s=1.0):
    targets = [
        Target.from_position_velocity(i, (0.0, float(i)), (8.0, 4.0))
        for i in range(1, n_targets + 1)
    ]
    return World(targets=targets, dt_s=dt_s, duration_s=duration_s)


def test_step_count_includes_initial_state():
    """A 60 s run at a 0.1 s timestep emits 601 states: t=0.0 through t=60.0."""
    assert make_world(duration_s=60.0, dt_s=0.1).step_count == 601


def test_first_state_is_the_initial_condition_at_t_zero():
    first = next(make_world().run())

    assert first.t_s == 0.0
    assert first.targets[0].x_m == pytest.approx(0.0)
    assert first.targets[0].vx_mps == pytest.approx(8.0)


def test_timestamps_are_exact_multiples_of_the_timestep():
    """Time must be computed as index * dt, never accumulated.

    Repeatedly adding 0.1 accumulates rounding error, because 0.1 has no exact
    binary representation. Over a long run that drift is large enough to perturb
    the 6-decimal output format and break SYS-003. Multiplying introduces a single
    rounding instead of one per step, so this comparison is exact.
    """
    world = make_world(duration_s=60.0, dt_s=0.1)

    for index, state in enumerate(world.run()):
        assert state.t_s == index * world.dt_s


def test_accumulated_time_would_have_drifted():
    """Documents the failure mode the previous test guards against.

    Not a test of our code, but of the reason for its design: after 600 additions
    the naive approach differs from the exact value by enough to matter.
    """
    naive = 0.0
    for _ in range(600):
        naive += 0.1

    assert naive != 600 * 0.1, "if this ever passes, the rationale above needs revisiting"
    assert abs(naive - 60.0) > 1e-13


def test_position_after_n_steps_matches_hand_computation():
    """After 10 steps of 0.1 s at 8 m/s East, the target has moved 8 m East."""
    states = list(make_world(dt_s=0.1, duration_s=1.0).run())

    final = states[10].targets[0]
    assert states[10].t_s == pytest.approx(1.0)
    assert final.x_m == pytest.approx(8.0, abs=1e-9)
    assert final.y_m == pytest.approx(1.0 + 4.0, abs=1e-9)


def test_supports_at_least_ten_simultaneous_targets():
    """Verifies SYS-002."""
    world = make_world(n_targets=10, duration_s=1.0)
    states = list(world.run())

    assert all(len(state.targets) == 10 for state in states)
    assert {t.target_id for t in states[-1].targets} == set(range(1, 11))

    # Every target advanced independently and kept its own initial offset in y.
    for target in states[-1].targets:
        assert target.x_m == pytest.approx(8.0, abs=1e-9)
        assert target.y_m == pytest.approx(target.target_id + 4.0, abs=1e-9)


def test_run_is_repeatable():
    """The same World yields identical states on every iteration."""
    world = make_world(n_targets=3, duration_s=2.0)

    first = [(s.t_s, tuple(t.state.tolist() for t in s.targets)) for s in world.run()]
    second = [(s.t_s, tuple(t.state.tolist() for t in s.targets)) for s in world.run()]

    assert first == second


def test_empty_target_list_rejected():
    with pytest.raises(ValueError, match="at least one target"):
        World(targets=[], dt_s=0.1, duration_s=1.0)


def test_duplicate_target_ids_rejected():
    """Duplicate IDs would make ground truth ambiguous during evaluation."""
    targets = [
        Target.from_position_velocity(1, (0.0, 0.0), (1.0, 0.0)),
        Target.from_position_velocity(1, (5.0, 5.0), (0.0, 1.0)),
    ]
    with pytest.raises(ValueError, match="duplicate target ids"):
        World(targets=targets, dt_s=0.1, duration_s=1.0)


@pytest.mark.parametrize("bad_dt", [0.0, -0.1])
def test_non_positive_timestep_rejected(bad_dt):
    with pytest.raises(ValueError, match="strictly positive"):
        make_world(dt_s=bad_dt)


def test_negative_duration_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        make_world(duration_s=-1.0)
