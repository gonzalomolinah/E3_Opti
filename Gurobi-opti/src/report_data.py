from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import load_data
from src.validate_data import validate_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Report high-level metrics for a JSON or CSV instance.")
    parser.add_argument("instance", help="Path to data/instances/*.json or a CSV instance directory")
    args = parser.parse_args()

    data = load_data(args.instance)
    validation = validate_data(data)
    for warning in validation.warnings:
        print(f"WARNING: {warning}")
    if not validation.ok:
        for error in validation.errors:
            print(f"ERROR: {error}")
        return 1

    total_demand = sum(data.demand.values())
    total_donations = sum(data.donations.values())
    total_initial = sum(data.initial_inventory.values())
    avg_daily_demand = total_demand / len(data.T)
    avg_daily_donations = total_donations / len(data.T)

    print(f"Instance: {data.metadata.get('name', 'unknown')}")
    print(f"Synthetic: {data.metadata.get('synthetic')}")
    print(f"Hospitals: {len(data.H)} | Blood types: {len(data.G)} | Periods: {len(data.T)} | L: {data.L}")
    print(f"Total demand: {total_demand:.0f} bags")
    print(f"Average daily demand: {avg_daily_demand:.1f} bags/day")
    print(f"Total donations: {total_donations:.0f} bags")
    print(f"Average daily donations: {avg_daily_donations:.1f} bags/day")
    print(f"Initial inventory: {total_initial:.0f} bags")

    print("\nDemand by hospital:")
    for h in data.H:
        demand_h = sum(data.demand[h, g, t] for g in data.G for t in data.T)
        avg_h = demand_h / len(data.T)
        cap_h = data.capacity[h]
        days = cap_h / avg_h if avg_h else float("inf")
        print(f"  {h}: demand={demand_h:.0f}, avg/day={avg_h:.1f}, capacity={cap_h:.0f}, cap_days={days:.1f}")

    print("\nDemand by blood type:")
    for g in data.G:
        demand_g = sum(data.demand[h, g, t] for h in data.H for t in data.T)
        donation_g = sum(data.donations[g, t] for t in data.T)
        print(f"  {g}: demand={demand_g:.0f}, donations={donation_g:.0f}")

    print("\nReference checks:")
    print("  RBC shelf life reference: 42 days for standard RBC units.")
    print("  Hospital inventory reference: about 4-6 days of average RBC use.")
    print("  Normal wastage reference: roughly 0-6% depending on setting.")
    nonzero_substitutions = sum(
        1
        for (donor, receiver), value in data.substitution_penalty.items()
        if donor != receiver and value > 0
    )
    print(f"  Substitution penalties active for {nonzero_substitutions} donor-receiver pairs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
