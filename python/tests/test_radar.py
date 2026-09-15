"""Tests for the simulated radar sensor.

Statistical assertions use a fixed seed and bounds derived from the standard error
of the estimate, several times wider than the expected spread. A test that fails
occasionally teaches you to ignore CI, which defeats the purpose of having it.
"""

import math

import numpy as np
import pytest

from mstt.sensors.radar import FALSE_ALARM_TARGET_ID, RadarConfig, RadarSensor
from mstt.sim.target import Target
from mstt.sim.world import WorldState


def make_config(**overrides) -> RadarConfig:
    params = {
        "sensor_id": "radar_0",
        "position_m": (0.0, 0.0),
        "update_rate_hz": 10.0,
        "range_noise_m": 2.0,
        "bearing_noise_deg": 1.0,
        "detection_probability": 0.95,
        "false_alarm_rate_per_scan": 0.5,
        "max_range_m": 5000.0,
    }
    params.update(overrides)
    return RadarConfig(**params)


def make_state(t_s=0.0, positions=((100.0, 0.0),)) -> WorldState:
    targets = tuple(
        Target.from_position_velocity(i, pos, (0.0, 0.0))
        for i, pos in enumerate(positions, start=1)
    )
    return WorldState(t_s=t_s, targets=targets)


def make_sensor(seed=12345, **overrides) -> RadarSensor:
    return RadarSensor(make_config(**overrides), np.random.default_rng(seed))


# --------------------------------------------------------------------------- config


def test_covariance_is_diagonal_variance_in_measurement_units():
    """R holds variances, not standard deviations, in (range, bearing) order."""
    cov = make_config(range_noise_m=2.0, bearing_noise_deg=1.0).covariance

    assert cov.shape == (2, 2)
    assert cov[0, 0] == pytest.approx(4.0)
    assert cov[1, 1] == pytest.approx(math.radians(1.0) ** 2)
    assert cov[0, 1] == 0.0 and cov[1, 0] == 0.0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("update_rate_hz", 0.0, "update_rate_hz"),
        ("range_noise_m", -1.0, "range_noise_m"),
        ("bearing_noise_deg", -1.0, "bearing_noise_deg"),
        ("detection_probability", 1.5, "detection_probability"),
        ("detection_probability", -0.1, "detection_probability"),
        ("false_alarm_rate_per_scan", -1.0, "false_alarm_rate_per_scan"),
        ("max_range_m", 0.0, "max_range_m"),
    ],
)
def test_invalid_configuration_rejected(field, value, message):
    with pytest.raises(ValueError, match=message):
        make_config(**{field: value})


# --------------------------------------------------------------------------- timing


@pytest.mark.parametrize(
    ("rate_hz", "dt_s", "expected_steps"),
    [(10.0, 0.1, 1), (5.0, 0.1, 2), (1.0, 0.1, 10), (2.0, 0.05, 10)],
)
def test_scan_interval_for_compatible_rates(rate_hz, dt_s, expected_steps):
    assert make_sensor(update_rate_hz=rate_hz).scan_step_interval(dt_s) == expected_steps


def test_scan_rate_faster_than_simulation_rejected():
    with pytest.raises(ValueError, match="cannot scan faster"):
        make_sensor(update_rate_hz=100.0).scan_step_interval(0.1)


def test_non_integer_scan_period_rejected():
    """3 Hz gives a 0.333 s period, which is not a multiple of a 0.1 s timestep.

    Snapping to the nearest step would silently jitter measurement timestamps, so
    the configuration is rejected instead.
    """
    with pytest.raises(ValueError, match="not an integer multiple"):
        make_sensor(update_rate_hz=3.0).scan_step_interval(0.1)


# ------------------------------------------------------------------------ detection


