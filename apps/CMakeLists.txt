# Executables live here rather than alongside the libraries, so that everything in
# src/ is linkable by the test suite. A main() in a library target cannot be.

add_executable(tracker tracker_main.cpp)
target_link_libraries(tracker PRIVATE mstt::core)
target_compile_definitions(tracker PRIVATE MSTT_VERSION="${PROJECT_VERSION}")

mstt_set_target_warnings(tracker)
mstt_enable_sanitizers(tracker)
