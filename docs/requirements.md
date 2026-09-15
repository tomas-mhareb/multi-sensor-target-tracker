# System Requirements

## Purpose

This document defines what the system shall do, in a form that can be verified.
Every requirement has a unique identifier, a single testable statement, a
verification method, and the version in which it is first satisfied.

Requirements are traced to the tests that verify them in
[Section 5](#5-traceability). A requirement with no linked verification is not
considered satisfied, regardless of whether the code appears to work.

## 1. How to read a requirement

| Field | Meaning |
|---|---|
| **ID** | `SYS-nnn` system requirement, `CON-nnn` constraint. Identifiers are permanent and are never reused |
| **Requirement** | One testable statement using "shall". One requirement per statement — no "and" that hides two obligations |
| **Verify** | How satisfaction is demonstrated (see below) |
| **Version** | The release in which this requirement is first met |
| **Status** | `Open` / `Met` / `Target`. **`Target` means the value is a goal that has not yet been measured** |

### Verification methods

| Method | Definition |
|---|---|
| **Test** | Execute the system with controlled inputs and compare outputs against expected values |
| **Analysis** | Establish satisfaction by computation or statistical argument over collected data |
| **Demonstration** | Observe the system performing the function under representative conditions |
| **Inspection** | Examine the artifact — source, configuration, or documentation — without executing it |

## 2. Constraints

| ID | Constraint | Verify |
|---|---|---|
| **CON-001** | The system shall be limited to detection, tracking, and estimation. It shall not implement weapon control, fire control, guidance, interception, or engagement functions. | Inspection |
| **CON-002** | The system shall build and execute on Ubuntu Linux. | Demonstration |
| **CON-003** | The tracking engine shall be implemented in C++17 or later. | Inspection |
| **CON-004** | All sensor data shall originate from simulation or from recorded civilian footage. The system shall not require a physically transmitting radar. | Inspection |

## 3. Functional requirements

| ID | Requirement | Verify | Version | Status |
|---|---|---|---|---|
| **SYS-001** | The system shall define simulation scenarios via an external configuration file specifying targets, sensors, duration, and timestep. | Test | 0.1 | Met |
| **SYS-002** | The simulator shall generate ground-truth trajectories for at least 10 simultaneous targets. | Test | 0.1 | Met |
| **SYS-003** | The simulator shall produce bit-identical output for a given configuration and random seed. | Test | 0.1 | Met |
| **SYS-004** | The radar model shall generate range and bearing measurements with configurable Gaussian noise, detection probability, and false-alarm rate. | Test | 0.2 | Met |
| **SYS-005** | The tracker shall estimate target position and velocity together with an associated covariance matrix. | Test | 0.3 | Open |
| **SYS-008** | The track manager shall confirm a track after M detections within N scans, and delete a track after K consecutive missed detections, where M, N, and K are configurable. | Test | 0.6 | Open |
| **SYS-009** | The system shall emit structured log records containing timestamp, component, severity, and optional track identifier, filtered by a configurable severity threshold. | Inspection | 0.6 | Open |
| **SYS-011** | The system shall fuse measurements from at least two sensor types having different measurement models into a common track state. | Test | 0.9 | Open |
| **SYS-012** | The system shall report position RMSE, velocity RMSE, track continuity, and false-track count for each scenario run. | Test | 0.8 | Open |

## 4. Performance requirements

Values in this section are **targets** until measured on the reference platform and
recorded in [`test-results.md`](test-results.md). An unmeasured target is never
reported as a result.

| ID | Requirement | Verify | Version | Status |
|---|---|---|---|---|
| **SYS-006** | The tracker's filter shall pass a normalized innovation squared (NIS) consistency check, with at least 90% of samples falling inside the 95% chi-squared confidence bound. | Analysis | 0.3 | Open |
| **SYS-007** | The tracker shall complete one update cycle for 10 simultaneous targets within 10 ms on the reference platform. | Test | 0.5 | **Target** |
| **SYS-010** | The build pipeline shall compile the project and execute all unit tests on Ubuntu for every push and pull request. | Demonstration | 0.1 | Met |

### Reference platform

Characterized as DEV-1 in [`test-results.md`](test-results.md). Performance figures
are measured on DEV-1 only; the CI runner is shared and unpinned, and is therefore
not a valid platform for timing claims.

## 5. Traceability

Each requirement links to the test that verifies it. Populated as tests are written;
empty cells are honest indications of unverified requirements, not oversights to hide.

| Requirement | Verified by | Result |
|---|---|---|
| SYS-001 | `test_scenario.py::test_shipped_scenario_a_loads`<br>`test_scenario.py::test_build_world_uses_configured_timing`<br>`test_scenario.py::test_unknown_top_level_key_rejected` | Pass |
| SYS-002 | `test_world.py::test_supports_at_least_ten_simultaneous_targets`<br>`test_scenario.py::test_scenario_c_has_ten_targets` | Pass |
| SYS-003 | `test_truth_csv.py::test_output_is_bit_identical_across_runs`<br>`test_world.py::test_timestamps_are_exact_multiples_of_the_timestep`<br>`test_generate.py::test_run_is_bit_identical_for_the_same_seed` | Pass |
| SYS-004 | `test_radar.py` (29 tests)<br>`test_generate.py::test_scenario_e_detection_rate_is_consistent_with_its_configuration` | Pass |
| SYS-005 | — | — |
| SYS-006 | — | — |
| SYS-007 | — | — |
| SYS-008 | — | — |
| SYS-009 | — | — |
| SYS-010 | `.github/workflows/ci.yml` | Pass — [run 34915031256](https://github.com/tomas-mhareb/multi-sensor-target-tracker/actions/runs/34915031256) |
| SYS-011 | — | — |
| SYS-012 | — | — |
