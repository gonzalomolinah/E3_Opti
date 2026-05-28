from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import load_data
from src.validate_data import validate_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Solve a blood distribution JSON file or CSV directory with Gurobi.")
    parser.add_argument("instance", help="Path to data/instances/*.json or a CSV instance directory")
    parser.add_argument("--time-limit", type=float, default=None)
    parser.add_argument("--quiet", action="store_true", help="Suppress Gurobi solver log")
    parser.add_argument("--report", action="store_true", help="Print grouped operational metrics")
    parser.add_argument("--details", action="store_true", help="Print all positive shipment and use variables")
    args = parser.parse_args()

    data = load_data(args.instance)
    validation = validate_data(data)
    for warning in validation.warnings:
        print(f"WARNING: {warning}")
    if not validation.ok:
        for error in validation.errors:
            print(f"ERROR: {error}")
        return 1

    try:
        from src.diagnose import diagnose_status
        from src.model import build_model
    except ModuleNotFoundError as exc:
        if exc.name == "gurobipy":
            print("ERROR: gurobipy is not installed. Install Gurobi and activate a license to solve.")
            return 2
        raise

    model = build_model(data)
    if args.time_limit is not None:
        model.Params.TimeLimit = args.time_limit
    if args.quiet:
        model.Params.OutputFlag = 0

    model.optimize()
    diagnose_status(model, data, include_details=args.details, include_report=args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
