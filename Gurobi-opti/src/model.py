from __future__ import annotations

import gurobipy as gp
from gurobipy import GRB

from src.data import Data


def build_model(data: Data) -> gp.Model:
    H, G, T, U, N = data.H, data.G, data.T, data.U, data.N
    L = data.L

    model = gp.Model("distribucion_sangre_entrega_3")

    x = model.addVars(H, G, U, T, vtype=GRB.INTEGER, lb=0, name="x")
    inv = model.addVars(N, G, U, T, vtype=GRB.INTEGER, lb=0, name="I")
    y = model.addVars(H, G, G, U, T, vtype=GRB.INTEGER, lb=0, name="y")
    shortage = model.addVars(H, G, T, vtype=GRB.INTEGER, lb=0, name="s")
    expired = model.addVars(N, G, T, vtype=GRB.INTEGER, lb=0, name="w")

    model.setObjective(
        gp.quicksum(
            (
                (L - u)
                + data.travel_time[h]
                + data.use_penalty[g]
                + data.substitution_penalty[g, gp_]
            )
            * y[h, g, gp_, u, t]
            for t in T
            for h in H
            for g in G
            for gp_ in G
            for u in U
        )
        + data.shortage_penalty
        * gp.quicksum(shortage[h, g, t] for h in H for g in G for t in T)
        + data.expiration_penalty
        * gp.quicksum(expired[n, g, t] for n in N for g in G for t in T),
        GRB.MINIMIZE,
    )

    first_t = min(T)
    later_t = [t for t in T if t != first_t]

    model.addConstrs(
        (
            inv[h, g, u, t]
            == inv[h, g, u + 1, t - 1] + x[h, g, u, t]
            - gp.quicksum(y[h, g, gp_, u, t] for gp_ in G)
            for h in H
            for g in G
            for u in U
            if u < L
            for t in later_t
        ),
        name="balance_hospital_u_menor_L",
    )

    model.addConstrs(
        (
            inv[h, g, L, t]
            == x[h, g, L, t] - gp.quicksum(y[h, g, gp_, L, t] for gp_ in G)
            for h in H
            for g in G
            for t in later_t
        ),
        name="balance_hospital_u_L",
    )

    model.addConstrs(
        (
            inv["0", g, u, t]
            == inv["0", g, u + 1, t - 1] - gp.quicksum(x[h, g, u, t] for h in H)
            for g in G
            for u in U
            if u < L
            for t in later_t
        ),
        name="balance_banco_u_menor_L",
    )

    model.addConstrs(
        (
            inv["0", g, L, t]
            == data.donations[g, t] - gp.quicksum(x[h, g, L, t] for h in H)
            for g in G
            for t in later_t
        ),
        name="balance_banco_u_L",
    )

    model.addConstrs(
        (
            inv[h, g, L, first_t]
            == data.initial_inventory[h, g] + x[h, g, L, first_t]
            - gp.quicksum(y[h, g, gp_, L, first_t] for gp_ in G)
            for h in H
            for g in G
        ),
        name="balance_inicial_hospital",
    )
    model.addConstrs(
        (
            inv["0", g, L, first_t]
            == data.initial_inventory["0", g] + data.donations[g, first_t]
            - gp.quicksum(x[h, g, L, first_t] for h in H)
            for g in G
        ),
        name="balance_inicial_banco",
    )
    model.addConstrs(
        (
            inv[n, g, u, first_t] == 0
            for n in N
            for g in G
            for u in U
            if u < L
        ),
        name="inventario_inicial_u_menor_L",
    )
    model.addConstrs(
        (
            x[h, g, u, first_t] == 0
            for h in H
            for g in G
            for u in U
            if u < L
        ),
        name="despacho_inicial_u_menor_L",
    )
    model.addConstrs(
        (
            y[h, g, gp_, u, first_t] == 0
            for h in H
            for g in G
            for gp_ in G
            for u in U
            if u < L
        ),
        name="uso_inicial_u_menor_L",
    )

    model.addConstrs(
        (
            x[h, g, u, t] == 0
            for h in H
            for g in G
            for u in U
            for t in T
            if u <= data.travel_time[h]
        ),
        name="factibilidad_traslado",
    )

    model.addConstrs(
        (
            gp.quicksum(inv[n, g, u, t] for g in G for u in U) <= data.capacity[n]
            for n in N
            for t in T
        ),
        name="capacidad_almacenamiento",
    )

    model.addConstrs(
        (
            expired[h, g, t] == inv[h, g, 1, t - 1]
            for h in H
            for g in G
            for t in later_t
        ),
        name="vencimiento_hospital",
    )
    model.addConstrs(
        (
            expired["0", g, t] == inv["0", g, 1, t - 1]
            for g in G
            for t in later_t
        ),
        name="vencimiento_banco",
    )
    model.addConstrs(
        (expired[n, g, first_t] == 0 for n in N for g in G),
        name="vencimiento_inicial",
    )

    model.addConstrs(
        (
            y[h, g, gp_, u, t] <= data.big_m * data.compatible[g, gp_]
            for h in H
            for g in G
            for gp_ in G
            for u in U
            for t in T
        ),
        name="compatibilidad",
    )

    model.addConstrs(
        (
            gp.quicksum(x[h, g, u, t] for h in H for g in G for u in U)
            <= data.max_transport[t]
            for t in T
        ),
        name="capacidad_transporte",
    )

    model.addConstrs(
        (
            gp.quicksum(y[h, g, gp_, u, t] for g in G for u in U)
            + shortage[h, gp_, t]
            == data.demand[h, gp_, t]
            for h in H
            for gp_ in G
            for t in T
        ),
        name="satisfaccion_demanda",
    )

    model._vars = {
        "x": x,
        "I": inv,
        "y": y,
        "s": shortage,
        "w": expired,
    }
    return model


