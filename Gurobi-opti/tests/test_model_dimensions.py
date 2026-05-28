from __future__ import annotations

import pytest

gp = pytest.importorskip("gurobipy")

from src.data import load_data
from src.model import build_model


def _count_constraints(model, prefix: str) -> int:
    model.update()
    return sum(1 for constr in model.getConstrs() if constr.ConstrName.startswith(prefix))


def test_decision_variable_dimensions_match_formulation():
    data = load_data("data/instances/tiny.json")
    model = build_model(data)
    model.update()

    vars_ = model._vars
    assert len(vars_["x"]) == len(data.H) * len(data.G) * len(data.U) * len(data.T)
    assert len(vars_["I"]) == len(data.N) * len(data.G) * len(data.U) * len(data.T)
    assert len(vars_["y"]) == len(data.H) * len(data.G) * len(data.G) * len(data.U) * len(data.T)
    assert len(vars_["s"]) == len(data.H) * len(data.G) * len(data.T)
    assert len(vars_["w"]) == len(data.N) * len(data.G) * len(data.T)


def test_all_decision_variables_have_nonnegative_lower_bounds():
    data = load_data("data/instances/tiny.json")
    model = build_model(data)
    model.update()
    assert all(var.LB == 0 for var in model.getVars())


def test_all_decision_variables_are_integer():
    data = load_data("data/instances/tiny.json")
    model = build_model(data)
    model.update()
    assert all(var.VType == gp.GRB.INTEGER for var in model.getVars())


def test_constraint_families_have_expected_counts():
    data = load_data("data/instances/tiny.json")
    model = build_model(data)
    model.update()

    assert _count_constraints(model, "balance_hospital_u_menor_L") == len(data.H) * len(data.G) * (data.L - 1) * (len(data.T) - 1)
    assert _count_constraints(model, "balance_hospital_u_L") == len(data.H) * len(data.G) * (len(data.T) - 1)
    assert _count_constraints(model, "balance_banco_u_menor_L") == len(data.G) * (data.L - 1) * (len(data.T) - 1)
    assert _count_constraints(model, "balance_banco_u_L") == len(data.G) * (len(data.T) - 1)
    assert _count_constraints(model, "capacidad_almacenamiento") == len(data.N) * len(data.T)
    assert _count_constraints(model, "compatibilidad") == len(data.H) * len(data.G) * len(data.G) * len(data.U) * len(data.T)
    assert _count_constraints(model, "capacidad_transporte") == len(data.T)
    assert _count_constraints(model, "satisfaccion_demanda") == len(data.H) * len(data.G) * len(data.T)
    assert _count_constraints(model, "vencimiento_inicial") == len(data.N) * len(data.G)


def test_transfer_feasibility_constraints_only_for_u_leq_tau():
    data = load_data("data/instances/tiny.json")
    model = build_model(data)
    model.update()

    expected = sum(
        len(data.G) * len(data.T) * sum(1 for u in data.U if u <= data.travel_time[h])
        for h in data.H
    )
    assert _count_constraints(model, "factibilidad_traslado") == expected
