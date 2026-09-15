/// Entry point for the tracking engine.
///
/// A placeholder at V0.3: the executable exists so that the build, the link, and the
/// packaging are exercised from the first release rather than discovered to be broken
/// once there is real code to run. It grows into the engine as the filter, association,
/// and track management land.

#include "mstt/core/Frames.hpp"
#include "mstt/core/Types.hpp"

#include <cstring>
#include <iostream>

namespace {

constexpr const char* kVersion = MSTT_VERSION;

void print_version() {
    std::cout << "mstt tracking engine " << kVersion << "\n"
              << "  state dimension : " << mstt::core::kStateDim << "\n"
              << "  frame           : East-North, angles CCW from +x, radians\n";
}

}  // namespace

int main(int argc, char** argv) {
    if (argc > 1 && std::strcmp(argv[1], "--version") == 0) {
        print_version();
        return 0;
    }

    std::cerr << "mstt " << kVersion << ": no tracking implemented yet.\n"
              << "The filter arrives in V0.3; see docs/requirements.md.\n"
              << "Usage: tracker --version\n";
    return 1;
}
