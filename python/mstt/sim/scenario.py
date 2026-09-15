"""Scenario configuration: loading, validation, and construction of a World.

Validation is deliberately strict. Unknown keys are rejected rather than ignored,
because a mistyped key in a lenient loader does not fail — it silently falls back
to a default. A scenario containing ``velocty_mps`` would produce a stationary
target, which is valid physics and therefore invisible at runtime. Failing at load
time turns a debugging session into an error message.
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from mstt.sim.target import Target
from mstt.sim.world import World


class ScenarioError(ValueError):
    """Raised when a scenario configuration is malformed.

    A distinct exception type so that callers — the CLI in particular — can report
    configuration problems as user errors with a clean message, rather than as an
    unhandled traceback that looks like a crash in the simulator.
    """


@dataclass(frozen=True)
class SimulationConfig:
    """Timing parameters for a scenario run."""

    duration_s: float
    timestep_s: float


@dataclass(frozen=True)
class Scenario:
    """A fully validated scenario, ready to be turned into a World."""

    name: str
    description: str
    simulation: SimulationConfig
    targets: tuple[Target, ...]

    @classmethod
    def from_yaml(cls, path: Path | str) -> Scenario:
        """Load and validate a scenario from a YAML file."""
        path = Path(path)
        try:
            raw = yaml.safe_load(path.read_text())
        except FileNotFoundError as exc:
            raise ScenarioError(f"scenario file not found: {path}") from exc
        except yaml.YAMLError as exc:
            raise ScenarioError(f"{path}: invalid YAML: {exc}") from exc

        if not isinstance(raw, Mapping):
            raise ScenarioError(f"{path}: top level must be a mapping, got {_type_name(raw)}")

        return cls.from_mapping(raw, source=str(path))

    @classmethod
    def from_mapping(cls, raw: Mapping, source: str = "<config>") -> Scenario:
        """Validate an already-parsed mapping and build a Scenario.

        Separated from :meth:`from_yaml` so that validation can be unit-tested
        directly against in-memory dictionaries, without a temporary file per case.
        """
        _check_keys(
            raw,
            required={"name", "simulation", "targets"},
            optional={"description"},
            context=source,
        )

        name = _require_str(raw, "name", source)
        description = str(raw.get("description", ""))

        sim_raw = raw["simulation"]
        if not isinstance(sim_raw, Mapping):
            raise ScenarioError(f"{source}: 'simulation' must be a mapping")
        _check_keys(
            sim_raw,
            required={"duration_s", "timestep_s"},
            optional=set(),
            context=f"{source}: simulation",
        )

        simulation = SimulationConfig(
            duration_s=_require_float(sim_raw, "duration_s", f"{source}: simulation"),
            timestep_s=_require_float(sim_raw, "timestep_s", f"{source}: simulation"),
        )
        if simulation.timestep_s <= 0.0:
            raise ScenarioError(
                f"{source}: simulation.timestep_s must be strictly positive, "
                f"got {simulation.timestep_s}"
            )
        if simulation.duration_s < 0.0:
            raise ScenarioError(
                f"{source}: simulation.duration_s must be non-negative, got {simulation.duration_s}"
            )

        targets_raw = raw["targets"]
        if not isinstance(targets_raw, list) or not targets_raw:
            raise ScenarioError(f"{source}: 'targets' must be a non-empty list")

        targets = tuple(
            _parse_target(entry, f"{source}: targets[{i}]") for i, entry in enumerate(targets_raw)
        )

        return cls(name=name, description=description, simulation=simulation, targets=targets)

    def build_world(self) -> World:
        """Construct the World this scenario describes."""
        return World(
            targets=list(self.targets),
            dt_s=self.simulation.timestep_s,
            duration_s=self.simulation.duration_s,
        )


def _parse_target(entry: object, context: str) -> Target:
    if not isinstance(entry, Mapping):
        raise ScenarioError(f"{context}: must be a mapping, got {_type_name(entry)}")

    _check_keys(
        entry, required={"id", "position_m", "velocity_mps"}, optional=set(), context=context
    )

    target_id = entry["id"]
    if not isinstance(target_id, int) or isinstance(target_id, bool):
        raise ScenarioError(f"{context}: 'id' must be an integer, got {target_id!r}")

    return Target.from_position_velocity(
        target_id=target_id,
        position_m=_require_pair(entry, "position_m", context),
        velocity_mps=_require_pair(entry, "velocity_mps", context),
    )


def _check_keys(mapping: Mapping, required: set[str], optional: set[str], context: str) -> None:
    """Reject missing required keys and any key that is not recognized.

    Both problems are reported together rather than bailing on the first. A typo
    produces both at once -- the intended key is missing *and* the misspelling is
    unrecognized -- and reporting only the missing half sends the reader looking for
    an absent key while the misspelled one sits in plain view. For the same reason a
    close match is suggested where one exists, which turns detection into diagnosis.
    """
    present = set(mapping.keys())
    allowed = sorted(required | optional)

    missing = required - present
    unknown = present - required - optional
    if not missing and not unknown:
        return

    problems = []
    if missing:
        problems.append(f"missing required key(s): {sorted(missing)}")
    if unknown:
        described = []
        for key in sorted(unknown):
            close = difflib.get_close_matches(str(key), allowed, n=1, cutoff=0.7)
            hint = f" (did you mean {close[0]!r}?)" if close else ""
            described.append(f"{key!r}{hint}")
        problems.append("unknown key(s): " + ", ".join(described))

    raise ScenarioError(f"{context}: {'; '.join(problems)}; allowed keys are {allowed}")


def _require_str(mapping: Mapping, key: str, context: str) -> str:
    value = mapping[key]
    if not isinstance(value, str) or not value.strip():
        raise ScenarioError(f"{context}: '{key}' must be a non-empty string, got {value!r}")
    return value


def _require_float(mapping: Mapping, key: str, context: str) -> float:
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScenarioError(f"{context}: '{key}' must be a number, got {value!r}")
    return float(value)


def _require_pair(mapping: Mapping, key: str, context: str) -> tuple[float, float]:
    value = mapping[key]
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise ScenarioError(f"{context}: '{key}' must be a list of two numbers, got {value!r}")

    items = list(value)
    if len(items) != 2:
        raise ScenarioError(f"{context}: '{key}' must have exactly 2 elements, got {len(items)}")
    for item in items:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ScenarioError(f"{context}: '{key}' elements must be numbers, got {item!r}")
    return float(items[0]), float(items[1])


def _type_name(value: object) -> str:
    return type(value).__name__
