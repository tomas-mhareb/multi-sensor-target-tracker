#include "mstt/core/Frames.hpp"

#include <cmath>
#include <stdexcept>

namespace mstt::core {

PolarPoint to_polar(CartesianPoint point) noexcept {
    return PolarPoint{std::hypot(point.x_m, point.y_m), std::atan2(point.y_m, point.x_m)};
}

CartesianPoint to_cartesian(PolarPoint point) {
    if (point.range_m < 0.0) {
        throw std::invalid_argument("range_m must be non-negative");
    }
    return CartesianPoint{point.range_m * std::cos(point.bearing_rad),
                          point.range_m * std::sin(point.bearing_rad)};
}

double wrap_angle(double angle_rad) noexcept {
    // atan2(sin, cos) discards whole revolutions by construction. std::fmod would be
    // faster but its sign for negative operands is implementation-visible in a way
    // that has caused real defects, and this is not a hot path.
    return std::atan2(std::sin(angle_rad), std::cos(angle_rad));
}

double angular_difference(double a_rad, double b_rad) noexcept {
    return wrap_angle(a_rad - b_rad);
}

double cross_range_error_m(double range_m, double bearing_sigma_rad) noexcept {
    return range_m * bearing_sigma_rad;
}

}  // namespace mstt::core
