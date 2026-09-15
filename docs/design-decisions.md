# Design Decisions

An append-only log of architectural decisions. Each entry records the context, the
options considered, the choice, and — most importantly — the reasoning, so that a
decision can be revisited when its assumptions change rather than treated as
permanent by default.

Entries are never deleted. A decision that is later reversed gets a new entry that
supersedes the old one, because the reversal and its cause are themselves useful
information.

---

## ADR-001 — The fusion engine is an orchestrator, not a pipeline stage

**Status:** Accepted · V0.1

**Context.** The initial concept placed fusion, data association, Kalman filtering,
and track management as four sequential stages, with fusion feeding association.

**Decision.** There is no separate fusion stage. `FusionEngine` owns the
timestamp-ordered measurement queue and the `TrackManager`, and drives one update
cycle per measurement:

1. predict all tracks forward to the measurement timestamp
2. gate and associate the measurement against the predicted tracks
3. update the matched track using that sensor's measurement model
4. track manager spawns, confirms, or deletes tracks

**Reasoning.** Fusion is not an operation performed on measurements before tracking;
it is the property that emerges when multiple sensors update shared track state
through their own measurement models. Modelling it as a pre-processing stage forces
sensors to be time-aligned and homogenized before use, which discards exactly the
per-sensor uncertainty structure that makes fusion worthwhile.

**Consequence.** Adding a sensor type means adding a measurement model, not a new
pipeline stage. Sensors at different rates require no special handling because the
cycle is driven by individual measurement timestamps.

---

## ADR-002 — Continuous integration from the first release, not the eighth

**Status:** Accepted · V0.1

**Context.** The original plan introduced automated testing and CI at V0.8. Primary
development happens on macOS; CON-002 requires Ubuntu.

**Decision.** CI runs from V0.1 and grows with the project: pytest and a linter at
V0.1, a C++ build and ctest at V0.3, sanitizers and static analysis at V0.8.

**Reasoning.** Two costs compound if CI is deferred. Platform divergence between the
macOS development machine and the Ubuntu target accumulates silently across eight
releases and must then be unwound all at once. And retrofitting test infrastructure
onto existing code is far more expensive than growing it alongside.

**Consequence.** SYS-010 is a V0.1 requirement.

---

## ADR-003 — The camera is a bearing-only sensor

**Status:** Accepted · V0.1 (implemented V0.9)

**Context.** Fusing a camera with a radar requires both to produce measurements
relatable to a common state. A monocular camera cannot measure range.

**Options.**

| Option | Assessment |
|---|---|
| Assume or invent a range for camera detections | Rejected — fabricates information the sensor does not carry, and any accuracy improvement would be an artifact of the assumption |
| Assume known target size and infer range from apparent size | Rejected — requires a target-size prior the system has no way to establish, and fails outright for unknown targets |
| Treat the camera as a bearing-only sensor | **Accepted** |

**Decision.** The camera produces an azimuth measurement derived from the detected
pixel column and known intrinsics:

```
theta_cam = atan2(u - cx, fx)
```

**Reasoning.** This is what the sensor physically measures. It also makes the two
sensors genuinely complementary rather than redundant: radar supplies range with
coarse bearing, the camera supplies precise bearing with no range. The resulting
improvement is real, physically explicable, and visible as an anisotropic reduction
in the covariance ellipse — which means it can be measured and defended rather than
asserted.

**Consequence.** Camera measurements cannot be converted to Cartesian, which forces
ADR-004. The camera operates in two modes that are never mixed in reported results:
*synthetic* (ground truth projected through known intrinsics, used for all metrics
and CI) and *recorded video* (OpenCV detection on real footage, used for
demonstration; reported in image-plane coordinates unless the lens field of view is
known).

---

## ADR-004 — Linear Kalman filter first, extended Kalman filter when required

**Status:** Accepted · V0.1 (KF at V0.3, EKF at V0.9)

**Context.** Radar measures range and bearing; the state is Cartesian. That
relationship is nonlinear.

**Options.**

| Option | Pros | Cons |
|---|---|---|
| Converted-measurement KF — convert polar to Cartesian outside the filter, rotate R accordingly | Simplest; the linear filter is learned with nothing hidden | Small bias at long range or high bearing noise; **cannot represent a bearing-only sensor** |
| Extended KF — retain polar measurements, linearize via Jacobian | Handles any nonlinear sensor including bearing-only | Jacobians are a known source of subtle error |
| Unscented KF | Best accuracy under strong nonlinearity | Unjustified complexity at current noise levels |

**Decision.** Converted-measurement linear KF at V0.3. Extended KF at V0.9, when the
camera is introduced.

**Reasoning.** With radar alone the converted-measurement filter is adequate, and it
allows the linear filter to be understood and verified in isolation. The bearing-only
camera then makes conversion impossible — an azimuth with no range cannot be expressed
in Cartesian coordinates — so the EKF is introduced because a requirement demands it,
not because it is more sophisticated.

**Consequence.** The EKF is validated against the linear KF on radar-only data before
the camera is enabled; agreement is required to within numerical tolerance.

---

## ADR-005 — Freeze the message schema; treat transports as adapters

**Status:** Accepted · V0.1 (file replay V0.1, UDP V0.9)

**Context.** Python simulation must deliver measurements to the C++ engine. Candidate
transports were files, TCP, UDP, and ZeroMQ.

