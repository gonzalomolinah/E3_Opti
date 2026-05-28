from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Data:
    H: list[str]
    G: list[str]
    T: list[int]
    U: list[int]
    L: int
    N: list[str]
    demand: dict[tuple[str, str, int], float]
    donations: dict[tuple[str, int], float]
    initial_inventory: dict[tuple[str, str], float]
    capacity: dict[str, float]
    travel_time: dict[str, int]
    compatible: dict[tuple[str, str], int]
    shortage_penalty: float
    expiration_penalty: float
    use_penalty: dict[str, float]
    substitution_penalty: dict[tuple[str, str], float]
    max_transport: dict[int, float]
    big_m: float
    metadata: dict[str, Any]


def load_instance(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if path.is_dir():
        return load_csv_instance(path)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _first_existing(base: Path, *names: str) -> Path:
    for name in names:
        path = base / name
        if path.exists():
            return path
    expected = ", ".join(names)
    raise FileNotFoundError(f"Missing CSV file. Expected one of: {expected}")


def _value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    expected = ", ".join(names)
    raise KeyError(f"Missing CSV column. Expected one of: {expected}")


def _number(value: Any) -> int | float:
    text = str(value).strip()
    number = float(text)
    return int(number) if number.is_integer() else number


def _bool(value: Any) -> bool:
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "si", "s"}:
        return True
    if text in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _global_parameters(base: Path) -> dict[str, Any]:
    path = _first_existing(base, "global_parameters.csv", "scalars.csv", "parametros_globales.csv")
    rows = _read_csv(path)
    params: dict[str, Any] = {}
    for row in rows:
        name = str(_value(row, "parameter", "parametro", "name", "nombre")).strip()
        params[name] = _number(_value(row, "value", "valor"))
    return params


def _metadata(base: Path) -> dict[str, Any]:
    path = base / "metadata.csv"
    if not path.exists():
        return {
            "name": base.name,
            "synthetic": True,
            "description": "CSV instance loaded from local files.",
        }
    rows = _read_csv(path)
    if len(rows) != 1:
        raise ValueError("metadata.csv must contain exactly one row")
    row = rows[0]
    return {
        "name": str(_value(row, "name")),
        "synthetic": _bool(_value(row, "synthetic")),
        "description": str(_value(row, "description")),
    }


def load_csv_instance(path: str | Path) -> dict[str, Any]:
    """Load a CSV directory and return the same instance shape as JSON files."""
    base = Path(path)
    params = _global_parameters(base)

    hospitals_rows = _read_csv(_first_existing(base, "hospitals.csv", "hospitales.csv"))
    blood_rows = _read_csv(_first_existing(base, "blood_types.csv", "tipos_sangre.csv"))
    demand_rows = _read_csv(_first_existing(base, "demand.csv", "demanda.csv"))
    donations_rows = _read_csv(_first_existing(base, "donations.csv", "donaciones.csv"))
    inventory_rows = _read_csv(_first_existing(base, "initial_inventory.csv", "inventario_inicial.csv"))
    compatibility_rows = _read_csv(_first_existing(base, "compatibility.csv", "compatibilidad.csv"))
    transport_rows = _read_csv(_first_existing(base, "max_transport.csv", "capacidad_transporte.csv"))

    capacity_file = base / "storage_capacity.csv"
    if not capacity_file.exists():
        capacity_file = base / "capacidad_nodos.csv"
    capacity_rows = _read_csv(capacity_file) if capacity_file.exists() else []

    travel_file = base / "travel_time.csv"
    travel_rows = _read_csv(travel_file) if travel_file.exists() else hospitals_rows

    use_penalty_file = base / "use_penalty.csv"
    use_penalty_rows = _read_csv(use_penalty_file) if use_penalty_file.exists() else blood_rows
    substitution_file = base / "substitution_penalty.csv"
    substitution_rows = _read_csv(substitution_file) if substitution_file.exists() else []

    H = [str(_value(row, "h", "hospital_id")) for row in hospitals_rows]
    G = [str(_value(row, "g", "tipo_sangre")) for row in blood_rows]
    L = int(params["L"])
    max_t = int(params.get("T", max(int(_value(row, "t")) for row in demand_rows)))
    T = list(range(1, max_t + 1))
    U = list(range(1, L + 1))
    N = ["0"] + H

    if capacity_rows:
        storage_capacity = [
            {
                "n": str(_value(row, "n", "nodo_id")),
                "value": _number(_value(row, "value", "capacidad_K_bolsas")),
            }
            for row in capacity_rows
        ]
    else:
        storage_capacity = [{"n": "0", "value": int(params["K0"])}]
        storage_capacity.extend(
            {
                "n": str(_value(row, "h", "hospital_id")),
                "value": _number(_value(row, "storage_capacity", "capacidad_K_bolsas")),
            }
            for row in hospitals_rows
        )

    compatibility = [
        {
            "donor": str(_value(row, "donor", "tipo_donante")),
            "receiver": str(_value(row, "receiver", "tipo_receptor")),
            "value": int(_number(_value(row, "value", "compatible"))),
        }
        for row in compatibility_rows
    ]
    C = [
        {"donor": row["donor"], "receiver": row["receiver"]}
        for row in compatibility
        if row["value"] == 1
    ]
    if substitution_rows:
        substitution_penalty = [
            {
                "donor": str(_value(row, "donor", "tipo_donante")),
                "receiver": str(_value(row, "receiver", "tipo_receptor")),
                "value": _number(_value(row, "value", "penalty", "penalizacion")),
            }
            for row in substitution_rows
        ]
    else:
        default_substitution = _number(params.get("default_substitution_penalty", 5))
        substitution_penalty = [
            {
                "donor": donor,
                "receiver": receiver,
                "value": 0 if donor == receiver else default_substitution,
            }
            for donor in G
            for receiver in G
        ]

    return {
        "metadata": _metadata(base),
        "sets": {"H": H, "G": G, "T": T, "L": L, "U": U, "N": N, "C": C},
        "parameters": {
            "demand": [
                {
                    "h": str(_value(row, "h", "hospital_id")),
                    "g": str(_value(row, "g", "tipo_sangre")),
                    "t": int(_value(row, "t")),
                    "value": _number(_value(row, "value", "demanda_bolsas")),
                }
                for row in demand_rows
            ],
            "donations": [
                {
                    "g": str(_value(row, "g", "tipo_sangre")),
                    "t": int(_value(row, "t")),
                    "value": _number(_value(row, "value", "donaciones_bolsas")),
                }
                for row in donations_rows
            ],
            "initial_inventory": [
                {
                    "n": str(_value(row, "n", "nodo_id")),
                    "g": str(_value(row, "g", "tipo_sangre")),
                    "value": _number(_value(row, "value", "inventario_inicial_bolsas")),
                }
                for row in inventory_rows
            ],
            "storage_capacity": storage_capacity,
            "travel_time": [
            {
                "h": str(_value(row, "h", "hospital_id")),
                "value": _number(_value(row, "value", "travel_time", "tau_dias", "tau")),
            }
            for row in travel_rows
        ],
            "shortage_penalty": _number(params["shortage_penalty"] if "shortage_penalty" in params else params["p"]),
            "expiration_penalty": _number(params["expiration_penalty"] if "expiration_penalty" in params else params["eta"]),
            "compatibility": compatibility,
            "use_penalty": [
                {
                    "g": str(_value(row, "g", "tipo_sangre")),
                    "value": _number(_value(row, "value", "use_penalty", "alpha")),
                }
                for row in use_penalty_rows
            ],
            "substitution_penalty": substitution_penalty,
            "big_m": _number(params["big_m"] if "big_m" in params else params["M"]),
            "max_transport": [
                {
                    "t": int(_value(row, "t")),
                    "value": _number(_value(row, "value", "Q_t")),
                }
                for row in transport_rows
            ],
        },
    }


