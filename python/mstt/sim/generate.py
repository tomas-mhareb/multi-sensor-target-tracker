"""Execute a scenario end to end and write its run artifacts.

Produces the four files described in docs/conventions.md section 6.3: ground truth,
the measurement stream the tracker consumes, the evaluation key it must not, and a
summary of what the sensors actually saw.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path

from mstt.io.measurement_jsonl import (
    FALSE_ALARM_TARGET_ID,
    write_measurement_truth_csv,
    write_measurements_jsonl,
)
from mstt.io.truth_csv import write_truth_csv
from mstt.sim.scenario import Scenario


@dataclass(frozen=True)
class RunSummary:
    """What a scenario run produced. Reported by the CLI and written to the run dir."""

    scenario_name: str
    seed: int | None
    sensor_positions: dict[str, tuple[float, float]]
    """Where each sensor sat, keyed by sensor id.

    Recorded so the run directory is self-describing: measurements are polar and
    relative to their sensor, so anything reading them back -- a plot, a metrics
    script, the tracker -- needs the sensor position to place them in the world. A
    run that required its originating scenario file to be interpretable would not be
    reproducible on its own.
    """
    timesteps: int
    truth_rows: int
    scans: int
    detection_opportunities: int
    detections: int
    missed_detections: int
    false_alarms: int
    measurements: int

    @property
    def detection_rate(self) -> float:
        """Fraction of in-range targets actually reported, across all scans.

        Compared against the configured detection probability, this is a direct check
        that the sensor behaved as specified over the whole run rather than only in
        the unit tests.
        """
        if self.detection_opportunities == 0:
            return 0.0
        return self.detections / self.detection_opportunities


def generate_run(scenario: Scenario, out_dir: Path | str) -> RunSummary:
    """Run a scenario and write truth, measurements, and the evaluation key.

    Args:
        scenario: A validated scenario.
        out_dir: Directory to write run artifacts into. Created if absent.

    Returns:
        A summary of the run.
    """
    out_dir = Path(out_dir)
    world = scenario.build_world()
    sensors = scenario.build_sensors()

    # Materialized rather than streamed because ground truth is consumed twice: once
    # to write truth.csv and once to drive the sensors. At the scales this project
    # targets -- hundreds of timesteps, tens of targets -- the memory cost is
    # negligible, and iterating once with two side effects would be harder to follow.
    states = list(world.run())
    truth_rows = write_truth_csv(out_dir / "truth.csv", states)

    scan_intervals = [sensor.scan_step_interval(world.dt_s) for sensor in sensors]

    measurements = []
    truth_pairs: list[tuple[int, int]] = []
    scans = 0
    detection_opportunities = 0
    next_meas_id = 0

    for step_index, state in enumerate(states):
        for sensor, interval in zip(sensors, scan_intervals, strict=True):
            if step_index % interval != 0:
                continue

            scans += 1
            detection_opportunities += _targets_in_range(state, sensor)

            result = sensor.scan(state, first_meas_id=next_meas_id)
            measurements.extend(result.measurements)
            truth_pairs.extend(
                zip(
                    (m.meas_id for m in result.measurements),
                    result.truth_target_ids,
                    strict=True,
                )
            )
            next_meas_id += len(result.measurements)

    # Sensors are visited per timestep, so measurements are already in ascending time
    # order. Sorting explicitly makes that a property of the file rather than an
    # accident of the loop, which matters once sensors run at different rates.
    measurements.sort(key=lambda m: (m.t_s, m.meas_id))

    if sensors:
        write_measurements_jsonl(out_dir / "measurements.jsonl", measurements)
        write_measurement_truth_csv(out_dir / "measurement_truth.csv", truth_pairs)

    false_alarms = sum(1 for _, tid in truth_pairs if tid == FALSE_ALARM_TARGET_ID)
    detections = len(truth_pairs) - false_alarms

    return RunSummary(
        scenario_name=scenario.name,
        seed=scenario.seed,
        sensor_positions={s.sensor_id: tuple(s.position_m) for s in scenario.sensors},
        timesteps=world.step_count,
        truth_rows=truth_rows,
        scans=scans,
        detection_opportunities=detection_opportunities,
        detections=detections,
        missed_detections=detection_opportunities - detections,
        false_alarms=false_alarms,
        measurements=len(measurements),
    )


def _targets_in_range(state, sensor) -> int:
    """Count targets a sensor could have detected, ignoring detection probability.

    This is the denominator for the measured detection rate. Targets beyond maximum
    range were never candidates, so counting them would understate sensor
    performance rather than describe it.
    """
    sx, sy = sensor.config.position_m
    return sum(
        1 for t in state.targets if math.hypot(t.x_m - sx, t.y_m - sy) <= sensor.config.max_range_m
    )


def summary_as_dict(summary: RunSummary) -> dict:
    """Summary in a form suitable for JSON, with the derived rate included."""
    data = asdict(summary)
    data["detection_rate"] = round(summary.detection_rate, 6)
    return data
