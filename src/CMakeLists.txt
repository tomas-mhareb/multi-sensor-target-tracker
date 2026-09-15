# The tracking engine's libraries. One target per module, so a dependency between
# modules has to be declared rather than acquired by accident.

add_library(mstt_core
    core/Frames.cpp)
add_library(mstt::core ALIAS mstt_core)

target_include_directories(mstt_core PUBLIC ${PROJECT_SOURCE_DIR}/include)
target_link_libraries(mstt_core PUBLIC Eigen3::Eigen)

mstt_set_target_warnings(mstt_core)
mstt_enable_sanitizers(mstt_core)
