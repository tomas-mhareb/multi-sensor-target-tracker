/// Tests for coordinate frame conversions.
///
/// Two kinds of check. The first is behavioural: hand-computed values, quadrant
/// coverage, and the wrap boundary. The second is cross-language: the same functions
/// implemented in Python must agree, verified against committed golden vectors. The
/// second catches the failure the first cannot, namely the two implementations being
/// individually self-consistent but disagreeing with each other.

#include "mstt/core/Frames.hpp"
#include "mstt/core/Types.hpp"

#include <gtest/gtest.h>

#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using mstt::core::CartesianPoint;
using mstt::core::PolarPoint;

constexpr double kPi = 3.14159265358979323846;

/// Absolute tolerance for cross-language comparison.
///
/// A double carries roughly 16 significant digits, so 1e-12 permits a few thousand
/// units in the last place -- ample room for the two standard libraries to round
/// differently, while remaining many orders of magnitude tighter than any convention
/// error, which would show up as a difference near pi or a sign flip.
constexpr double kCrossLanguageTolerance = 1e-12;

double degrees(double radians) {
    return radians * 180.0 / kPi;
}

struct GoldenRow {
    std::string case_name;
    double in_a = 0.0;
    double in_b = 0.0;
    double out_a = 0.0;
    double out_b = 0.0;
};

std::vector<GoldenRow> load_golden_vectors() {
    const std::string path = std::string(MSTT_TEST_DATA_DIR) + "/golden/geometry.csv";
    std::ifstream file(path);
    // A missing golden file must fail loudly. Silently skipping would turn the
    // cross-language check into a test that always passes.
    EXPECT_TRUE(file.is_open()) << "cannot open golden vectors at " << path;

    std::vector<GoldenRow> rows;
    std::string line;
    std::getline(file, line);  // header

    while (std::getline(file, line)) {
        if (line.empty()) {
            continue;
        }
        std::istringstream stream(line);
        std::string field;
        GoldenRow row;

        std::getline(stream, row.case_name, ',');
        std::getline(stream, field, ',');
        row.in_a = std::stod(field);
        std::getline(stream, field, ',');
        row.in_b = std::stod(field);
        std::getline(stream, field, ',');
        row.out_a = std::stod(field);
        std::getline(stream, field, ',');
        row.out_b = std::stod(field);

        rows.push_back(row);
    }
    return rows;
}

}  // namespace

TEST(Frames, MatchesTheWorkedExampleInConventions) {
    // docs/conventions.md section 7 fixes this case. A bearing of 26.57 degrees would
    // mean compass convention had crept in.
    const PolarPoint polar = mstt::core::to_polar(CartesianPoint{100.0, 200.0});

    EXPECT_NEAR(polar.range_m, 223.6068, 1e-4);
    EXPECT_NEAR(degrees(polar.bearing_rad), 63.4349, 1e-4);
}

TEST(Frames, BearingCoversAllFourQuadrants) {
    struct Case {
        double x_m;
        double y_m;
        double expected_deg;
        const char* label;
    };
    // The West and South-West cases are the ones atan(y/x) reports incorrectly; the
    // North and South cases are the ones it cannot evaluate at all.
    const Case cases[] = {
        {100.0, 0.0, 0.0, "East"},          {0.0, 100.0, 90.0, "North"},
        {-100.0, 0.0, 180.0, "West"},       {0.0, -100.0, -90.0, "South"},
        {100.0, 100.0, 45.0, "North-East"}, {-100.0, -100.0, -135.0, "South-West"},
    };

    for (const Case& c : cases) {
        const PolarPoint polar = mstt::core::to_polar(CartesianPoint{c.x_m, c.y_m});
        EXPECT_NEAR(degrees(polar.bearing_rad), c.expected_deg, 1e-9) << c.label;
        EXPECT_NEAR(polar.range_m, 100.0 * (std::abs(c.x_m) > 0 && std::abs(c.y_m) > 0
                                                ? std::sqrt(2.0)
                                                : 1.0),
                    1e-9)
            << c.label;
    }
}

TEST(Frames, RoundTripIsIdentity) {
    for (double x_m = -1000.0; x_m <= 1000.0; x_m += 250.0) {
        for (double y_m = -1000.0; y_m <= 1000.0; y_m += 250.0) {
            const CartesianPoint back = mstt::core::to_cartesian(
                mstt::core::to_polar(CartesianPoint{x_m, y_m}));

            EXPECT_NEAR(back.x_m, x_m, 1e-9) << "at (" << x_m << ", " << y_m << ")";
            EXPECT_NEAR(back.y_m, y_m, 1e-9) << "at (" << x_m << ", " << y_m << ")";
        }
    }
}