def test_noiseless_perfect_sensor_reproduces_exact_geometry():
    """With no noise and certain detection, output must equal the true polar position."""
    sensor = make_sensor(
        range_noise_m=0.0,
        bearing_noise_deg=0.0,
        detection_probability=1.0,
        false_alarm_rate_per_scan=0.0,
    )
    result = sensor.scan(make_state(positions=((100.0, 200.0),)), first_meas_id=0)

    assert len(result.measurements) == 1
    values = result.measurements[0].values
    assert values["range_m"] == pytest.approx(223.6068, abs=1e-4)
    assert math.degrees(values["bearing_rad"]) == pytest.approx(63.4349, abs=1e-4)
    assert result.truth_target_ids == (1,)


def test_sensor_offset_from_origin_measures_relative_geometry():
    """A radar away from the origin reports range and bearing from itself."""
    sensor = make_sensor(
        position_m=(50.0, 50.0),
        range_noise_m=0.0,
        bearing_noise_deg=0.0,
        detection_probability=1.0,
        false_alarm_rate_per_scan=0.0,
    )
    result = sensor.scan(make_state(positions=((150.0, 50.0),)), first_meas_id=0)

    values = result.measurements[0].values
    assert values["range_m"] == pytest.approx(100.0, abs=1e-9)
    assert values["bearing_rad"] == pytest.approx(0.0, abs=1e-9)


def test_targets_beyond_max_range_are_not_reported():
    sensor = make_sensor(
        max_range_m=1000.0,
        range_noise_m=0.0,
        bearing_noise_deg=0.0,
        detection_probability=1.0,
        false_alarm_rate_per_scan=0.0,
    )
    result = sensor.scan(make_state(positions=((500.0, 0.0), (2000.0, 0.0))), first_meas_id=0)

    assert result.truth_target_ids == (1,)


def test_zero_detection_probability_reports_nothing():
    sensor = make_sensor(detection_probability=0.0, false_alarm_rate_per_scan=0.0)

    assert sensor.scan(make_state(), first_meas_id=0).measurements == ()


def test_measurement_ids_are_sequential_from_the_supplied_start():
    sensor = make_sensor(detection_probability=1.0, false_alarm_rate_per_scan=0.0)
    positions = tuple((100.0 * i, 0.0) for i in range(1, 6))

    result = sensor.scan(make_state(positions=positions), first_meas_id=100)

    assert [m.meas_id for m in result.measurements] == [100, 101, 102, 103, 104]


def test_measurement_carries_the_sensor_covariance():
    sensor = make_sensor(detection_probability=1.0, false_alarm_rate_per_scan=0.0)
    result = sensor.scan(make_state(), first_meas_id=0)

    np.testing.assert_allclose(result.measurements[0].covariance, sensor.config.covariance)
    assert result.measurements[0].sensor_type == "radar"
    assert result.measurements[0].frame == "polar"


# ----------------------------------------------------------------------- statistics


def test_range_noise_matches_the_configured_standard_deviation():
    """Over many scans the error distribution must match the configured sigma.

    With 20000 samples the sample standard deviation has a relative standard error
    near 0.5%, so a 5% tolerance is roughly ten standard errors wide.
    """
    sigma_m, true_range_m, samples = 2.0, 1000.0, 20000
    sensor = make_sensor(
        range_noise_m=sigma_m,
        bearing_noise_deg=0.0,
        detection_probability=1.0,
        false_alarm_rate_per_scan=0.0,
    )
    state = make_state(positions=((true_range_m, 0.0),))

    errors = np.array(
        [
            sensor.scan(state, 0).measurements[0].values["range_m"] - true_range_m
            for _ in range(samples)
        ]
    )

    assert errors.mean() == pytest.approx(0.0, abs=0.15)
    assert errors.std(ddof=1) == pytest.approx(sigma_m, rel=0.05)


def test_bearing_noise_matches_the_configured_standard_deviation():
    """Target placed due East so the error never straddles the +/-pi wrap point."""
    sigma_deg, samples = 1.0, 20000
    sensor = make_sensor(
        range_noise_m=0.0,
        bearing_noise_deg=sigma_deg,
        detection_probability=1.0,
        false_alarm_rate_per_scan=0.0,
    )
    state = make_state(positions=((1000.0, 0.0),))

    errors_deg = np.degrees(
        [sensor.scan(state, 0).measurements[0].values["bearing_rad"] for _ in range(samples)]
    )

    assert errors_deg.mean() == pytest.approx(0.0, abs=0.08)
    assert errors_deg.std(ddof=1) == pytest.approx(sigma_deg, rel=0.05)


