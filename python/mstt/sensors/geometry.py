"""Conversions between the Cartesian world frame and radar-native polar coordinates.

The world is Cartesian: x metres East, y metres North. A radar measures neither.
It measures range, from echo travel time, and bearing, from antenna pointing. Every
simulated measurement therefore crosses from Cartesian to polar, and every
measurement the tracker consumes crosses back.

Conventions are fixed by docs/conventions.md: angles are measured counter-clockwise
from the +x (East) axis, in radians, and the origin is the surveillance site.

Functions here are built from numpy ufuncs, so they accept scalars or arrays and
return the corresponding shape. That costs nothing and lets the analysis tooling
convert a whole trajectory in one call.
"""

from __future__ import annotations

import numpy as np


def cartesian_to_polar(x_m, y_m):
    """Convert world-frame position to radar-native range and bearing.

    Args:
        x_m: Position East of the surveillance site, metres.
        y_m: Position North of the surveillance site, metres.

    Returns:
        ``(range_m, bearing_rad)``, with bearing counter-clockwise from East.

    Note:
        Bearing uses ``arctan2(y, x)`` rather than ``arctan(y / x)``. The single
        argument form collapses the signs of x and y into one ratio before the
        arctangent sees them, so it cannot distinguish opposite quadrants: a target
        due West at (-100, 0) yields ``arctan(0 / -100) = 0``, reporting it due East.
        It also divides by zero for any target due North or South. The two-argument
        form inspects both signs and covers the full circle.
    """
    return np.hypot(x_m, y_m), np.arctan2(y_m, x_m)


def polar_to_cartesian(range_m, bearing_rad):
    """Convert a radar measurement back into the world frame.

    Args:
        range_m: Distance from the surveillance site, metres. Must be non-negative.
        bearing_rad: Bearing counter-clockwise from East, radians.

    Returns:
        ``(x_m, y_m)`` in the world frame.

    Raises:
        ValueError: If any range is negative. A negative range has no physical
            meaning, and silently accepting one would place the target in exactly
            the opposite direction -- a mirrored track rather than a visible error.
    """
    if np.any(np.asarray(range_m) < 0.0):
        raise ValueError("range_m must be non-negative")
    return range_m * np.cos(bearing_rad), range_m * np.sin(bearing_rad)


def wrap_angle(angle_rad):
    """Wrap an angle into ``[-pi, +pi]``.

    Every angular difference must be wrapped before use. The Kalman filter's
    innovation is the difference between a measured and a predicted bearing, and
    across the +/-pi discontinuity an unwrapped difference between two nearly
    identical directions evaluates to almost 2*pi. Fed to the filter as an error of
    360 degrees, it destroys the track in a single update.

    Implemented as ``arctan2(sin(a), cos(a))``, which discards whole revolutions by
    construction rather than by a modulo whose behaviour on negative inputs differs
    between languages.

    Note:
        The result interval is closed, not half-open: an input of exactly ``-pi``
        returns ``-pi`` rather than ``+pi``. Both denote due West, and the project
        never compares angles for equality, so no branch is added to enforce a
        distinction that carries no operational meaning.
    """
    return np.arctan2(np.sin(angle_rad), np.cos(angle_rad))


def angular_difference(a_rad, b_rad):
    """Return ``a - b`` wrapped to ``[-pi, +pi]``: the shortest turn from b to a."""
    return wrap_angle(np.asarray(a_rad) - np.asarray(b_rad))


def cross_range_error_m(range_m, bearing_sigma_rad):
    """Position error perpendicular to the line of sight, caused by bearing error.

    A bearing uncertainty is an angle, but a track lives in metres, and the arc
    length an angular error subtends grows with range::

        cross_range_error = range * bearing_sigma

    This is why a radar's uncertainty region is a wedge rather than a circle: the
    along-range error stays at its fixed metre value while the cross-range error
    scales with distance. With 2 m range noise and 1 degree bearing noise, the two
    are comparable at 100 m but the cross-range error is over forty times larger at
    5 km.

    It is also precisely the weakness a camera repairs. A camera cannot measure
    range at all, but it measures bearing far more precisely than a radar, so
    fusing the two collapses the wide axis of the wedge. See ADR-003.
    """
    return np.asarray(range_m) * np.asarray(bearing_sigma_rad)
