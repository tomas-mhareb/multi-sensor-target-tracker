"""Ground-truth target representation.

A Target is the simulator's notion of an object that actually exists, with a known
exact state. This is deliberately distinct from a Track, which is the tracker's
*estimate* of an object it believes exists. The two are never interchangeable —
see docs/conventions.md section 5 on identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from mstt.sim.motion import IDX_VX, IDX_VY, IDX_X, IDX_Y, STATE_DIM, propagate


@dataclass(frozen=True)
class Target:
    """A single ground-truth target at one instant in time.

    Frozen because a Target represents the target's state at a specific timestep,
    not a mutable object that evolves in place. Advancing time produces a new
    Target via :meth:`advanced`, which makes it impossible to accidentally share
    or overwrite state between timesteps — a common source of silent simulation
    bugs when trajectories are stored for later analysis.

    Attributes:
        target_id: Identifier from the scenario configuration. Stable for the run.
        state: A ``(4,)`` array ``[x_m, y_m, vx_mps, vy_mps]`` in the world frame.
    """

    target_id: int
    state: np.ndarray

    def __post_init__(self) -> None:
        if self.state.shape != (STATE_DIM,):
            raise ValueError(
                f"target {self.target_id}: state must have shape ({STATE_DIM},), "
                f"got {self.state.shape}"
            )

    @classmethod
    def from_position_velocity(
        cls,
        target_id: int,
        position_m: tuple[float, float],
        velocity_mps: tuple[float, float],
    ) -> Target:
        """Build a Target from separate position and velocity pairs.

        This is the form scenario configuration files use, since ``position: [0, 0]``
        reads more clearly to a human author than a flat four-element state vector.
        """
        state = np.array(
            [position_m[0], position_m[1], velocity_mps[0], velocity_mps[1]],
            dtype=np.float64,
        )
        return cls(target_id=target_id, state=state)

    @property
    def x_m(self) -> float:
        """Position East, metres."""
        return float(self.state[IDX_X])

    @property
    def y_m(self) -> float:
        """Position North, metres."""
        return float(self.state[IDX_Y])

    @property
    def vx_mps(self) -> float:
        """Velocity East, metres per second."""
        return float(self.state[IDX_VX])

    @property
    def vy_mps(self) -> float:
        """Velocity North, metres per second."""
        return float(self.state[IDX_VY])

    @property
    def speed_mps(self) -> float:
        """Scalar speed, metres per second."""
        return float(np.hypot(self.state[IDX_VX], self.state[IDX_VY]))

    @property
    def heading_rad(self) -> float:
        """Direction of travel, radians counter-clockwise from East, in (-pi, pi].

        Undefined for a stationary target; returns 0.0 in that case rather than
        raising, since a stationary target is a legitimate scenario and the caller
        can check :attr:`speed_mps` if the distinction matters.
        """
        return float(np.arctan2(self.state[IDX_VY], self.state[IDX_VX]))

    def advanced(self, transition: np.ndarray) -> Target:
        """Return a new Target advanced by one application of ``transition``."""
        return Target(target_id=self.target_id, state=propagate(self.state, transition))
