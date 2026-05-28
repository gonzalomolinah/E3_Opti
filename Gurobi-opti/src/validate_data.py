from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Iterable

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import Data, data_from_instance, load_instance


@dataclass(frozen=True)
class ValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _is_nonnegative_integer_value(value: Any) -> bool:
    return _is_number(value) and value >= 0 and float(value).is_integer()


def _record_key(record: dict[str, Any], fields: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(record.get(field) for field in fields)


def _check_unique_records(
    errors: list[str],
    records: list[dict[str, Any]],
    fields: tuple[str, ...],
    name: str,
) -> None:
    seen: set[tuple[Any, ...]] = set()
    for record in records:
        key = _record_key(record, fields)
        if key in seen:
            errors.append(f"{name} has duplicate index {key}")
        seen.add(key)


def _check_record_values(
    errors: list[str],
    records: list[dict[str, Any]],
    name: str,
    *,
    integer: bool = False,
    binary: bool = False,
) -> None:
    for record in records:
        value = record.get("value")
        if binary:
            if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1):
                errors.append(f"{name}{record} must be 0 or 1")
            continue
        if integer:
            if not _is_nonnegative_integer_value(value):
                errors.append(f"{name}{record} must be a nonnegative integer")
            continue
        if not _is_number(value):
            errors.append(f"{name}{record} must be a finite number")
        elif value < 0:
            errors.append(f"{name}{record} must be nonnegative")


def _check_complete_indices(
    errors: list[str],
    actual: Iterable[tuple[Any, ...]],
    expected: Iterable[tuple[Any, ...]],
    name: str,
) -> None:
    actual_set = set(actual)
    expected_set = set(expected)
    for key in sorted(expected_set - actual_set):
        errors.append(f"{name} missing required index {key}")
    for key in sorted(actual_set - expected_set):
        errors.append(f"{name} has unexpected index {key}")


def _check_nonnegative_mapping(
    errors: list[str],
    mapping: dict[Any, float],
    name: str,
) -> None:
    for key, value in mapping.items():
        if not _is_number(value):
            errors.append(f"{name}{key} must be a finite number")
        elif value < 0:
            errors.append(f"{name}{key} must be nonnegative")


