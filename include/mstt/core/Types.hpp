#pragma once

#include <Eigen/Dense>

/// Core types shared across the tracking engine.
///
/// Conventions are normative and defined in docs/conventions.md: an East-North world
/// frame, SI units, angles counter-clockwise from +x in radians.
namespace mstt::core {

/// Dimension of the 2D constant-velocity state vector, [x, y, vx, vy].
///
/// Named rather than written as a literal so the move to a 3D state in a later
/// release is a change to this constant and the matrices built from it, not a search
/// for every occurrence of the number four.
inline constexpr int kStateDim = 4;

/// Indices into a state vector. Fixed by docs/conventions.md.
inline constexpr int kIdxX = 0;
inline constexpr int kIdxY = 1;
inline constexpr int kIdxVx = 2;
inline constexpr int kIdxVy = 3;

/// Fixed-size aliases. Fixed-size Eigen types are stack allocated and their
/// arithmetic is unrolled at compile time, which matters for a filter that runs its
/// update cycle many times per second.
using StateVector = Eigen::Matrix<double, kStateDim, 1>;
using StateMatrix = Eigen::Matrix<double, kStateDim, kStateDim>;

}  // namespace mstt::core