def solution_totals(model: gp.Model, data: Data) -> dict[str, float]:
    vars_ = model._vars
    return {
        "shortage": sum(vars_["s"][h, g, t].X for h in data.H for g in data.G for t in data.T),
        "expired": sum(vars_["w"][n, g, t].X for n in data.N for g in data.G for t in data.T),
        "shipped": sum(vars_["x"][h, g, u, t].X for h in data.H for g in data.G for u in data.U for t in data.T),
        "used": sum(
            vars_["y"][h, donor, receiver, u, t].X
            for h in data.H
            for donor in data.G
            for receiver in data.G
            for u in data.U
            for t in data.T
        ),
    }


def solution_metrics(model: gp.Model, data: Data) -> dict[str, object]:
    vars_ = model._vars
    x = vars_["x"]
    inv = vars_["I"]
    y = vars_["y"]
    shortage = vars_["s"]
    expired = vars_["w"]

    last_t = max(data.T)
    total_demand = sum(data.demand[h, g, t] for h in data.H for g in data.G for t in data.T)
    total_transport_capacity = sum(data.max_transport[t] for t in data.T)

    metrics: dict[str, object] = {
        "total_demand": total_demand,
        "total_transport_capacity": total_transport_capacity,
        "shortage_by_hospital": {h: 0.0 for h in data.H},
        "shortage_by_type": {g: 0.0 for g in data.G},
        "shortage_by_period": {t: 0.0 for t in data.T},
        "expired_by_node": {n: 0.0 for n in data.N},
        "expired_by_type": {g: 0.0 for g in data.G},
        "shipped_by_hospital": {h: 0.0 for h in data.H},
        "shipment_by_period": {t: 0.0 for t in data.T},
        "substitution_by_pair": {},
        "final_inventory_by_node": {n: 0.0 for n in data.N},
        "final_inventory_by_type": {g: 0.0 for g in data.G},
    }

    totals = {
        "shortage": 0.0,
        "expired": 0.0,
        "shipped": 0.0,
        "used": 0.0,
        "exact_match_use": 0.0,
        "substitution_use": 0.0,
        "final_inventory": 0.0,
        "saturated_transport_days": 0.0,
    }
    objective = {
        "age": 0.0,
        "travel": 0.0,
        "use_penalty": 0.0,
        "substitution": 0.0,
        "shortage": 0.0,
        "expiration": 0.0,
    }

    for h in data.H:
        for g in data.G:
            for t in data.T:
                value = shortage[h, g, t].X
                totals["shortage"] += value
                metrics["shortage_by_hospital"][h] += value
                metrics["shortage_by_type"][g] += value
                metrics["shortage_by_period"][t] += value

    for n in data.N:
        for g in data.G:
            for t in data.T:
                value = expired[n, g, t].X
                totals["expired"] += value
                metrics["expired_by_node"][n] += value
                metrics["expired_by_type"][g] += value

    for h in data.H:
        for g in data.G:
            for u in data.U:
                for t in data.T:
                    value = x[h, g, u, t].X
                    totals["shipped"] += value
                    metrics["shipped_by_hospital"][h] += value
                    metrics["shipment_by_period"][t] += value

    for t, value in metrics["shipment_by_period"].items():
        if value >= data.max_transport[t] - 1e-6:
            totals["saturated_transport_days"] += 1.0

    for n in data.N:
        for g in data.G:
            for u in data.U:
                value = inv[n, g, u, last_t].X
                totals["final_inventory"] += value
                metrics["final_inventory_by_node"][n] += value
                metrics["final_inventory_by_type"][g] += value

    substitution_by_pair: dict[tuple[str, str], float] = {}
    for h in data.H:
        for donor in data.G:
            for receiver in data.G:
                for u in data.U:
                    for t in data.T:
                        value = y[h, donor, receiver, u, t].X
                        totals["used"] += value
                        objective["age"] += (data.L - u) * value
                        objective["travel"] += data.travel_time[h] * value
                        objective["use_penalty"] += data.use_penalty[donor] * value
                        objective["substitution"] += data.substitution_penalty[donor, receiver] * value
                        if donor == receiver:
                            totals["exact_match_use"] += value
                        else:
                            totals["substitution_use"] += value
                            key = (donor, receiver)
                            substitution_by_pair[key] = substitution_by_pair.get(key, 0.0) + value

    objective["shortage"] = data.shortage_penalty * totals["shortage"]
    objective["expiration"] = data.expiration_penalty * totals["expired"]

    metrics["totals"] = totals
    metrics["objective"] = objective
    metrics["substitution_by_pair"] = substitution_by_pair
    return metrics


