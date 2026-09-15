"""Motion models used to propagate ground-truth target state.

The constant-velocity model defined here is deliberately expressed as an explicit
state-transition matrix rather than as scalar arithmetic. The same operator appears
again in the Kalman filter's prediction step (V0.3): the simulator applies F to
propagate truth, and the filter applies the identical F to predict an estimate.
Writing it once, as a matrix, keeps that shared structure visible.

Frame and unit conventions are defined in docs/conventions.md. In short: state is
[x_m, y_m, vx_mps, vy_mps] in an East-North world frame, SI units throughout.
"""

from __future__ import annotations

import numpy as np

STATE_DIM = 4
"""Size of the 2D constant-velocity state vector."""

IDX_X = 0
IDX_Y = 1
IDX_VX = 2
IDX_VY = 3

STATE_FIELDS = ("x_m", "y_m", "vx_mps", "vy_mps")
"""Names of the state elements, in index order. Used for CSV headers and diagnostics."""


def constant_velocity_transition(dt_s: float) -> np.ndarray:
    """Build the state-transition matrix F for a constant-velocity target.

    Applying F advances the state by ``dt_s`` seconds::

        x_next = F @ x

    The matrix is the identity with two off-diagonal terms, which are the only
    coupling in the model and encode the single physical statement that position
    is the integral of velocity:

        [1  0  dt  0 ]     new_x  = x + vx*dt
        [0  1  0   dt]     new_y  = y + vy*dt
        [0  0  1   0 ]     new_vx = vx      (constant)
        [0  0  0   1 ]     new_vy = vy      (constant)

    Args:
        dt_s: Timestep in seconds. Must be strictly positive.

    Returns:
        A ``(4, 4)`` transition matrix.

    Raises:
        ValueError: If ``dt_s`` is not strictly positive. A zero or negative
            timestep indicates a malformed scenario rather than an edge case
            worth supporting, so it fails loudly at the source.
    """
    if dt_s <= 0.0:
        raise ValueError(f"dt_s must be strictly positive, got {dt_s!r}")

    transition = np.eye(STATE_DIM)
    transition[IDX_X, IDX_VX] = dt_s
    transition[IDX_Y, IDX_VY] = dt_s
    return transition


def propagate(state: np.ndarray, transition: np.ndarray) -> np.ndarray:
    """Advance a state vector by one application of a transition matrix.

    Args:
        state: A ``(4,)`` state vector ``[x_m, y_m, vx_mps, vy_mps]``.
        transition: A ``(4, 4)`` transition matrix, e.g. from
            :func:`constant_velocity_transition`.

    Returns:
        A new ``(4,)`` state vector. The input is not modified, so callers cannot
        accidentally alias propagated state across targets or timesteps.
    """
    if state.shape != (STATE_DIM,):
        raise ValueError(f"state must have shape ({STATE_DIM},), got {state.shape}")
    return transition @ state
