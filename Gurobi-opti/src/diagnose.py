from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import load_data
from src.validate_data import validate_data

try:
    from gurobipy import GRB
except ModuleNotFoundError:
    GRB = None


def _status_name(status: int) -> str:
    if GRB is None:
        return f"STATUS_{status}"
    names = {
        GRB.OPTIMAL: "OPTIMAL",
        GRB.INFEASIBLE: "INFEASIBLE",
        GRB.INF_OR_UNBD: "INF_OR_UNBD",
        GRB.UNBOUNDED: "UNBOUNDED",
        GRB.TIME_LIMIT: "TIME_LIMIT",
    }
    return names.get(status, f"STATUS_{status}")


def _constraint_family(name: str) -> str:
    return name.split("[", 1)[0]


def diagnose_infeasible(model, output_dir: str | Path = "diagnostics") -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    print("Computing IIS...")
    model.computeIIS()
    iis_path = output / "iis.ilp"
    model.write(str(iis_path))
    print(f"IIS written to {iis_path}")

    grouped: dict[str, list[str]] = defaultdict(list)
    for constr in model.getConstrs():
        if constr.IISConstr:
            grouped[_constraint_family(constr.ConstrName)].append(constr.ConstrName)

    for family, names in sorted(grouped.items()):
        print(f"IIS constraint family {family}: {len(names)}")
        for name in names[:10]:
            print(f"  {name}")
        if len(names) > 10:
            print("  ...")

    for var in model.getVars():
        if var.IISLB or var.IISUB:
            print(f"IIS variable bound: {var.VarName}, LB={var.IISLB}, UB={var.IISUB}")

    relaxed = model.copy()
    relaxed.feasRelaxS(0, True, False, True)
    relaxed.optimize()
    relax_path = output / "feasrelax.lp"
    relaxed.write(str(relax_path))
    print(f"FeasRelax model written to {relax_path}")
    if relaxed.Status == GRB.OPTIMAL:
        print(f"Minimum relaxation objective: {relaxed.ObjVal:.6g}")


def diagnose_status(
    model,
    data,
    output_dir: str | Path = "diagnostics",
    include_details: bool = False,
    include_report: bool = False,
) -> int:
    if GRB is None:
        raise RuntimeError("gurobipy is not installed; diagnostics require Gurobi")

    from src.model import print_solution, solution_totals

    status = model.Status
    print(f"Gurobi status: {_status_name(status)}")

    if status == GRB.OPTIMAL:
        print_solution(model, data, include_details=include_details, include_report=include_report)
        return status

    if status == GRB.INFEASIBLE:
        diagnose_infeasible(model, output_dir)
        return status

    if status == GRB.INF_OR_UNBD:
        print("Retrying with DualReductions=0 to distinguish infeasible from unbounded.")
        model.Params.DualReductions = 0
        model.reset()
        model.optimize()
        return diagnose_status(
            model,
            data,
            output_dir,
            include_details=include_details,
            include_report=include_report,
        )

    if status == GRB.UNBOUNDED:
        print("The objective is unbounded. Check negative costs, missing bounds, and missing balance constraints.")
        return status

    if status == GRB.TIME_LIMIT:
        if model.SolCount > 0:
            print("Time limit reached with an incumbent solution.")
            print(f"Incumbent objective: {model.ObjVal:.2f}")
            print(f"Best bound: {model.ObjBound:.2f}")
            print(f"MIP gap: {model.MIPGap:.6g}")
            print_solution(model, data, include_details=False, include_report=include_report)
            totals = solution_totals(model, data)
            if totals["used"] > 0 and totals["expired"] / max(totals["used"], 1.0) > 0.06:
                print("WARNING: wastage exceeds 6% of used units in the incumbent solution.")
        else:
            print("Time limit reached without an incumbent solution.")
        return status

    print("No specialized diagnostic implemented for this status.")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose a Gurobi optimization instance.")
    parser.add_argument("instance", help="Path to data/instances/*.json")
    parser.add_argument("--output-dir", default="diagnostics")
    parser.add_argument("--report", action="store_true", help="Print grouped operational metrics.")
    parser.add_argument("--details", action="store_true", help="Print all positive shipment and use variables.")
    args = parser.parse_args()

    data = load_data(args.instance)
    validation = validate_data(data)
    for warning in validation.warnings:
        print(f"WARNING: {warning}")
    if not validation.ok:
        for error in validation.errors:
            print(f"ERROR: {error}")
        return 1

    if GRB is None:
        print("ERROR: gurobipy is not installed. Install Gurobi and activate a license to diagnose.")
        return 2

    from src.model import build_model

    model = build_model(data)
    model.optimize()
    diagnose_status(model, data, args.output_dir, include_details=args.details, include_report=args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