def test_detection_probability_is_honoured():
    """p = 0.9 over 20000 scans has a standard error near 0.002; allow 0.02."""
    p, samples = 0.9, 20000
    sensor = make_sensor(detection_probability=p, false_alarm_rate_per_scan=0.0)
    state = make_state()

    hits = sum(len(sensor.scan(state, 0).measurements) for _ in range(samples))

    assert hits / samples == pytest.approx(p, abs=0.02)


def test_false_alarm_count_matches_the_configured_rate():
    """Poisson mean equals the rate; standard error over 20000 scans is near 0.01."""
    rate, samples = 2.0, 20000
    sensor = make_sensor(detection_probability=0.0, false_alarm_rate_per_scan=rate)
    state = make_state()

    counts = [len(sensor.scan(state, 0).measurements) for _ in range(samples)]

    assert np.mean(counts) == pytest.approx(rate, abs=0.08)
    # A Poisson distribution has variance equal to its mean; a different spread
    # would indicate the wrong distribution even if the average came out right.
    assert np.var(counts) == pytest.approx(rate, rel=0.10)


def test_false_alarms_are_labelled_and_lie_within_range():
    sensor = make_sensor(
        detection_probability=0.0, false_alarm_rate_per_scan=5.0, max_range_m=1000.0
    )
    result = sensor.scan(make_state(), first_meas_id=0)

    assert len(result.measurements) > 0
    assert set(result.truth_target_ids) == {FALSE_ALARM_TARGET_ID}
    for m in result.measurements:
        assert 0.0 <= m.values["range_m"] <= 1000.0
        assert -math.pi <= m.values["bearing_rad"] <= math.pi


def test_reported_range_is_never_negative():
    """A close target with large noise must not produce an unphysical range."""
    sensor = make_sensor(
        range_noise_m=50.0,
        detection_probability=1.0,
        false_alarm_rate_per_scan=0.0,
    )
    state = make_state(positions=((1.0, 0.0),))

    ranges = [sensor.scan(state, 0).measurements[0].values["range_m"] for _ in range(5000)]

    assert min(ranges) >= 0.0


def test_scan_order_does_not_reveal_which_detections_are_real():
    """Real detections are generated before false alarms, so output must be shuffled.

    Without the shuffle every false alarm would appear last, and a tracker could
    score perfectly on association by reading position in the list rather than by
    associating anything.
    """
    sensor = make_sensor(detection_probability=1.0, false_alarm_rate_per_scan=3.0)
    state = make_state(positions=((100.0, 0.0), (200.0, 100.0), (300.0, -50.0)))

    real_appears_after_false = 0
    for _ in range(300):
        labels = sensor.scan(state, 0).truth_target_ids
        if FALSE_ALARM_TARGET_ID in labels:
            first_false = labels.index(FALSE_ALARM_TARGET_ID)
            if any(label != FALSE_ALARM_TARGET_ID for label in labels[first_false:]):
                real_appears_after_false += 1

    assert real_appears_after_false > 50, "ordering still correlates with truth"


# --------------------------------------------------------------------- determinism


def test_same_seed_produces_identical_measurements():
    """Verifies SYS-003 holds once randomness is in the loop."""
    state = make_state(positions=((100.0, 50.0), (300.0, -200.0)))

    def run(seed):
        sensor = make_sensor(seed=seed)
        return [
            (m.meas_id, m.values["range_m"], m.values["bearing_rad"])
            for _ in range(20)
            for m in sensor.scan(state, 0).measurements
        ]

    assert run(4242) == run(4242)


def test_different_seeds_produce_different_measurements():
    """Guards against an RNG that is accidentally fixed rather than merely seeded."""
    state = make_state(positions=((100.0, 50.0),))

    def run(seed):
        sensor = make_sensor(seed=seed)
        return [sensor.scan(state, 0).measurements[0].values["range_m"] for _ in range(20)]

    assert run(1) != run(2)
