"""The Python package and the C++ engine must report the same version.

The version is written in three places: the C++ project in CMakeLists.txt, the
package metadata in pyproject.toml, and ``mstt.__version__``. Before this test
existed they had drifted apart (0.3.0, 0.1.0, and 0.1.0) without anyone noticing.
A shared VERSION file would stop them drifting at all, but setuptools reading a file
outside python/ is fragile when building a source distribution. This test lets them
drift only as far as the next CI run.
"""

import re
import tomllib
from pathlib import Path

import mstt

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_python_and_cpp_versions_agree():
    cmake = (REPO_ROOT / "CMakeLists.txt").read_text()
    match = re.search(r"project\(\s*mstt\s+VERSION\s+(\d+\.\d+\.\d+)", cmake)
    assert match, "could not find the project version in CMakeLists.txt"

    with (REPO_ROOT / "python" / "pyproject.toml").open("rb") as handle:
        package = tomllib.load(handle)["project"]["version"]

    versions = {
        "CMakeLists.txt": match.group(1),
        "pyproject.toml": package,
        "mstt.__version__": mstt.__version__,
    }
    assert len(set(versions.values())) == 1, f"versions disagree: {versions}"