def _hgt(records: list[dict[str, Any]]) -> dict[tuple[str, str, int], float]:
    return {(r["h"], r["g"], int(r["t"])): float(r["value"]) for r in records}


def _gt(records: list[dict[str, Any]]) -> dict[tuple[str, int], float]:
    return {(r["g"], int(r["t"])): float(r["value"]) for r in records}


def _ng(records: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    return {(r["n"], r["g"]): float(r["value"]) for r in records}


def _n(records: list[dict[str, Any]]) -> dict[str, float]:
    return {r["n"]: float(r["value"]) for r in records}


def _h_int(records: list[dict[str, Any]]) -> dict[str, int]:
    return {r["h"]: int(r["value"]) for r in records}


def _gg(records: list[dict[str, Any]]) -> dict[tuple[str, str], int]:
    return {(r["donor"], r["receiver"]): int(r["value"]) for r in records}


def _gg_float(records: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    return {(r["donor"], r["receiver"]): float(r["value"]) for r in records}


def _g(records: list[dict[str, Any]]) -> dict[str, float]:
    return {r["g"]: float(r["value"]) for r in records}


def _t(records: list[dict[str, Any]]) -> dict[int, float]:
    return {int(r["t"]): float(r["value"]) for r in records}


def data_from_instance(instance: dict[str, Any]) -> Data:
    sets = instance["sets"]
    params = instance["parameters"]
    return Data(
        H=list(sets["H"]),
        G=list(sets["G"]),
        T=[int(t) for t in sets["T"]],
        U=[int(u) for u in sets["U"]],
        L=int(sets["L"]),
        N=list(sets["N"]),
        demand=_hgt(params["demand"]),
        donations=_gt(params["donations"]),
        initial_inventory=_ng(params["initial_inventory"]),
        capacity=_n(params["storage_capacity"]),
        travel_time=_h_int(params["travel_time"]),
        compatible=_gg(params["compatibility"]),
        shortage_penalty=float(params["shortage_penalty"]),
        expiration_penalty=float(params["expiration_penalty"]),
        use_penalty=_g(params["use_penalty"]),
        substitution_penalty=_gg_float(
            params.get(
                "substitution_penalty",
                [
                    {"donor": donor, "receiver": receiver, "value": 0 if donor == receiver else 5}
                    for donor in sets["G"]
                    for receiver in sets["G"]
                ],
            )
        ),
        max_transport=_t(params["max_transport"]),
        big_m=float(params["big_m"]),
        metadata=dict(instance["metadata"]),
    )


def load_data(path: str | Path) -> Data:
    return data_from_instance(load_instance(path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a JSON instance file or CSV instance directory.")
    parser.add_argument("instance", help="Path to data/instances/*.json or a CSV instance directory")
    args = parser.parse_args()
    data = load_data(args.instance)
    print(
        f"Loaded {data.metadata.get('name', 'instance')}: "
        f"|H|={len(data.H)}, |G|={len(data.G)}, |T|={len(data.T)}, L={data.L}"
    )


if __name__ == "__main__":
    main()
