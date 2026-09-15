"""Tests for scenario configuration loading and validation.

Verifies SYS-001 (scenarios defined by external configuration).
"""

from pathlib import Path

import pytest

from mstt.sim.scenario import Scenario, ScenarioError

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_A = REPO_ROOT / "config" / "scenarios" / "A_single_cv.yaml"


def valid_mapping(**overrides):
    base = {
        "name": "unit_test",
        "description": "fixture",
        "simulation": {"duration_s": 10.0, "timestep_s": 0.1},
        "targets": [{"id": 1, "position_m": [0.0, 0.0], "velocity_mps": [8.0, 4.0]}],
    }
    base.update(overrides)
    return base


def test_shipped_scenario_a_loads():
    """The scenario file committed to the repository must be valid."""
    scenario = Scenario.from_yaml(SCENARIO_A)

    assert scenario.name == "A_single_cv"
    assert scenario.simulation.duration_s == 10.0 * 6
    assert scenario.simulation.timestep_s == 0.1
    assert len(scenario.targets) == 1
    assert scenario.targets[0].target_id == 1
    assert scenario.targets[0].vx_mps == 8.0


def test_scenario_a_reaches_the_expected_endpoint():
    """Ground truth for Scenario A ends at (480, 240), as its header comment states.

    A target starting at the origin at (8, 4) m/s for 60 s travels 480 m East and
    240 m North. This guards the documentation against silently going stale.
    """
    world = Scenario.from_yaml(SCENARIO_A).build_world()
    final = list(world.run())[-1]

    assert final.t_s == pytest.approx(60.0)
    assert final.targets[0].x_m == pytest.approx(480.0, abs=1e-6)
    assert final.targets[0].y_m == pytest.approx(240.0, abs=1e-6)


def test_build_world_uses_configured_timing():
    scenario = Scenario.from_mapping(valid_mapping())
    world = scenario.build_world()

    assert world.dt_s == 0.1
    assert world.duration_s == 10.0
    assert world.step_count == 101


def test_unknown_top_level_key_rejected():
    """Unknown keys are errors, not warnings, so typos cannot silently take defaults."""
    with pytest.raises(ScenarioError, match="unknown key"):
        Scenario.from_mapping(valid_mapping(durations=5))


def test_mistyped_target_key_rejected():
    """The motivating case: 'velocty_mps' must fail loudly, not yield a still target."""
    bad = valid_mapping(targets=[{"id": 1, "position_m": [0.0, 0.0], "velocty_mps": [8.0, 4.0]}])
    with pytest.raises(ScenarioError, match="velocty_mps"):
        Scenario.from_mapping(bad)


@pytest.mark.parametrize("missing", ["name", "simulation", "targets"])
def test_missing_required_key_rejected(missing):
    mapping = valid_mapping()
    del mapping[missing]
    with pytest.raises(ScenarioError, match="missing required key"):
        Scenario.from_mapping(mapping)


@pytest.mark.parametrize("bad_timestep", [0.0, -0.1])
def test_non_positive_timestep_rejected(bad_timestep):
    bad = valid_mapping(simulation={"duration_s": 10.0, "timestep_s": bad_timestep})
    with pytest.raises(ScenarioError, match="timestep_s must be strictly positive"):
        Scenario.from_mapping(bad)


def test_negative_duration_rejected():
    bad = valid_mapping(simulation={"duration_s": -1.0, "timestep_s": 0.1})
    with pytest.raises(ScenarioError, match="duration_s must be non-negative"):
        Scenario.from_mapping(bad)


def test_empty_target_list_rejected():
    with pytest.raises(ScenarioError, match="non-empty list"):
        Scenario.from_mapping(valid_mapping(targets=[]))


@pytest.mark.parametrize(
    "bad_position",
    [[0.0], [0.0, 1.0, 2.0], "0,0", [None, 1.0], [True, 1.0]],
)
def test_malformed_position_rejected(bad_position):
    """Including bool, which Python would otherwise silently accept as a number."""
    bad = valid_mapping(targets=[{"id": 1, "position_m": bad_position, "velocity_mps": [1.0, 1.0]}])
    with pytest.raises(ScenarioError):
        Scenario.from_mapping(bad)


def test_non_integer_target_id_rejected():
    bad = valid_mapping(
        targets=[{"id": "one", "position_m": [0.0, 0.0], "velocity_mps": [1.0, 1.0]}]
    )
    with pytest.raises(ScenarioError, match="'id' must be an integer"):
        Scenario.from_mapping(bad)


def test_missing_file_reports_cleanly(tmp_path):
    """A missing file is a user error and must not surface as a bare OSError."""
    with pytest.raises(ScenarioError, match="not found"):
        Scenario.from_yaml(tmp_path / "does_not_exist.yaml")


def test_invalid_yaml_reports_cleanly(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("name: [unclosed\n")
    with pytest.raises(ScenarioError, match="invalid YAML"):
        Scenario.from_yaml(path)


def test_scenario_c_has_ten_targets():
    """Verifies SYS-002 at the configuration level."""
    scenario = Scenario.from_yaml(REPO_ROOT / "config" / "scenarios" / "C_multi_target.yaml")

    assert len(scenario.targets) == 10
    assert {t.target_id for t in scenario.targets} == set(range(1, 11))


def test_scenario_d_targets_actually_cross():
    """The crossing scenario is worthless unless the paths genuinely coincide.

    Both targets must occupy the same point at t = 20 s. Asserting it here means a
    later edit to the scenario cannot silently remove the crossing that V0.5's
    data-association tests depend on.
    """
    world = Scenario.from_yaml(REPO_ROOT / "config" / "scenarios" / "D_crossing.yaml").build_world()
    states = list(world.run())

    at_crossing = next(s for s in states if abs(s.t_s - 20.0) < 1e-9)
    first, second = sorted(at_crossing.targets, key=lambda t: t.target_id)

    assert first.x_m == pytest.approx(second.x_m, abs=1e-6)
    assert first.y_m == pytest.approx(second.y_m, abs=1e-6)
    assert (first.x_m, first.y_m) == pytest.approx((0.0, 300.0), abs=1e-6)

    # Away from the crossing they must be well separated, or the scenario is not
    # testing a crossing so much as two targets flying in formation.
    start = states[0].targets
    assert abs(start[0].x_m - start[1].x_m) > 100.0
