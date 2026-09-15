"""The common sensor measurement record.

Every sensor in the system produces this same structure, whatever it physically
measures. A radar contributes range and bearing; a camera will contribute a single
bearing. The tracker does not branch on sensor hardware -- it reads ``sensor_type``
and ``frame`` and applies the matching measurement model. That is what makes adding
a sensor a matter of adding a model rather than a pipeline stage (ADR-001).

Ground truth is deliberately absent from this record. Which target produced a
measurement is written separately, so a tracker cannot read it even by accident.
See docs/conventions.md section 6.2.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Measurement:
    """A single sensor observation, with the sensor's own uncertainty attached.

    Attributes:
        meas_id: Unique, monotonically increasing within a run. Joins to the
            evaluation key in measurement_truth.csv.
        t_s: Simulation time at which the measurement was taken.
        sensor_id: Which sensor instance produced it, e.g. ``radar_0``.
        sensor_type: Selects the tracker's measurement model, e.g. ``radar``.
        frame: Coordinate frame of ``values``, e.g. ``polar``.
        values: The measured quantities, keyed by name. **Iteration order defines
            the row and column order of** ``covariance``; dictionaries preserve
            insertion order, and the two must be constructed together.
        covariance: The sensor's R, square, in the units of ``values``.
    """

    meas_id: int
    t_s: float
    sensor_id: str
    sensor_type: str
    frame: str
    values: dict[str, float]
    covariance: np.ndarray

    def __post_init__(self) -> None:
        dim = len(self.values)
        if self.covariance.shape != (dim, dim):
            raise ValueError(
                f"measurement {self.meas_id}: covariance must be "
                f"({dim}, {dim}) to match {dim} value(s), got {self.covariance.shape}"
            )

    @property
    def value_vector(self) -> np.ndarray:
        """The measured quantities as a vector, ordered to match ``covariance``."""
        return np.array(list(self.values.values()), dtype=np.float64)

    @property
    def value_names(self) -> tuple[str, ...]:
        """Names of the measured quantities, in covariance row order."""
        return tuple(self.values.keys())
