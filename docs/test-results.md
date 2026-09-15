# Test Results

Measured results only. Every number in this document was produced by running the
software and is reproducible from the commit and platform recorded beside it.

Values that have not been measured do not appear here. They appear in
[`requirements.md`](requirements.md) marked `Target`, and are listed in the
"Not yet measured" section of each release below.

---

## Reference platforms

| | **DEV-1** (development) | **CI-1** (continuous integration) |
|---|---|---|
| OS | macOS 15.7.9 | Ubuntu (GitHub `ubuntu-latest`) |
| Architecture | x86_64 | x86_64 |
| CPU | Intel Core i7-8559U @ 2.70 GHz | GitHub-hosted runner, not pinned |
| Cores | 4 physical / 8 logical | 4 (as provisioned) |
| Memory | 16 GB | 16 GB (as provisioned) |
| Python | 3.13 (Homebrew) | 3.13 (`actions/setup-python@v7`) |
| Compiler | Homebrew clang 21.1.1 | not yet used |
| CMake | 4.4.3 | not yet used |

CI-1 is a shared, unpinned runner and its performance varies between runs. It is
suitable for verifying correctness and platform portability; it is **not** a valid
platform for timing claims. Performance requirements are measured on DEV-1 only,
and any figure quoted without a platform label should be treated as unverified.

---

## V0.2 — 2026-09-15

**Branch:** `feature/radar-simulator`
**Platform:** DEV-1 unless stated

### Unit tests

| Platform | Result | Duration |
|---|---|---|
| DEV-1 | 125 passed, 0 failed | 3.36 - 3.62 s over 3 runs |

Duration grew from 0.2 s to 3.4 s because the statistical tests draw tens of
thousands of samples each. That is the price of checking a stochastic model against
its configuration rather than only checking that it runs.

### Requirement verification

| ID | Requirement | Method | Result |
|---|---|---|---|
| SYS-004 | Radar model with configurable noise, detection probability, and false-alarm rate | Test | **Pass** |
| SYS-003 | Bit-identical output for a given configuration and seed | Test | **Pass** — still holds with randomness in the pipeline |

### Sensor model verified end to end

Residuals recovered from the written artifacts of Scenario B -- not from the
generator in memory -- by joining `measurements.jsonl` to `truth.csv` through
`measurement_truth.csv`. This checks the whole path including serialization
precision, not just the noise draw.

| Quantity | Configured | Measured | Standard error | Deviation |
|---|---|---|---|---|
| Range error mean | 0.0 m | +0.0402 m | 0.0836 m | 0.48 s.e. |
| Range error sigma | 2.0 m | 1.9244 m | 0.0591 m | -1.28 s.e. |
| Bearing error mean | 0.0 deg | +0.0665 deg | 0.0418 deg | 1.59 s.e. |
| Bearing error sigma | 1.0 deg | 0.9491 deg | 0.0296 deg | -1.72 s.e. |

Sample size 572 detections. Standard errors are `sigma/sqrt(n)` for the mean and
`sigma/sqrt(2n)` for the standard deviation. Every deviation falls within two
standard errors, which is what a correctly implemented model should produce.

### Scenario runs

All three scenarios: 60 s duration, 0.1 s timestep, 601 timesteps, radar at 10 Hz,
seed 20260915, maximum range 1000 m.

| Scenario | Configured P_d | Scans | Detections | Missed | False alarms | Total measurements | Measured rate |
|---|---|---|---|---|---|---|---|
| B_single_noisy | 0.95 | 601 | 572 | 29 | 303 | 875 | 0.9517 |
| E_missed_detections | 0.60 | 601 | 347 | 254 | 0 | 347 | 0.5774 |
| F_false_alarms | 1.00 | 601 | 601 | 0 | 2459 | 3060 | 1.0000 |

Rates against configuration, with binomial standard error `sqrt(p(1-p)/n)` for
detection and Poisson standard error `sqrt(lambda*n)` for false alarm counts:

| Scenario | Quantity | Expected | Measured | Deviation |
|---|---|---|---|---|
| B | detection rate | 0.950 | 0.9517 | 0.20 s.e. |
| B | false alarms | 301 | 303 | 0.14 s.e. |
| E | detection rate | 0.600 | 0.5774 | -1.13 s.e. |
| F | false alarms | 2404 | 2459 | 1.12 s.e. |

Scenario E's 57.7% differs from its configured 60% by 2.3 percentage points, which
looks like a discrepancy and is not: at 1.13 standard errors it is ordinary sampling
variation. Eyeballing a rate without computing its standard error is how a correct
model gets "fixed" into an incorrect one.

