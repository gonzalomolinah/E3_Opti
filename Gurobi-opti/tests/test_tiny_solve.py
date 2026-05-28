from __future__ import annotations

import pytest

gp = pytest.importorskip("gurobipy")
from gurobipy import GRB, GurobiError

from src.data import load_data
from src.model import build_model
from src.validate_data import validate_data


@pytest.mark.parametrize("path", ["data/instances/tiny.json", "data/csv/tiny"])
def test_tiny_instance_solves_if_gurobi_license_is_available(path):
    data = load_data(path)
    validation = validate_data(data)
    assert validation.ok

    try:
        model = build_model(data)
        model.Params.OutputFlag = 0
        model.optimize()
    except GurobiError as exc:
        pytest.skip(f"Gurobi unavailable or unlicensed: {exc}")

    assert model.Status == GRB.OPTIMAL