def _pct(numerator: float, denominator: float) -> float:
    return 100 * numerator / denominator if denominator else 0.0


def _print_positive_map(title: str, values: dict, limit: int | None = None) -> None:
    positives = [(key, value) for key, value in values.items() if value > 1e-6]
    positives.sort(key=lambda item: item[1], reverse=True)
    if limit is not None:
        positives = positives[:limit]
    print(f"\n{title}:")
    if not positives:
        print("  Sin valores positivos.")
        return
    for key, value in positives:
        print(f"  {key}: {value:.2f}")


def print_solution(
    model: gp.Model,
    data: Data,
    include_details: bool = True,
    include_report: bool = False,
) -> None:
    metrics = solution_metrics(model, data)
    totals = metrics["totals"]
    objective = metrics["objective"]
    total_demand = metrics["total_demand"]
    total_transport_capacity = metrics["total_transport_capacity"]
    satisfied = total_demand - totals["shortage"]
    avg_daily_demand = total_demand / len(data.T) if data.T else 0.0
    final_inventory_days = totals["final_inventory"] / avg_daily_demand if avg_daily_demand else 0.0

    print(f"Valor objetivo: {model.ObjVal:.2f}")
    print(f"Demanda total: {total_demand:.2f}")
    print(f"Demanda satisfecha: {satisfied:.2f}")
    print(f"Demanda insatisfecha total: {totals['shortage']:.2f}")
    print(f"Fill rate: {_pct(satisfied, total_demand):.2f}%")
    print(f"Sangre vencida total: {totals['expired']:.2f}")
    print(f"Wastage / uso: {_pct(totals['expired'], totals['used']):.2f}%")
    print(f"Wastage / demanda: {_pct(totals['expired'], total_demand):.2f}%")
    print(f"Despachos totales: {totals['shipped']:.2f}")
    print(f"Uso total: {totals['used']:.2f}")
    print(f"Inventario final total: {totals['final_inventory']:.2f}")
    print(f"Inventario final en dias de demanda promedio: {final_inventory_days:.2f}")
    print(f"Uso mismo tipo: {totals['exact_match_use']:.2f}")
    print(f"Uso por sustitucion compatible: {totals['substitution_use']:.2f}")
    print(f"Tasa de sustitucion: {_pct(totals['substitution_use'], totals['used']):.2f}%")
    print(f"Capacidad transporte usada: {_pct(totals['shipped'], total_transport_capacity):.2f}%")
    print(f"Dias con transporte saturado: {totals['saturated_transport_days']:.0f} de {len(data.T)}")

    print("\nDescomposicion objetivo:")
    print(f"  Edad de sangre usada: {objective['age']:.2f}")
    print(f"  Traslado: {objective['travel']:.2f}")
    print(f"  Penalizacion por tipo usado: {objective['use_penalty']:.2f}")
    print(f"  Penalizacion por sustitucion: {objective['substitution']:.2f}")
    print(f"  Demanda insatisfecha: {objective['shortage']:.2f}")
    print(f"  Vencimiento: {objective['expiration']:.2f}")

    if "O-" in data.G:
        o_neg_total = sum(
            model._vars["y"][h, "O-", receiver, u, t].X
            for h in data.H
            for receiver in data.G
            for u in data.U
            for t in data.T
        )
        o_neg_for_o_neg = sum(
            model._vars["y"][h, "O-", "O-", u, t].X
            for h in data.H
            for u in data.U
            for t in data.T
        )
        print("\nUso O-:")
        print(f"  Uso total O-: {o_neg_total:.2f}")
        print(f"  O- usado para O-: {o_neg_for_o_neg:.2f}")
        print(f"  O- usado para otros receptores: {o_neg_total - o_neg_for_o_neg:.2f}")

    if include_report:
        _print_positive_map("Demanda insatisfecha por hospital", metrics["shortage_by_hospital"])
        _print_positive_map("Demanda insatisfecha por tipo sanguineo", metrics["shortage_by_type"])
        _print_positive_map("Top 10 periodos con demanda insatisfecha", metrics["shortage_by_period"], limit=10)
        _print_positive_map("Vencimiento por nodo", metrics["expired_by_node"])
        _print_positive_map("Vencimiento por tipo sanguineo", metrics["expired_by_type"])
        _print_positive_map("Despachos por hospital", metrics["shipped_by_hospital"])
        _print_positive_map("Inventario final por nodo", metrics["final_inventory_by_node"])
        _print_positive_map("Inventario final por tipo sanguineo", metrics["final_inventory_by_type"])
        _print_positive_map("Top 10 sustituciones compatibles", metrics["substitution_by_pair"], limit=10)

    if not include_details:
        return

    x = model._vars["x"]
    y = model._vars["y"]

    print("\nDespachos positivos:")
    for t in data.T:
        for h in data.H:
            for g in data.G:
                for u in data.U:
                    value = x[h, g, u, t].X
                    if value > 1e-6:
                        print(f"t={t}, hospital={h}, tipo={g}, vida={u}: {value:.2f}")

    print("\nUsos positivos:")
    for t in data.T:
        for h in data.H:
            for donor in data.G:
                for receiver in data.G:
                    for u in data.U:
                        value = y[h, donor, receiver, u, t].X
                        if value > 1e-6:
                            print(
                                f"t={t}, hospital={h}, donante={donor}, "
                                f"receptor={receiver}, vida={u}: {value:.2f}"
                            )
