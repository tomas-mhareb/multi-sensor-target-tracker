# Unit tests. Registered individually with ctest via gtest_discover_tests, so a
# failure names the specific test rather than reporting that "the test binary failed".

add_executable(mstt_unit_tests
    unit/test_frames.cpp)

target_link_libraries(mstt_unit_tests PRIVATE
    mstt::core
    GTest::gtest_main)

# Golden vectors are located by absolute path at compile time rather than relative to
# the working directory, so the tests pass whether run from the build directory, the
# repository root, or by ctest.
target_compile_definitions(mstt_unit_tests PRIVATE
    MSTT_TEST_DATA_DIR="${PROJECT_SOURCE_DIR}/tests/data")

mstt_set_target_warnings(mstt_unit_tests)
mstt_enable_sanitizers(mstt_unit_tests)

include(GoogleTest)
gtest_discover_tests(mstt_unit_tests)
