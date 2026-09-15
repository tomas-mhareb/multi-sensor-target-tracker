"""Tests for the ground-truth CSV writer.

Verifies SYS-003 (bit-identical output for a given configuration).
"""

import csv

import pytest

from mstt.io.truth_csv import TRUTH_COLUMNS, write_truth_csv
from mstt.sim.target import Target
from mstt.sim.world import World


def make_world(n_targets=2, duration_s=1.0, dt_s=0.1):
    targets = [
        Target.from_position_velocity(i, (float(i), 0.0), (8.0, 4.0))
        for i in range(1, n_targets + 1)
    ]
    return World(targets=targets, dt_s=dt_s, duration_s=duration_s)


def test_header_matches_the_documented_schema(tmp_path):
    path = tmp_path / "truth.csv"
    write_truth_csv(path, make_world().run())

    with path.open() as handle:
        header = next(csv.reader(handle))

    assert tuple(header) == TRUTH_COLUMNS
    assert tuple(header) == ("t_s", "target_id", "x_m", "y_m", "vx_mps", "vy_mps")


def test_row_count_is_steps_times_targets(tmp_path):
    world = make_world(n_targets=3, duration_s=1.0, dt_s=0.1)
    rows = write_truth_csv(tmp_path / "truth.csv", world.run())

    assert rows == world.step_count * 3 == 11 * 3


def test_rows_ordered_by_time_then_target_id(tmp_path):
    """Deterministic ordering, independent of the order the simulator holds targets."""
    path = tmp_path / "truth.csv"
    write_truth_csv(path, make_world(n_targets=3, duration_s=0.2).run())

    with path.open() as handle:
        rows = list(csv.DictReader(handle))

    keys = [(float(r["t_s"]), int(r["target_id"])) for r in rows]
    assert keys == sorted(keys)
    assert keys[:3] == [(0.0, 1), (0.0, 2), (0.0, 3)]


def test_all_float_fields_use_six_decimal_places(tmp_path):
    """Fixed-width formatting is what makes byte comparison a meaningful check."""
    path = tmp_path / "truth.csv"
    write_truth_csv(path, make_world(n_targets=1, duration_s=0.2).run())

    with path.open() as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        for field in ("t_s", "x_m", "y_m", "vx_mps", "vy_mps"):
            assert row[field].split(".")[1] == row[field].split(".")[1][:6]
            assert len(row[field].split(".")[1]) == 6, f"{field}={row[field]!r}"


def test_values_match_hand_computation(tmp_path):
    """Target 1 starts at (1, 0) at (8, 4) m/s; after 1.0 s it is at (9, 4)."""
    path = tmp_path / "truth.csv"
    write_truth_csv(path, make_world(n_targets=1, duration_s=1.0).run())

    with path.open() as handle:
        rows = list(csv.DictReader(handle))

    assert float(rows[0]["x_m"]) == pytest.approx(1.0)
    assert float(rows[-1]["t_s"]) == pytest.approx(1.0)
    assert float(rows[-1]["x_m"]) == pytest.approx(9.0, abs=1e-6)
    assert float(rows[-1]["y_m"]) == pytest.approx(4.0, abs=1e-6)


def test_output_is_bit_identical_across_runs(tmp_path):
    """Verifies SYS-003 by byte comparison, the strongest available check."""
    first = tmp_path / "a" / "truth.csv"
    second = tmp_path / "b" / "truth.csv"

    write_truth_csv(first, make_world(n_targets=5, duration_s=30.0).run())
    write_truth_csv(second, make_world(n_targets=5, duration_s=30.0).run())

    assert first.read_bytes() == second.read_bytes()
    assert first.stat().st_size > 0


def test_parent_directories_created(tmp_path):
    path = tmp_path / "deeply" / "nested" / "run" / "truth.csv"
    write_truth_csv(path, make_world().run())

    assert path.is_file()
