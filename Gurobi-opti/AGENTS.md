# Project guidance for Codex

This repository implements a mathematical optimization model in Python using gurobipy.

Important rules:
- Do not change the mathematical formulation unless explicitly asked.
- Treat formulation/model.tex as the source of truth.
- Any generated data must be clearly marked as synthetic.
- Do not invent real-world data sources.
- Every dataset must satisfy formulation/data_contract.md.
- All variables, constraints, and parameters must preserve the index sets from the LaTeX formulation.
- Prefer small reproducible instances before large instances.
- After code changes, run:
  python -m pytest
  python src/validate_data.py data/instances/tiny.json
  python src/solve.py data/instances/tiny.json

Review expectations:
- Check dimensions of all indexed parameters.
- Check lower/upper bounds.
- Check units.
- Check whether constraints are <=, >=, or == exactly as in the formulation.
- If the model is infeasible, run src/diagnose.py and summarize the likely cause.