def validate_instance_dict(instance: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    for section in ("metadata", "sets", "parameters"):
        if section not in instance:
            errors.append(f"Missing top-level section {section}")
    if errors:
        return ValidationResult(errors, warnings)

    metadata = instance["metadata"]
    sets = instance["sets"]
    params = instance["parameters"]

    if metadata.get("synthetic") is not True:
        errors.append("metadata.synthetic must be true for generated datasets")

    required_sets = ("H", "G", "T", "L", "U", "N", "C")
    required_params = (
        "demand",
        "donations",
        "initial_inventory",
        "storage_capacity",
        "travel_time",
        "shortage_penalty",
        "expiration_penalty",
        "compatibility",
        "use_penalty",
        "big_m",
        "max_transport",
    )
    for name in required_sets:
        if name not in sets:
            errors.append(f"Missing set {name}")
    for name in required_params:
        if name not in params:
            errors.append(f"Missing parameter {name}")
    if errors:
        return ValidationResult(errors, warnings)

    for set_name in ("H", "G", "T", "U", "N"):
        values = sets[set_name]
        if not isinstance(values, list) or not values:
            errors.append(f"Set {set_name} must be a nonempty list")
        elif len(values) != len(set(values)):
            errors.append(f"Set {set_name} must not contain duplicates")

    if not isinstance(sets["L"], int) or sets["L"] < 1:
        errors.append("L must be a positive integer")
    if errors:
        return ValidationResult(errors, warnings)

    H = list(sets["H"])
    G = list(sets["G"])
    T = [int(t) for t in sets["T"]]
    U = [int(u) for u in sets["U"]]
    L = int(sets["L"])
    N = list(sets["N"])

    if N != ["0"] + H:
        errors.append('N must equal ["0"] + H')
    if T != list(range(1, max(T) + 1)):
        errors.append("T must be contiguous and equal to [1, ..., Tmax]")
    if U != list(range(1, L + 1)):
        errors.append("U must equal [1, ..., L]")

    for name, fields in (
        ("demand", ("h", "g", "t")),
        ("donations", ("g", "t")),
        ("initial_inventory", ("n", "g")),
        ("storage_capacity", ("n",)),
        ("travel_time", ("h",)),
        ("compatibility", ("donor", "receiver")),
        ("substitution_penalty", ("donor", "receiver")),
        ("use_penalty", ("g",)),
        ("max_transport", ("t",)),
    ):
        if name not in params:
            continue
        if not isinstance(params[name], list):
            errors.append(f"{name} must be a list of records")
        else:
            _check_unique_records(errors, params[name], fields, name)
    if errors:
        return ValidationResult(errors, warnings)

    for name in ("demand", "donations", "initial_inventory", "storage_capacity", "use_penalty", "max_transport"):
        _check_record_values(
            errors,
            params[name],
            name,
            integer=name
            in ("demand", "donations", "initial_inventory", "storage_capacity", "max_transport"),
        )
    _check_record_values(errors, params["travel_time"], "travel_time", integer=True)
    _check_record_values(errors, params["compatibility"], "compatibility", binary=True)
    if "substitution_penalty" in params:
        _check_record_values(errors, params["substitution_penalty"], "substitution_penalty")

    for scalar_name in ("shortage_penalty", "expiration_penalty", "big_m"):
        value = params[scalar_name]
        if not _is_number(value):
            errors.append(f"{scalar_name} must be a finite number")
        elif scalar_name == "big_m" and value <= 0:
            errors.append("big_m must be positive")
        elif scalar_name != "big_m" and value < 0:
            errors.append(f"{scalar_name} must be nonnegative")
    if errors:
        return ValidationResult(errors, warnings)

    data = data_from_instance(instance)

    _check_complete_indices(errors, data.demand.keys(), product(H, G, T), "demand")
    _check_complete_indices(errors, data.donations.keys(), product(G, T), "donations")
    _check_complete_indices(errors, data.initial_inventory.keys(), product(N, G), "initial_inventory")
    _check_complete_indices(errors, [(n,) for n in data.capacity.keys()], [(n,) for n in N], "storage_capacity")
    _check_complete_indices(errors, [(h,) for h in data.travel_time.keys()], [(h,) for h in H], "travel_time")
    _check_complete_indices(errors, data.compatible.keys(), product(G, G), "compatibility")
    _check_complete_indices(errors, data.substitution_penalty.keys(), product(G, G), "substitution_penalty")
    _check_complete_indices(errors, [(g,) for g in data.use_penalty.keys()], [(g,) for g in G], "use_penalty")
    _check_complete_indices(errors, [(t,) for t in data.max_transport.keys()], [(t,) for t in T], "max_transport")
    if errors:
        return ValidationResult(errors, warnings)

    _check_nonnegative_mapping(errors, data.demand, "demand")
    _check_nonnegative_mapping(errors, data.donations, "donations")
    _check_nonnegative_mapping(errors, data.initial_inventory, "initial_inventory")
    _check_nonnegative_mapping(errors, data.capacity, "storage_capacity")
    _check_nonnegative_mapping(errors, data.use_penalty, "use_penalty")
    _check_nonnegative_mapping(errors, data.substitution_penalty, "substitution_penalty")
    _check_nonnegative_mapping(errors, data.max_transport, "max_transport")

    for h, tau in data.travel_time.items():
        if not isinstance(tau, int) or tau < 0:
            errors.append(f"travel_time[{h}] must be a nonnegative integer")
        elif tau >= L:
            warnings.append(
                f"travel_time[{h}] >= L; all shipments to this hospital are blocked by u <= tau[h]"
            )

    for key, value in data.compatible.items():
        if value not in (0, 1):
            errors.append(f"compatibility{key} must be 0 or 1")
    if errors:
        return ValidationResult(errors, warnings)

    for name, value in (
        ("shortage_penalty", data.shortage_penalty),
        ("expiration_penalty", data.expiration_penalty),
        ("big_m", data.big_m),
    ):
        if not _is_number(value):
            errors.append(f"{name} must be a finite number")
        elif name == "big_m" and value <= 0:
            errors.append("big_m must be positive")
        elif name != "big_m" and value < 0:
            errors.append(f"{name} must be nonnegative")

    max_hospital_period_demand = max(
        (sum(data.demand[h, g, t] for g in G) for h in H for t in T),
        default=0,
    )
    if data.big_m < max_hospital_period_demand:
        errors.append(
            "big_m must be at least the maximum total demand by hospital-period "
            f"({max_hospital_period_demand})"
        )

    compatible_pairs = {(r["donor"], r["receiver"]) for r in sets["C"]}
    matrix_pairs = {key for key, value in data.compatible.items() if value == 1}
    if compatible_pairs != matrix_pairs:
        errors.append("Set C must match compatibility entries with value 1")

    for n in N:
        initial_total = sum(data.initial_inventory[n, g] for g in G)
        if initial_total > data.capacity[n]:
            warnings.append(
                f"initial inventory at node {n} exceeds storage capacity and may make period 1 infeasible"
            )

    for h in H:
        avg_daily_demand = sum(data.demand[h, g, t] for g in G for t in T) / len(T)
        if avg_daily_demand > 0 and data.capacity[h] > 10 * avg_daily_demand:
            warnings.append(
                f"capacity at hospital {h} exceeds 10 days of average demand; expiration risk may be high"
            )

    return ValidationResult(errors, warnings)


def validate_data(data: Data) -> ValidationResult:
    instance = {
        "metadata": data.metadata,
        "sets": {
            "H": data.H,
            "G": data.G,
            "T": data.T,
            "L": data.L,
            "U": data.U,
            "N": data.N,
            "C": [
                {"donor": donor, "receiver": receiver}
                for (donor, receiver), value in data.compatible.items()
                if value == 1
            ],
        },
        "parameters": {
            "demand": [
                {"h": h, "g": g, "t": t, "value": value}
                for (h, g, t), value in data.demand.items()
            ],
            "donations": [
                {"g": g, "t": t, "value": value}
                for (g, t), value in data.donations.items()
            ],
            "initial_inventory": [
                {"n": n, "g": g, "value": value}
                for (n, g), value in data.initial_inventory.items()
            ],
            "storage_capacity": [{"n": n, "value": value} for n, value in data.capacity.items()],
            "travel_time": [{"h": h, "value": value} for h, value in data.travel_time.items()],
            "shortage_penalty": data.shortage_penalty,
            "expiration_penalty": data.expiration_penalty,
            "compatibility": [
                {"donor": donor, "receiver": receiver, "value": value}
                for (donor, receiver), value in data.compatible.items()
            ],
            "use_penalty": [{"g": g, "value": value} for g, value in data.use_penalty.items()],
            "substitution_penalty": [
                {"donor": donor, "receiver": receiver, "value": value}
                for (donor, receiver), value in data.substitution_penalty.items()
            ],
            "big_m": data.big_m,
            "max_transport": [{"t": t, "value": value} for t, value in data.max_transport.items()],
        },
    }
    return validate_instance_dict(instance)


def validate_file(path: str | Path) -> ValidationResult:
    return validate_instance_dict(load_instance(path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a JSON instance file or CSV instance directory.")
    parser.add_argument("instance", help="Path to data/instances/*.json or a CSV instance directory")
    parser.add_argument("--json", action="store_true", help="Print validation result as JSON")
    args = parser.parse_args()

    result = validate_file(args.instance)
    if args.json:
        print(json.dumps({"errors": result.errors, "warnings": result.warnings}, indent=2))
    else:
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        if result.ok:
            print("Validation passed")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
