# External dependencies, fetched and pinned rather than taken from the system.
#
# The development machine has Eigen 5.0.1 from Homebrew while Ubuntu's libeigen3-dev
# is 3.4.x. Building against whatever each platform happens to provide would bake the
# macOS/Linux divergence that CI exists to catch directly into the build. Pinning one
# version means the Mac, the CI runner, and the V0.8 Docker image compile identical
# sources, so a failure on one is reproducible on the others.
#
# The cost is a download on a cold build; CI caches it. See ADR-007.

include(FetchContent)

# Eigen: header-only linear algebra. Used for the filter's matrices, which are small
# and fixed-size, so Eigen allocates them on the stack and unrolls the arithmetic.
FetchContent_Declare(
    Eigen3
    GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
    GIT_TAG 3.4.0
    GIT_SHALLOW TRUE
    GIT_PROGRESS TRUE
    # Include these headers with -isystem so the compiler suppresses diagnostics from
    # them. This project builds its own sources with -Wold-style-cast and -Wconversion
    # among others, and Eigen's internals legitimately use constructs those flags
    # reject. Without SYSTEM the build fails inside a dependency we cannot fix, and the
    # only remedies would be to weaken the warnings for our own code or to ignore the
    # output -- both worse than the problem.
    SYSTEM)

# Eigen's own build produces tests, documentation, and install rules this project does
# not need; disabling them keeps the configure step from doing several minutes of
# irrelevant work.
set(EIGEN_BUILD_DOC OFF CACHE BOOL "" FORCE)
set(EIGEN_BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(EIGEN_BUILD_PKGCONFIG OFF CACHE BOOL "" FORCE)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)

FetchContent_MakeAvailable(Eigen3)

if(MSTT_BUILD_TESTS)
    FetchContent_Declare(
        googletest
        GIT_REPOSITORY https://github.com/google/googletest.git
        GIT_TAG v1.18.0
        GIT_SHALLOW TRUE
        GIT_PROGRESS TRUE
        SYSTEM)

    # Without this, GoogleTest links the static runtime on Windows while the rest of
    # the project links the dynamic one, which fails at link time.
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)

    FetchContent_MakeAvailable(googletest)
endif()
