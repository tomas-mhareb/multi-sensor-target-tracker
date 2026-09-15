cmake_minimum_required(VERSION 3.20)

project(mstt
    VERSION 0.3.0
    DESCRIPTION "Multi-sensor target tracking engine"
    LANGUAGES CXX)

# An in-source build scatters generated files through the tree and makes it
# impossible to tell what is source and what is output. Fail early with the fix.
if(PROJECT_SOURCE_DIR STREQUAL PROJECT_BINARY_DIR)
    message(FATAL_ERROR
        "In-source builds are not supported. Run:\n"
        "  cmake -B build && cmake --build build")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# Disable compiler extensions so the build fails on a GNU-only construct here rather
# than on a different compiler later. CON-002 requires this to run on Linux.
set(CMAKE_CXX_EXTENSIONS OFF)

# Emitted for clang-tidy and editor tooling; both need to know how each file is compiled.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    # Optimized but with debug information: the tracker's performance figures must be
    # measured on optimized code, and a stack trace is still wanted when it crashes.
    set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING "Build type" FORCE)
endif()

option(MSTT_BUILD_TESTS "Build the test suite" ON)
option(MSTT_ENABLE_SANITIZERS "Build with AddressSanitizer and UndefinedBehaviorSanitizer" OFF)
option(MSTT_WARNINGS_AS_ERRORS "Treat compiler warnings as errors" OFF)

include(cmake/CompilerWarnings.cmake)
include(cmake/Dependencies.cmake)

add_subdirectory(src)
add_subdirectory(apps)

if(MSTT_BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()

message(STATUS "")
message(STATUS "mstt ${PROJECT_VERSION}")
message(STATUS "  build type      : ${CMAKE_BUILD_TYPE}")
message(STATUS "  compiler        : ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}")
message(STATUS "  tests           : ${MSTT_BUILD_TESTS}")
message(STATUS "  sanitizers      : ${MSTT_ENABLE_SANITIZERS}")
message(STATUS "  warnings as err : ${MSTT_WARNINGS_AS_ERRORS}")
message(STATUS "")
