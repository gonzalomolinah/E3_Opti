import csv
import sys
from pathlib import Path

from gurobipy import GRB, Model, quicksum


if len(sys.argv) != 2:
    raise SystemExit("Uso: py -3.8 main.py <directorio_datos>")

DIRECTORIO_DATOS = Path(sys.argv[1])


def leer(nombre):
    with open(DIRECTORIO_DATOS / nombre, newline="", encoding="utf-8-sig") as archivo:
        return list(csv.DictReader(archivo))


parametros = {r["parametro"]: float(r["valor"]) for r in leer("parametros_globales.csv")}
L = int(parametros["L"])
T = range(1, int(parametros["T"]) + 1)
U = range(1, L + 1)
H = [r["hospital_id"] for r in leer("hospitales.csv")]
G = [r["tipo_sangre"] for r in leer("tipos_sangre.csv")]
N = ["0"] + H

hospitales = {r["hospital_id"]: r for r in leer("hospitales.csv")}
tipos = {r["tipo_sangre"]: r for r in leer("tipos_sangre.csv")}
C = [
    (r["tipo_donante"], r["tipo_receptor"])
    for r in leer("compatibilidad.csv")
    if int(r["compatible"]) == 1
]
receptores = {g: [r for d, r in C if d == g] for g in G}
donantes = {g: [d for d, r in C if r == g] for g in G}

tau = {h: float(hospitales[h]["tau_dias"]) for h in H}
alpha = {g: float(tipos[g]["alpha"]) for g in G}
K = {r["nodo_id"]: float(r["capacidad_K_bolsas"]) for r in leer("capacidad_nodos.csv")}
Q = {int(r["t"]): float(r["Q_t"]) for r in leer("capacidad_transporte.csv")}
b = {
    (r["tipo_sangre"], int(r["t"])): float(r["donaciones_bolsas"])
    for r in leer("donaciones.csv")
}
d = {
    (r["hospital_id"], r["tipo_sangre"], int(r["t"])): float(r["demanda_bolsas"])
    for r in leer("demanda.csv")
}
I0 = {
    (r["nodo_id"], r["tipo_sangre"]): float(r["inventario_inicial_bolsas"])
    for r in leer("inventario_inicial.csv")
}

modelo = Model("distribucion_sangre")
x = modelo.addVars(H, G, U, T, name="x")
I = modelo.addVars(N, G, U, T, name="I")
y = modelo.addVars(
    ((h, g, r, u, t) for h in H for g, r in C for u in U for t in T),
    name="y",
)
s = modelo.addVars(H, G, T, name="s")
w = modelo.addVars(N, G, T, name="w")

modelo.setObjective(
    quicksum(
        ((L - u) + tau[h] + alpha[g]) * y[h, g, r, u, t]
        for h in H
        for g, r in C
        for u in U
        for t in T
    )
    + parametros["p"] * quicksum(s[h, g, t] for h in H for g in G for t in T)
    + parametros["eta"] * quicksum(w[n, g, t] for n in N for g in G for t in T),
    GRB.MINIMIZE,
)

modelo.addConstrs(
    (
        I[h, g, u, t]
        == I[h, g, u + 1, t - 1]
        + x[h, g, u, t]
        - quicksum(y[h, g, r, u, t] for r in receptores[g])
        for h in H
        for g in G
        for u in range(1, L)
        for t in range(2, len(T) + 1)
    ),
    name="balance_hospital",
)
modelo.addConstrs(
    (
        I[h, g, L, t] == x[h, g, L, t] - quicksum(y[h, g, r, L, t] for r in receptores[g])
        for h in H
        for g in G
        for t in range(2, len(T) + 1)
    ),
    name="sangre_nueva_hospital",
)
modelo.addConstrs(
    (
        I["0", g, u, t]
        == I["0", g, u + 1, t - 1] - quicksum(x[h, g, u, t] for h in H)
        for g in G
        for u in range(1, L)
        for t in range(2, len(T) + 1)
    ),
    name="balance_banco",
)
modelo.addConstrs(
    (
        I["0", g, L, t] == b[g, t] - quicksum(x[h, g, L, t] for h in H)
        for g in G
        for t in range(2, len(T) + 1)
    ),
    name="donaciones",
)
modelo.addConstrs(
    (
        I[h, g, L, 1]
        == I0[h, g] + x[h, g, L, 1] - quicksum(y[h, g, r, L, 1] for r in receptores[g])
        for h in H
        for g in G
    ),
    name="inventario_inicial_hospital",
)
modelo.addConstrs(
    (
        I["0", g, L, 1] == I0["0", g] + b[g, 1] - quicksum(x[h, g, L, 1] for h in H)
        for g in G
    ),
    name="inventario_inicial_banco",
)
modelo.addConstrs((I[n, g, u, 1] == 0 for n in N for g in G for u in range(1, L)), name="I_inicial_cero")
modelo.addConstrs((x[h, g, u, 1] == 0 for h in H for g in G for u in range(1, L)), name="x_inicial_cero")
modelo.addConstrs(
    (y[h, g, r, u, 1] == 0 for h in H for g, r in C for u in range(1, L)),
    name="y_inicial_cero",
)

for h in H:
    for u in U:
        if u <= tau[h]:
            modelo.addConstrs((x[h, g, u, t] == 0 for g in G for t in T), name="traslado")

modelo.addConstrs(
    (quicksum(I[n, g, u, t] for g in G for u in U) <= K[n] for n in N for t in T),
    name="capacidad_nodo",
)
modelo.addConstrs((w[n, g, 1] == 0 for n in N for g in G), name="vencimiento_inicial")
modelo.addConstrs(
    (w[n, g, t] == I[n, g, 1, t - 1] for n in N for g in G for t in range(2, len(T) + 1)),
    name="vencimiento",
)
modelo.addConstrs(
    (quicksum(x[h, g, u, t] for h in H for g in G for u in U) <= Q[t] for t in T),
    name="transporte",
)
modelo.addConstrs(
    (
        quicksum(y[h, donor, receptor, u, t] for donor in donantes[receptor] for u in U)
        + s[h, receptor, t]
        == d[h, receptor, t]
        for h in H
        for receptor in G
        for t in T
    ),
    name="demanda",
)

modelo.optimize()

if modelo.Status == GRB.OPTIMAL:
    print(f"Valor objetivo: {modelo.ObjVal:,.2f}")
    print(f"Tiempo de resolucion: {modelo.Runtime / 60:.2f} minutos")
else:
    print(f"Estado de Gurobi: {modelo.Status}")
    print(f"Tiempo de resolucion: {modelo.Runtime / 60:.2f} minutos")
