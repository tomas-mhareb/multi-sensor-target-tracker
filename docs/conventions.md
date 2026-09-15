# Conventions

**Status:** normative. Every module in this repository conforms to this document.
If code and this document disagree, the code is wrong.

This file exists because coordinate-frame and unit mismatches are the most common
and most expensive class of bug in sensor software. They do not crash; they produce
confident, plausible, wrong answers. Fixing the convention once, here, is far
cheaper than debugging a mirrored track three weeks from now.

---

## 1. World frame

A single 2D Cartesian frame, right-handed, used by every component.

```
        y (North, +m)
        ^
        |
        |        * target
        |      /
        |    /  r
        |  /
        | / theta
        +-------------------> x (East, +m)
      origin
   (surveillance site)
```

| Property | Value |
|---|---|
| Origin | The surveillance site — by definition the radar's phase centre |
| `x` | East, metres, positive East |
| `y` | North, metres, positive North |
| Handedness | Right-handed |
| 3D extension | Add `z` = Up, metres. This is the ENU (East-North-Up) convention |

**Why ENU:** it is the standard local-tangent-plane frame in navigation and robotics,
and it extends to 3D by appending a coordinate rather than by renaming the existing
ones. 3D tracking is a post-V1.0 goal (§36); choosing ENU now means that upgrade does
not invalidate any 2D code or recorded data.

## 2. Angles

**Canonical convention: counter-clockwise from the +x (East) axis.**

| Property | Value |
|---|---|
| Zero | +x axis (East) |
| Positive direction | Counter-clockwise (East → North is +90°) |
| Internal representation | radians, `double` |
| Wrapped range | `[-pi, +pi]` (closed; `-pi` and `+pi` both denote due West) |
| File / config representation | degrees, in `(-180, +180]` |

This is exactly what `atan2(y, x)` returns, in exactly that range. That is the whole
justification: the tracker's measurement models and their Jacobians are built out of
`atan2`, `sin`, and `cos`, and any other convention would require a conversion at every
one of those call sites. Conversions you perform hundreds of times are conversions you
will eventually forget once.

### Relationship to compass bearing

Operational radar systems normally report **compass bearing**: clockwise from North,
in `[0, 360)`. This project does not use that internally. The conversion, should real
sensor data ever be ingested, is:

```
bearing_compass_deg = (90 - theta_math_deg) mod 360
theta_math_deg      = (90 - bearing_compass_deg) mod 360   # same formula, self-inverse
```

The conversion belongs in an input adapter at the boundary and nowhere else.

### Angle wrapping

Angular differences must always be wrapped before use — particularly the Kalman filter
innovation, where an unwrapped difference across the `±pi` discontinuity produces an
error of nearly `2*pi` and will destroy a track in one update.

```
wrap(a) = atan2(sin(a), cos(a))
```

## 3. Units

SI throughout. No exceptions, no implicit scaling.

| Quantity | Unit | Name suffix |
|---|---|---|
| Position | metre | `_m` |
| Velocity | metre/second | `_mps` |
| Acceleration | metre/second² | `_mps2` |
| Time | second | `_s` |
| Angle (internal) | radian | `_rad` |
| Angle (files, config) | degree | `_deg` |
| Angular rate | radian/second | `_radps` |

**Rule: every identifier carrying a dimensioned quantity states its unit in its name.**
`range_m`, `bearing_deg`, `dt_s`, `vx_mps`. Never a bare `x`, `dt`, or `bearing`.

This is deliberately slightly verbose. The cost is a few extra characters; the benefit
is that a unit error becomes visible at the point of use, during code review, without
having to trace a variable back to its definition.

Degrees appear only in files a human reads or writes. The boundary is the parser.

## 4. Time

| Property | Value |
|---|---|
| Simulation time | seconds, `float64`, starts at `t = 0.0` |
| Ordering authority | the `t_s` field — **never** file position or arrival order |
| Wall-clock time | tracked separately, used only for performance measurement |

**Simulation time and wall-clock time are strictly separate concepts.** The tracking
engine advances on measurement timestamps and never sleeps, which keeps tests fast and
deterministic. Throughput and latency are measured independently, by timing the
processing of each cycle. Conflating the two makes a system that cannot be tested
quickly and whose performance claims mean nothing.

## 5. Identifiers

| Identifier | Owner | Rule |
|---|---|---|
| `target_id` | Scenario config | Integer, assigned by the author, stable for the run. Ground truth only |
| `sensor_id` | Scenario config | String, e.g. `radar_0`, `camera_0` |
| `track_id` | Tracker | Integer, monotonically increasing, **never reused** after deletion |

**`track_id` is not `target_id` and must never be assumed equal to it.** The tracker has
no access to ground truth; it invents track IDs as it goes. Evaluating tracking accuracy
therefore requires an explicit truth-to-track assignment step, computed after the run.
Code that indexes ground truth by `track_id` is measuring nothing and is a bug.

## 6. Data schemas

### 6.1 Ground truth — `truth.csv` (V0.1)

CSV with a header row, one row per target per timestep, ordered by `t_s` then `target_id`.

```
t_s,target_id,x_m,y_m,vx_mps,vy_mps
0.000000,1,0.000000,0.000000,8.000000,4.000000
0.100000,1,0.800000,0.400000,8.000000,4.000000
```

All floating-point fields are written with **exactly 6 decimal places**. Fixed-width
formatting is what makes SYS-003 (bit-identical reruns) mechanically checkable — a
byte comparison of two runs either matches or it does not.

Later schemas (`measurements.jsonl`, `tracks.jsonl`) are defined when the components
that produce them are built, in V0.2 and V0.3.

### 6.2 Run directory layout

Every scenario run writes to its own directory under `data/runs/`, which is
git-ignored because it is a build product reproducible from config.

```
data/runs/<scenario_name>/
  truth.csv           # V0.1  ground truth from the simulator
  measurements.jsonl  # V0.2  noisy sensor measurements
  tracks.jsonl        # V0.3  tracker output
  metrics.json        # V0.8  computed performance metrics
  run.log             # structured log
```

## 7. Worked example

A target at `x = 100 m`, `y = 200 m`, observed from a radar at the origin:

| Quantity | Value |
|---|---|
| `range_m` | `sqrt(100^2 + 200^2)` = `223.6068` |
| `bearing_deg` (this project) | `atan2(200, 100)` = `63.4349` |
| `bearing_compass_deg` (not used here) | `(90 - 63.4349) mod 360` = `26.5651` |

Any implementation that reports `26.57` where this table says `63.43` has a convention
bug, not a noise realization.