**Decision.** Define the measurement schema first. File replay (JSONL) is the
canonical interface and is what CI executes. A UDP transport carrying the identical
schema is added at V0.9.

**Reasoning.** Transport was the wrong first question; the message contract is what
components actually depend on. File replay is deterministic and repeatable, which is
what makes scenario results reproducible and makes a failing run re-executable
identically while debugging.

UDP rather than TCP for the live path, because real sensor feeds are lossy datagram
streams and TCP's retransmission is actively harmful here — a radar return redelivered
200 ms late is worse than one that never arrives, and the tracker already handles
missed detections. ZeroMQ was rejected as an added dependency that would obscure the
socket handling this project intends to demonstrate.

**Consequence.** The tracking core is transport-agnostic: measurements may originate
from a file, a socket, or physical hardware without changes to the engine. This is
also the mechanism by which the optional hardware extension attaches.

---

## ADR-006 — The C++ engine is the product; Python is the test equipment

**Status:** Accepted · V0.1

**Decision.** Python implements the world simulator, sensor noise generation,
computer vision, metrics, and visualization. C++ implements the measurement models,
filter, association, track management, fusion, logging, and configuration.

**Reasoning.** This mirrors how software-in-the-loop environments are actually built:
the software under test is one program and the simulation environment is separate
infrastructure. It keeps the C++ focused on the real-time path.

Note the deliberate split of each sensor across both languages. The simulator
*generates* a noisy bearing (Python, test infrastructure); the filter *models* how a
bearing relates to state (C++, product code). Different responsibilities, correctly
separated.

**Consequence.** The Kalman filter is prototyped in Python for comprehension, its
output frozen as golden vectors under `tests/data/golden/`, and the prototype then
deleted. The C++ implementation is verified against those vectors, which is the same
technique used to verify hand-written flight code against a model. Two parallel
implementations are explicitly not maintained.

---

## ADR-007 — Pin C++ dependencies rather than use system packages

**Status:** Accepted · V0.3

**Context.** The C++ engine needs Eigen for linear algebra and GoogleTest for unit
tests. The development machine has Eigen 5.0.1 from Homebrew; Ubuntu's `libeigen3-dev`
is 3.4.x.

**Options.**

| Option | Assessment |
|---|---|
| `find_package` against whatever each platform provides | Rejected — bakes the macOS/Linux divergence that CI exists to catch directly into the build. A failure on one platform need not reproduce on the other |
| Vendor the sources into the repository | Rejected — large, obscures history, and updating becomes a manual merge |
| `FetchContent` pinned to a specific tag | **Accepted** |

**Decision.** Fetch Eigen 3.4.0 and GoogleTest v1.18.0 by pinned git tag, shallow
cloned, marked `SYSTEM`.

**Reasoning.** The Mac, the CI runner, and the V0.8 Docker image then compile
identical dependency sources, so a failure on one is reproducible on the others.
Eigen 3.4.0 rather than 5.x because it is what every apt package, reference, and
tutorial uses, which makes the project's build match what a reviewer expects.

The cost is a download on a cold build. CI caches it, keyed on the hash of the
declaration file, so the cache invalidates exactly when a version changes.

**Consequence.** `SYSTEM` is required, not optional. This project compiles its own
sources with `-Wold-style-cast`, `-Wconversion` and others that Eigen's internals
legitimately violate. Without `SYSTEM` the build fails inside a dependency we cannot
fix, and the only remedies would be weakening the warnings for our own code or
ignoring the output. Third-party headers are held to no warning standard precisely
because we cannot act on warnings they produce.

---

## ADR-008 — Verify the cross-language contract in both directions

**Status:** Accepted · V0.3

**Context.** ADR-006 established golden vectors: the Python implementation is frozen
to a committed file, and the C++ implementation is tested against it.

**Decision.** CI additionally regenerates the golden vectors and fails if they differ
from what is committed.

**Reasoning.** Testing C++ against the file alone leaves a hole. If the Python
implementation changes and the file is not regenerated, the C++ test still passes --
C++ still matches the old file -- while Python now disagrees with both. Every check
would be green with the two implementations silently divergent, which is the exact
mirrored-track failure the golden vectors exist to prevent.

Checking both halves gives `golden == Python` and `C++ == golden`, and therefore
`C++ == Python`.

**Consequence.** Changing either implementation requires regenerating the vectors and
confirming the other side still passes. That friction is the point: the two are a
contract, and a contract that can be changed unilaterally is not one.

**Amendment, same day.** The Python half was first implemented as a CI step that
regenerated the file and compared it byte for byte. It failed on the first run: numpy's
`hypot` differs by one unit in the last place between Apple's libm and glibc, so a range
of `561.30624241630869` on macOS is `561.30624241630858` on Linux. Bearings were
identical; only `hypot` differed.

IEEE-754 does not require bit-identical results from transcendental functions across
implementations, so a byte comparison of values written at full double precision tests
the C library rather than this project. The check is now a numerical comparison with a
tolerance of 1e-12, matching the tolerance the C++ side already used -- roughly ten
orders of magnitude above a ULP difference and ten below any convention error, which is
exactly the distinction the check needs to make. It also moved from a CI shell step into
`python/tests/test_golden_vectors.py`, so it runs locally rather than only on a runner.

The two tolerances must be kept equal. A tighter one on either side would reject
differences the other accepts.
