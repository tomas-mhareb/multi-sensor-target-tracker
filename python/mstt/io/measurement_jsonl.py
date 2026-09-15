"""Reader and writer for the measurement stream defined in docs/conventions.md 6.2.

JSON Lines rather than CSV because a measurement carries a covariance matrix, which
is awkward to express in flat columns and impossible to express uniformly across
sensors with different dimensionality. One self-describing object per line keeps the
file streamable: a consumer reads it incrementally without loading the whole run,
which is what allows the same schema to be carried over a socket later (ADR-005).
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Iterator
from pathlib import Path

import numpy as np

from mstt.sensors.measurement import Measurement

FALSE_ALARM_TARGET_ID = -1
"""Sentinel in measurement_truth.csv marking a measurement no target produced."""

FLOAT_PRECISION = 7
"""Decimal places for measurement values.

One more than truth.csv, because bearings are stored in radians: 1e-6 rad is about
0.2 m of cross-range error at 3 km, which is coarse enough to be visible against a
sub-metre sensor. Fixed-width formatting preserves the byte-comparison determinism
check from SYS-003.
"""


def write_measurements_jsonl(path: Path | str, measurements: Iterable[Measurement]) -> int:
    """Write measurements to JSON Lines. Returns the number of records written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0

    with path.open("w") as handle:
        for m in measurements:
            record = {
                "meas_id": m.meas_id,
                "t_s": round(m.t_s, 6),
                "sensor_id": m.sensor_id,
                "sensor_type": m.sensor_type,
                "frame": m.frame,
                "values": {k: round(v, FLOAT_PRECISION) for k, v in m.values.items()},
                "covariance": [[round(float(x), 12) for x in row] for row in m.covariance],
            }
            handle.write(json.dumps(record, sort_keys=False) + "\n")
            written += 1

    return written


def read_measurements_jsonl(path: Path | str) -> Iterator[Measurement]:
    """Stream measurements back from JSON Lines.

    Yields rather than returning a list so a long run can be replayed without being
    held in memory, matching how a socket transport would deliver them.
    """
    with Path(path).open() as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc

            yield Measurement(
                meas_id=record["meas_id"],
                t_s=record["t_s"],
                sensor_id=record["sensor_id"],
                sensor_type=record["sensor_type"],
                frame=record["frame"],
                values=dict(record["values"]),
                covariance=np.array(record["covariance"], dtype=np.float64),
            )


def write_measurement_truth_csv(path: Path | str, pairs: Iterable[tuple[int, int]]) -> int:
    """Write the evaluation key mapping meas_id to the target that produced it.

    A ``target_id`` of :data:`FALSE_ALARM_TARGET_ID` marks a false alarm. This file
    is written for scoring only and is never read by the tracking engine; keeping it
    out of the measurement stream is what makes cheating structurally impossible
    rather than merely discouraged.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("meas_id", "target_id"))
        for meas_id, target_id in pairs:
            writer.writerow([meas_id, target_id])
            written += 1

    return written