TEST(Frames, NegativeRangeIsRejected) {
    // Accepting it would place the point in exactly the opposite direction: a mirrored
    // track rather than a visible failure.
    // to_cartesian is [[nodiscard]]; the result is discarded explicitly because the
    // throw is what is under test. static_cast rather than a C-style cast, which
    // -Wold-style-cast rejects.
    EXPECT_THROW(static_cast<void>(mstt::core::to_cartesian(PolarPoint{-10.0, 0.0})),
                 std::invalid_argument);
}

TEST(Frames, WrapAngleRemovesWholeRevolutions) {
    EXPECT_NEAR(mstt::core::wrap_angle(0.0), 0.0, 1e-12);
    EXPECT_NEAR(degrees(mstt::core::wrap_angle(kPi * 181.0 / 180.0)), -179.0, 1e-9);
    EXPECT_NEAR(mstt::core::wrap_angle(2.0 * kPi), 0.0, 1e-9);
    EXPECT_NEAR(degrees(mstt::core::wrap_angle(kPi * 450.0 / 180.0)), 90.0, 1e-9);
    EXPECT_NEAR(degrees(mstt::core::wrap_angle(kPi * -450.0 / 180.0)), -90.0, 1e-9);
}

TEST(Frames, WrapAngleAlwaysWithinPi) {
    for (double angle = -50.0; angle <= 50.0; angle += 0.37) {
        const double wrapped = mstt::core::wrap_angle(angle);
        EXPECT_GE(wrapped, -kPi - 1e-12) << "at " << angle;
        EXPECT_LE(wrapped, kPi + 1e-12) << "at " << angle;
    }
}

TEST(Frames, AngularDifferenceAcrossTheDiscontinuity) {
    // The Kalman innovation case. Two bearings four degrees apart straddling the
    // boundary must differ by four degrees; subtracting naively gives 356, which as a
    // filter input destroys a track in one update.
    const double a = kPi * 178.0 / 180.0;
    const double b = kPi * -178.0 / 180.0;

    EXPECT_NEAR(degrees(a - b), 356.0, 1e-9);  // documents the failure mode
    EXPECT_NEAR(degrees(mstt::core::angular_difference(a, b)), -4.0, 1e-9);
}

TEST(Frames, CrossRangeErrorGrowsLinearlyWithRange) {
    const double sigma_rad = kPi * 1.0 / 180.0;

    EXPECT_NEAR(mstt::core::cross_range_error_m(100.0, sigma_rad), 1.7453, 1e-4);
    EXPECT_NEAR(mstt::core::cross_range_error_m(1000.0, sigma_rad), 17.4533, 1e-4);
    // Justifies ADR-003: at long range the camera repairs the axis the radar is worst at.
    EXPECT_GT(mstt::core::cross_range_error_m(5000.0, sigma_rad), 40.0 * 2.0);
}

TEST(Frames, StateIndicesMatchTheDocumentedOrder) {
    EXPECT_EQ(mstt::core::kStateDim, 4);
    EXPECT_EQ(mstt::core::kIdxX, 0);
    EXPECT_EQ(mstt::core::kIdxY, 1);
    EXPECT_EQ(mstt::core::kIdxVx, 2);
    EXPECT_EQ(mstt::core::kIdxVy, 3);
}

/// Cross-language verification against the Python implementation.
///
/// The golden file is produced by scripts/generate_golden_vectors.py. If this test
/// fails after a change to either implementation, the two have diverged and one is
/// wrong; regenerating the file to make the test pass would discard the only check
/// that the simulator and the tracker share a convention.
TEST(FramesGoldenVectors, AgreeWithThePythonImplementation) {
    const std::vector<GoldenRow> rows = load_golden_vectors();
    ASSERT_GT(rows.size(), 100U) << "golden vector file looks truncated";

    int to_polar_cases = 0;
    int wrap_cases = 0;

    for (const GoldenRow& row : rows) {
        if (row.case_name == "to_polar") {
            const PolarPoint polar = mstt::core::to_polar(CartesianPoint{row.in_a, row.in_b});
            const double range_tolerance =
                std::max(kCrossLanguageTolerance, kCrossLanguageTolerance * std::abs(row.out_a));

            EXPECT_NEAR(polar.range_m, row.out_a, range_tolerance)
                << "range at (" << row.in_a << ", " << row.in_b << ")";
            EXPECT_NEAR(polar.bearing_rad, row.out_b, kCrossLanguageTolerance)
                << "bearing at (" << row.in_a << ", " << row.in_b << ")";
            ++to_polar_cases;
        } else if (row.case_name == "wrap_angle") {
            EXPECT_NEAR(mstt::core::wrap_angle(row.in_a), row.out_a, kCrossLanguageTolerance)
                << "wrap of " << row.in_a;
            ++wrap_cases;
        } else {
            FAIL() << "unknown golden vector case: " << row.case_name;
        }
    }

    EXPECT_GT(to_polar_cases, 100);
    EXPECT_GT(wrap_cases, 50);
}
