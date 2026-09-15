"""The simulated world: a set of ground-truth targets advanced on a fixed clock."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from mstt.sim.motion import constant_velocity_transition
from mstt.sim.target import Target


@dataclass(frozen=True)
class WorldState:
    """All ground-truth targets at a single simulation time."""

    t_s: float
    targets: tuple[Target, ...]


class World:
    """Advances a collection of targets on a fixed timestep.

    The world owns simulation time only. It has no knowledge of sensors, noise, or
    tracking; it answers exactly one question — where is everything, when. Keeping
    that boundary strict is what allows ground truth to be generated once and reused
    across any number of sensor configurations.
    """

    def __init__(self, targets: list[Target], dt_s: float, duration_s: float) -> None:
        """
        Args:
            targets: Initial ground-truth targets. Must be non-empty with unique IDs.
            dt_s: Simulation timestep in seconds, strictly positive.
            duration_s: Total simulated duration in seconds, non-negative.

        Raises:
            ValueError: On an empty target list, duplicate target IDs, or a
                non-positive timestep. These indicate a malformed scenario, which
                should fail at load time rather than produce a silently empty run.
        """
        if not targets:
            raise ValueError("scenario must define at least one target")

        ids = [t.target_id for t in targets]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"duplicate target ids in scenario: {sorted(duplicates)}")

        if dt_s <= 0.0:
            raise ValueError(f"dt_s must be strictly positive, got {dt_s!r}")
        if duration_s < 0.0:
            raise ValueError(f"duration_s must be non-negative, got {duration_s!r}")

        self._initial_targets = tuple(targets)
        self.dt_s = float(dt_s)
        self.duration_s = float(duration_s)
        self._transition = constant_velocity_transition(self.dt_s)

    @property
    def step_count(self) -> int:
        """Number of timesteps the run will emit, including the initial state at t=0."""
        return int(round(self.duration_s / self.dt_s)) + 1

    def run(self) -> Iterator[WorldState]:
        """Yield the world state at each timestep, starting at t = 0.

        Simulation time is computed as ``step_index * dt_s`` rather than by
        accumulating ``t += dt_s``. Repeated addition of a value such as 0.1, which
        has no exact binary representation, accumulates rounding error that grows
        with run length — after 600 steps the drift is large enough to perturb the
        6-decimal output format and break the bit-identical reruns required by
        SYS-003. Multiplication introduces a single rounding, not six hundred.
        """
        targets = self._initial_targets
        for step_index in range(self.step_count):
            yield WorldState(t_s=step_index * self.dt_s, targets=targets)
            targets = tuple(t.advanced(self._transition) for t in targets)
