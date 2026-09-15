"""End-to-end tests for scenario execution and run artifacts.

Verifies SYS-004 at system level and confirms SYS-003 still holds now that the
pipeline contains randomness.
"""

import csv
import json
from pathlib import Path

import pytest

from mstt.io.measurement_jsonl import FALSE_ALARM_TARGET_ID, read_measurements_jsonl
from mstt.sim.generate import generate_run
from mstt.sim.scenario import Scenario

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "config" / "scenarios"


def load(name: str) -> Scenario:
    return Scenario.from_yaml(SCENARIOS / f"{name}.yaml")


def test_run_writes_the_documented_artifacts(tmp_path):
    generate_run(load("B_single_noisy"), tmp_path)

    for filename in ("truth.csv", "measurements.jsonl", "measurement_truth.csv"):
        assert (tmp_path / filename).is_file(), filename


def test_truth_only_scenario_writes_no_measurement_files(tmp_path):
    """Scenario A has no sensors, so it must not leave empty measurement files."""
    summary = generate_run(load("A_single_cv"), tmp_path)

    assert (tmp_path / "truth.csv").is_file()
    assert not (tmp_path / "measurements.jsonl").exists()
    assert summary.measurements == 0
    assert summary.scans == 0


def test_measurements_are_in_ascending_time_order(tmp_path):
    generate_run(load("B_single_noisy"), tmp_path)

    times = [m.t_s for m in read_measurements_jsonl(tmp_path / "measurements.jsonl")]

    assert times == sorted(times)


def test_measurement_ids_are_unique_and_join_to_the_evaluation_key(tmp_path):
    generate_run(load("B_single_noisy"), tmp_path)

    ids = [m.meas_id for m in read_measurements_jsonl(tmp_path / "measurements.jsonl")]
    with (tmp_path / "measurement_truth.csv").open() as handle:
        key = {int(r["meas_id"]): int(r["target_id"]) for r in csv.DictReader(handle)}

    assert len(ids) == len(set(ids)), "measurement ids must be unique"
    assert set(ids) == set(key), "every measurement must appear in the evaluation key"


def test_measurement_stream_contains_no_ground_truth(tmp_path):
    """The tracker's input must not reveal which target produced a measurement.

    Guarded by a test because the consequence of a leak is silent: a tracker able to
    read the answer would score perfectly on data association while implementing
    none, and the resulting metrics would be meaningless.
    """
    generate_run(load("B_single_noisy"), tmp_path)

    raw = (tmp_path / "measurements.jsonl").read_text()
    first = json.loads(raw.splitlines()[0])

    assert set(first) == {
        "meas_id",
        "t_s",
        "sensor_id",
        "sensor_type",
        "frame",
        "values",
        "covariance",
    }
    for forbidden in ("target_id", "truth", "true_range_m", "is_false_alarm"):
        assert forbidden not in raw, f"{forbidden!r} leaked into the measurement stream"


def test_run_is_bit_identical_for_the_same_seed(tmp_path):
    """Verifies SYS-003 with randomness in the loop."""
    a, b = tmp_path / "a", tmp_path / "b"
    generate_run(load("B_single_noisy"), a)
    generate_run(load("B_single_noisy"), b)

    for filename in ("truth.csv", "measurements.jsonl", "measurement_truth.csv"):
        assert (a / filename).read_bytes() == (b / filename).read_bytes(), filename


def test_changing_the_seed_changes_the_measurements_but_not_the_truth(tmp_path):
    """Ground truth is deterministic physics; only the sensor is stochastic."""
    scenario = load("B_single_noisy")
    reseeded = Scenario(
        name=scenario.name,
        description=scenario.description,
        simulation=scenario.simulation,
        targets=scenario.targets,
        sensors=scenario.sensors,
        seed=scenario.seed + 1,
    )
    a, b = tmp_path / "a", tmp_path / "b"
    generate_run(scenario, a)
    generate_run(reseeded, b)

    assert (a / "truth.csv").read_bytes() == (b / "truth.csv").read_bytes()
    assert (a / "measurements.jsonl").read_bytes() != (b / "measurements.jsonl").read_bytes()


def test_scenario_e_detection_rate_is_consistent_with_its_configuration(tmp_path):
    """Detection is binomial; allow four standard errors so the test cannot flake.

    With n = 601 opportunities at p = 0.60 the standard error is about 0.020, so a
    four-sigma band is +/- 0.08 -- wide enough to be stable across seeds, narrow
    enough to catch a sensor that ignores its configured probability.
    """
    summary = generate_run(load("E_missed_detections"), tmp_path)

    assert summary.detection_rate == pytest.approx(0.60, abs=0.08)
    assert summary.false_alarms == 0, "scenario E disables false alarms"


def test_scenario_f_is_dominated_by_false_alarms(tmp_path):
    summary = generate_run(load("F_false_alarms"), tmp_path)

    assert summary.detection_rate == 1.0, "scenario F pins detection at certainty"
    assert summary.missed_detections == 0
    assert summary.false_alarms > 3 * summary.detections


def test_false_alarms_are_labelled_in_the_evaluation_key(tmp_path):
    generate_run(load("F_false_alarms"), tmp_path)

    with (tmp_path / "measurement_truth.csv").open() as handle:
        labels = [int(r["target_id"]) for r in csv.DictReader(handle)]

    assert FALSE_ALARM_TARGET_ID in labels
    assert set(labels) <= {FALSE_ALARM_TARGET_ID, 1}


def test_summary_json_is_written_with_the_derived_rate(tmp_path):
    from mstt.sim.generate import summary_as_dict

    summary = generate_run(load("B_single_noisy"), tmp_path)
    data = summary_as_dict(summary)

    assert data["detection_rate"] == pytest.approx(summary.detection_rate)
    assert data["seed"] == 20260915
    assert data["measurements"] == summary.detections + summary.false_alarms


def test_slower_sensor_scans_less_often(tmp_path):
    """A 10 Hz simulation with a 5 Hz radar must scan on every other step."""
    scenario = load("B_single_noisy")
    slower = Scenario(
        name=scenario.name,
        description=scenario.description,
        simulation=scenario.simulation,
        targets=scenario.targets,
        sensors=(
            type(scenario.sensors[0])(**{**scenario.sensors[0].__dict__, "update_rate_hz": 5.0}),
        ),
        seed=scenario.seed,
    )

    fast = generate_run(scenario, tmp_path / "fast")
    slow = generate_run(slower, tmp_path / "slow")

    assert fast.scans == 601
    assert slow.scans == 301
