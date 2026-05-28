from __future__ import annotations

import copy
import math

from src.data import load_instance
from src.data import load_data
from src.validate_data import validate_instance_dict


TINY = "data/instances/tiny.json"
TINY_CSV = "data/csv/tiny"


def tiny_instance():
    return load_instance(TINY)


def assert_invalid(instance, expected: str) -> None:
    result = validate_instance_dict(instance)
    assert not result.ok
    assert any(expected in error for error in result.errors)


def test_valid_tiny_instance_passes_validation():
    result = validate_instance_dict(tiny_instance())
    assert result.ok


def test_valid_tiny_csv_instance_passes_validation():
    result = validate_instance_dict(load_instance(TINY_CSV))
    assert result.ok


def test_tiny_csv_loads_equivalent_data_to_json():
    json_data = load_data(TINY)
    csv_data = load_data(TINY_CSV)
    assert csv_data.H == json_data.H
    assert csv_data.G == json_data.G
    assert csv_data.T == json_data.T
    assert csv_data.U == json_data.U
    assert csv_data.N == json_data.N
    assert csv_data.demand == json_data.demand
    assert csv_data.donations == json_data.donations
    assert csv_data.initial_inventory == json_data.initial_inventory
    assert csv_data.capacity == json_data.capacity
    assert csv_data.travel_time == json_data.travel_time
    assert csv_data.compatible == json_data.compatible
    assert csv_data.use_penalty == json_data.use_penalty
    assert csv_data.substitution_penalty == json_data.substitution_penalty
    assert csv_data.max_transport == json_data.max_transport
    assert csv_data.big_m == json_data.big_m


def test_rejects_missing_indexed_parameter_entries():
    instance = tiny_instance()
    instance["parameters"]["demand"].pop()
    assert_invalid(instance, "demand missing required index")


def test_rejects_extra_indexed_parameter_entries_outside_sets():
    instance = tiny_instance()
    instance["parameters"]["donations"].append({"g": "A+", "t": 1, "value": 1})
    assert_invalid(instance, "donations has unexpected index")


def test_rejects_nan_none_and_non_numeric_values():
    instance = tiny_instance()
    instance["parameters"]["demand"][0]["value"] = math.nan
    assert_invalid(instance, "must be a nonnegative integer")

    instance = tiny_instance()
    instance["parameters"]["donations"][0]["value"] = "bad"
    assert_invalid(instance, "must be a nonnegative integer")


def test_rejects_negative_quantities_and_capacities():
    instance = tiny_instance()
    instance["parameters"]["storage_capacity"][0]["value"] = -1
    assert_invalid(instance, "must be a nonnegative integer")


def test_rejects_fractional_blood_unit_quantities():
    instance = tiny_instance()
    instance["parameters"]["demand"][0]["value"] = 1.5
    assert_invalid(instance, "must be a nonnegative integer")


def test_rejects_negative_penalties_and_use_costs():
    instance = tiny_instance()
    instance["parameters"]["expiration_penalty"] = -1
    assert_invalid(instance, "expiration_penalty must be nonnegative")


def test_rejects_invalid_compatibility_values():
    instance = tiny_instance()
    instance["parameters"]["compatibility"][0]["value"] = 2
    assert_invalid(instance, "must be 0 or 1")


def test_rejects_negative_substitution_penalty():
    instance = tiny_instance()
    instance["parameters"]["substitution_penalty"] = [
        {"donor": donor, "receiver": receiver, "value": 0 if donor == receiver else 5}
        for donor in instance["sets"]["G"]
        for receiver in instance["sets"]["G"]
    ]
    instance["parameters"]["substitution_penalty"][1]["value"] = -1
    assert_invalid(instance, "substitution_penalty")


def test_travel_time_greater_than_or_equal_lifetime_warns():
    instance = tiny_instance()
    instance["parameters"]["travel_time"][0]["value"] = instance["sets"]["L"]
    result = validate_instance_dict(instance)
    assert result.ok
    assert any("all shipments to this hospital are blocked" in warning for warning in result.warnings)


def test_rejects_insufficient_big_m():
    instance = tiny_instance()
    instance["parameters"]["big_m"] = 1
    assert_invalid(instance, "big_m must be at least")


def test_rejects_c_not_matching_compatibility_matrix():
    instance = tiny_instance()
    instance["sets"]["C"] = copy.deepcopy(instance["sets"]["C"][:-1])
    assert_invalid(instance, "Set C must match compatibility")
