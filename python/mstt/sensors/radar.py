"""A simulated radar sensor.

This is a software model, not a transmitting device. It takes exact ground truth and
degrades it the way a real radar would: additive noise, an imperfect chance of seeing
anything at all, and occasional reports of things that are not there.

Per ADR-006 the noise *generation* here is test infrastructure, written in Python.
The measurement *model* the filter uses -- h(x), its Jacobian, and R -- is product
code and will be implemented in C++. The distinction matters: this module decides
what a sensor would have reported; the tracker decides what a report implies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from mstt.sensors.geometry import cartesian_to_polar, wrap_angle
from mstt.sensors.measurement import Measurement
from mstt.sim.world import WorldState

FALSE_ALARM_TARGET_ID = -1


@dataclass(frozen=True)
class RadarConfig:
    """Parameters of a simulated radar.

    Attributes:
        sensor_id: Instance name, e.g. ``radar_0``.
        position_m: Sensor location in the world frame. Usually the origin, which
            docs/conventions.md defines as the surveillance site.
        update_rate_hz: Scans per second. Must divide the simulation rate evenly.
        range_noise_m: Standard deviation of range error, metres.
        bearing_noise_deg: Standard deviation of bearing error, degrees. Authored in
            degrees because a human writes it; converted once, at this boundary.
        detection_probability: Chance a target within range is reported on any given
            scan. Real radars miss targets through fading, aspect changes, and
            threshold crossings that fail.
        false_alarm_rate_per_scan: Mean number of spurious detections per scan.
        max_range_m: Beyond this the sensor reports nothing.
    """

    sensor_id: str
    position_m: tuple[float, float]
    update_rate_hz: float
    range_noise_m: float
    bearing_noise_deg: float
    detection_probability: float
    false_alarm_rate_per_scan: float
    max_range_m: float

    def __post_init__(self) -> None:
        if self.update_rate_hz <= 0.0:
            raise ValueError(f"{self.sensor_id}: update_rate_hz must be positive")
        if self.range_noise_m < 0.0:
            raise ValueError(f"{self.sensor_id}: range_noise_m must be non-negative")
        if self.bearing_noise_deg < 0.0:
            raise ValueError(f"{self.sensor_id}: bearing_noise_deg must be non-negative")
        if not 0.0 <= self.detection_probability <= 1.0:
            raise ValueError(
                f"{self.sensor_id}: detection_probability must lie in [0, 1], "
                f"got {self.detection_probability}"
            )
        if self.false_alarm_rate_per_scan < 0.0:
            raise ValueError(f"{self.sensor_id}: false_alarm_rate_per_scan must be non-negative")
        if self.max_range_m <= 0.0:
            raise ValueError(f"{self.sensor_id}: max_range_m must be positive")

    @property
    def bearing_noise_rad(self) -> float:
        """Bearing standard deviation in radians, the unit everything internal uses."""
        return math.radians(self.bearing_noise_deg)

    @property
    def covariance(self) -> np.ndarray:
        """The measurement noise covariance R, in (range, bearing) order.

        Diagonal, because range is derived from echo timing and bearing from antenna
        pointing: different hardware, different mechanisms, uncorrelated errors. The
        entries are variances, not standard deviations, so the units are m^2 and
        rad^2.
        """
        return np.diag([self.range_noise_m**2, self.bearing_noise_rad**2])


@dataclass(frozen=True)
class ScanResult:
    """Measurements from one scan, with a parallel list of their true origins.

    The two tuples are separate rather than combined into one record so that the
    measurements can be written to the tracker's input file while the truth labels
    go to the evaluation key, which the tracker never sees.
    """

    measurements: tuple[Measurement, ...]
    truth_target_ids: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.measurements) != len(self.truth_target_ids):
            raise ValueError("measurements and truth_target_ids must be parallel")


class RadarSensor:
    """Generates noisy range and bearing measurements from ground truth."""

    SENSOR_TYPE = "radar"
    FRAME = "polar"

    def __init__(self, config: RadarConfig, rng: np.random.Generator) -> None:
        """
        Args:
            config: Sensor parameters.
            rng: A seeded generator. Passed in rather than created internally so the
                caller controls reproducibility: SYS-003 requires bit-identical
                output for a given configuration and seed, and a sensor that seeded
                itself would make that impossible to guarantee across sensors.
        """
        self.config = config
        self._rng = rng

    def scan_step_interval(self, dt_s: float) -> int:
        """Simulation steps between scans, for a given simulation timestep.

        Raises:
            ValueError: If the sensor rate is not an integer divisor of the
                simulation rate. Allowing a fractional interval would force scans to
                be placed at the nearest step, silently jittering the measurement
                times. Rejecting the configuration keeps sensor timing exact.
        """
        scan_period_s = 1.0 / self.config.update_rate_hz
        steps = round(scan_period_s / dt_s)

        if steps < 1:
            raise ValueError(
                f"{self.config.sensor_id}: update_rate_hz "
                f"({self.config.update_rate_hz}) exceeds the simulation rate "
                f"({1.0 / dt_s:g} Hz); a sensor cannot scan faster than the world updates"
            )
        if abs(steps * dt_s - scan_period_s) > 1e-9:
            raise ValueError(
                f"{self.config.sensor_id}: scan period {scan_period_s:g} s is not an "
                f"integer multiple of the simulation timestep {dt_s:g} s"
            )
        return steps

    def scan(self, state: WorldState, first_meas_id: int) -> ScanResult:
        """Produce one scan's worth of measurements from the current world state.

        Args:
            state: Ground truth at the scan time.
            first_meas_id: Identifier to assign to the first measurement produced.

        Returns:
            The scan's measurements and the target id that produced each one, with
            :data:`FALSE_ALARM_TARGET_ID` marking a spurious detection.
        """
        detections: list[tuple[float, float, int]] = []

        for target in sorted(state.targets, key=lambda t: t.target_id):
            entry = self._detect(target)
            if entry is not None:
                detections.append((*entry, target.target_id))

        detections.extend((r, b, FALSE_ALARM_TARGET_ID) for r, b in self._false_alarms())

        # Shuffle before assigning identifiers. Real detections are generated first
        # and false alarms appended, so unshuffled output would encode which is which
        # in its ordering -- information a real sensor does not provide, and which a
        # tracker could exploit to score well on association it never performed.
        self._rng.shuffle(detections)

        measurements = []
        truth_ids = []
        for offset, (range_m, bearing_rad, target_id) in enumerate(detections):
            measurements.append(
                Measurement(
                    meas_id=first_meas_id + offset,
                    t_s=state.t_s,
                    sensor_id=self.config.sensor_id,
                    sensor_type=self.SENSOR_TYPE,
                    frame=self.FRAME,
                    values={"range_m": range_m, "bearing_rad": bearing_rad},
                    covariance=self.config.covariance,
                )
            )
            truth_ids.append(target_id)

        return ScanResult(tuple(measurements), tuple(truth_ids))

    def _detect(self, target) -> tuple[float, float] | None:
        """Attempt to detect one target. Returns None for a miss."""
        dx = target.x_m - self.config.position_m[0]
        dy = target.y_m - self.config.position_m[1]
        true_range_m, true_bearing_rad = cartesian_to_polar(dx, dy)

        if true_range_m > self.config.max_range_m:
            return None
        if self._rng.random() > self.config.detection_probability:
            return None

        noisy_range_m = true_range_m + self._rng.normal(0.0, self.config.range_noise_m)
        noisy_bearing_rad = wrap_angle(
            true_bearing_rad + self._rng.normal(0.0, self.config.bearing_noise_rad)
        )

        # A receiver measures echo delay and cannot report a negative one, so a noise
        # draw that would push range below zero is clipped rather than emitted. This
        # biases the error distribution very close to the sensor; at the ranges and
        # noise levels used here the affected region is a few metres wide.
        return max(0.0, float(noisy_range_m)), float(noisy_bearing_rad)

    def _false_alarms(self) -> list[tuple[float, float]]:
        """Generate spurious detections for one scan.

        The count is Poisson distributed because a radar tests a large number of
        independent resolution cells per scan, each with a small probability of
        crossing the detection threshold on noise alone. A large number of rare
        independent trials is exactly the limit the Poisson distribution describes.

        Position is uniform in range and bearing rather than uniform in Cartesian
        area, because false alarms occur per resolution cell and cells are laid out
        on a polar grid. Viewed in x and y the result is correctly denser near the
        sensor, since cell area grows with range.
        """
        count = int(self._rng.poisson(self.config.false_alarm_rate_per_scan))
        return [
            (
                float(self._rng.uniform(0.0, self.config.max_range_m)),
                float(self._rng.uniform(-math.pi, math.pi)),
            )
            for _ in range(count)
        ]
