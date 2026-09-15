#pragma once

/// Conversions between the Cartesian world frame and sensor-native polar coordinates.
///
/// This is the C++ counterpart of python/mstt/sensors/geometry.py. The two exist
/// deliberately: the simulator generates measurements in Python, the tracker consumes
/// them in C++, and both must agree exactly on what a bearing means. Agreement is
/// verified against shared golden vectors rather than assumed, because a convention
/// mismatch between the two languages would produce mirrored tracks and no error.
namespace mstt::core {

/// A position in the world frame: metres East and North of the site datum.
struct CartesianPoint {
    double x_m = 0.0;
    double y_m = 0.0;
};

/// A position relative to a sensor: range in metres, bearing counter-clockwise from
/// East in radians.
struct PolarPoint {
    double range_m = 0.0;
    double bearing_rad = 0.0;
};

/// Convert a world-frame offset to range and bearing.
///
/// Bearing is computed with std::atan2 rather than std::atan of a ratio. The ratio
/// form collapses the signs of x and y before the arctangent sees them, so it cannot
/// distinguish opposite quadrants -- a point due West reports as due East -- and it
/// divides by zero for anything due North or South.
///
/// @param point Offset from the sensor, in the world frame.
/// @return Range in metres and bearing in radians, wrapped to [-pi, +pi].
[[nodiscard]] PolarPoint to_polar(CartesianPoint point) noexcept;

/// Convert range and bearing back to a world-frame offset.
///
/// @param point Range and bearing relative to the sensor.
/// @return Offset in metres.
/// @throws std::invalid_argument if range is negative. A negative range has no
///         physical meaning and would place the point in exactly the opposite
///         direction, producing a mirrored track rather than a visible failure.
[[nodiscard]] CartesianPoint to_cartesian(PolarPoint point);

/// Wrap an angle into [-pi, +pi].
///
/// Every angular difference must be wrapped before use. The Kalman innovation is the
/// difference between a measured and a predicted bearing; across the +/-pi boundary an
/// unwrapped difference between two nearly identical directions evaluates to almost
/// 2*pi, and fed to the filter as an error of a full revolution it destroys the track
/// in a single update.
[[nodiscard]] double wrap_angle(double angle_rad) noexcept;

/// The shortest signed turn from @p b_rad to @p a_rad, wrapped to [-pi, +pi].
[[nodiscard]] double angular_difference(double a_rad, double b_rad) noexcept;

/// Position error perpendicular to the line of sight caused by bearing uncertainty.
///
/// Equal to range * sigma, because an angular error subtends an arc length that grows
/// with distance. This is why a radar's uncertainty region is a wedge rather than a
/// circle, and it is the weakness a bearing-only camera repairs. See ADR-003.
[[nodiscard]] double cross_range_error_m(double range_m, double bearing_sigma_rad) noexcept;

}  // namespace mstt::core