### Defects found and corrected during V0.2

Both were found by inspecting output rather than by a failing test, which is why
plotting a run is treated as instrumentation rather than decoration.

1. **Degenerate geometry.** Scenarios B, E and F originally started the target at the
   origin, which is where the radar sat. Bearing is undefined at zero range, and the
   first measurement of Scenario B read 0.89 m at a meaningless bearing. Trajectories
   were moved to hold the target between roughly 358 m and 447 m from the sensor, and
   a test now asserts that clearance.
2. **Clutter scattered outside the region of interest.** Maximum range was 5000 m
   while the target never exceeded 447 m, so false alarms spread across a disc the
   target never visited and data association would have been trivially easy. Scenario
   F would have produced a reassuring V0.5 result while testing nothing. Maximum range
   is now 1000 m.

### Not yet measured

- **SYS-005, SYS-006, SYS-007, SYS-012** — no tracker exists. Unchanged from V0.1.
- Position and velocity RMSE cannot be computed without an estimator to evaluate.

---

## V0.1 — 2026-09-15

**Commit under test:** `3db8640` (merged to `develop` as `9291fd1`)
**CI run:** [34915031256](https://github.com/tomas-mhareb/multi-sensor-target-tracker/actions/runs/34915031256)

### Unit tests

| Platform | Result | Duration |
|---|---|---|
| DEV-1 | 55 passed, 0 failed | 0.22 – 0.37 s over 3 runs |
| CI-1 | 55 passed, 0 failed | 0.32 s |

Identical test counts and outcomes on both platforms. Static analysis
(`ruff check`) and formatting (`ruff format --check`) pass on both, with zero
workflow annotations.

### Requirement verification

| ID | Requirement | Method | Result |
|---|---|---|---|
| SYS-001 | Scenarios defined by external configuration | Test | **Pass** |
| SYS-002 | At least 10 simultaneous targets | Test | **Pass** — Scenario C runs 10 targets over 601 timesteps, 6010 truth rows |
| SYS-003 | Bit-identical output for a given configuration | Test | **Pass** — see below |
| SYS-010 | CI builds and tests on Ubuntu per push and PR | Demonstration | **Pass** — run 34915031256, 23 s |

### Determinism (SYS-003)

Scenario A executed twice into separate output directories and compared byte for byte:

```
$ cmp data/runs/A_single_cv/truth.csv /tmp/mstt_rerun/truth.csv
(no output — files identical)

SHA-256: 75f57a5db285183e...
```

### Numerical verification

Scenario A places one target at the origin travelling at (8.0, 4.0) m/s for 60 s.
Closed-form endpoint: `x = 8.0 * 60 = 480 m`, `y = 4.0 * 60 = 240 m`.

| Quantity | Expected | Produced |
|---|---|---|
| Final `t_s` | 60.000000 | `60.000000` |
| Final `x_m` | 480.000000 | `480.000000` |
| Final `y_m` | 240.000000 | `240.000000` |
| Truth rows | 601 | 601 |

### Floating-point drift from stepwise propagation

The simulator advances state by applying the transition matrix once per timestep,
rather than propagating from the initial state by total elapsed time. Stepwise
propagation is required for the manoeuvring targets planned in later releases, but
it accumulates rounding error. Measured over Scenario A's 600 steps:

| Quantity | Value |
|---|---|
| Stepwise result | `480.00000000000466 m` |
| Closed-form result | `480.0 m` |
| Drift in x | `4.661e-12 m` |
| Drift in y | `2.331e-12 m` |
| Output resolution | `1e-6 m` |
| Drift as a fraction of resolution | `4.66e-06` |

The drift is roughly five orders of magnitude below the output format's resolution,
which is why it rounds away entirely and does not threaten SYS-003. It grows with
step count, so this figure should be re-measured if run durations increase
substantially.

### Not yet measured

- **SYS-007** (10 ms update cycle for 10 targets) — no tracker exists. Remains `Target`.
- **SYS-006** (NIS filter consistency) — no filter exists.
- Position RMSE, velocity RMSE, track continuity, false-track count (SYS-012) — no
  tracks exist. These require V0.3 at the earliest.
- CPU and memory utilization — not instrumented.

### Environment caveat

The development virtual environment links against the Homebrew Python framework,
so a `brew upgrade` changes the interpreter underneath it (3.13.7 to 3.13.15 was
observed during V0.1 setup). This affects reproducibility on DEV-1 only; CI-1 pins
its interpreter through `actions/setup-python`. The Docker environment planned for
V0.8 removes the discrepancy.
