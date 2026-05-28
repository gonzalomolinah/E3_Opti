import math, os

import pandas as pd
import gurobipy as gp
from gurobipy import GRB


# =============================================================================
# 1. CARGA DE DATOS
# =============================================================================

def cargar_datos(ruta='.', t_max=None, factor_donaciones=1.0, eta_override=None):
    """
    Lee los CSVs de `ruta` y devuelve el dict de parametros del modelo.

    Soporta dos esquemas de columnas (Ross/Nef y Guridi); detecta automatico.

    Parametros opcionales (sensibilidad):
      t_max               : trunca el horizonte a 1..t_max (None = T del CSV)
      factor_donaciones   : multiplicador sobre b[g,t]
      eta_override        : reemplaza eta del CSV
    """
    def lee(nombre):
        return pd.read_csv(os.path.join(ruta, nombre))

    # Escalares y deteccion de formato
    params = lee('parametros_globales.csv').set_index('parametro')['valor']
    if 'T' in params.index:
        formato = 'ross'
        L = int(params['L'])
        T_csv = int(params['T'])
        p = float(params['p'])
        eta_csv = float(params['eta'])
        M = float(params['M'])
    else:
        formato = 'guridi'
        L = int(params['vida_util_L'])
        T_csv = int(params['horizonte_T'])
        p = float(params['penalizacion_demanda_insatisfecha_p'])
        eta_csv = float(params['penalizacion_vencimiento_eta'])
        M = float(params['M_grande'])
    eta = float(eta_override) if eta_override is not None else eta_csv
    T_horizonte = T_csv if t_max is None else min(int(t_max), T_csv)

    # Mapeo de nombres de columnas segun el formato
    if formato == 'ross':
        COL = {
            'hospital': 'hospital_id', 'tipo': 'tipo_sangre', 'tau': 'tau_dias',
            'K_nodo': 'nodo_id', 'K_cap': 'capacidad_K_bolsas', 'alpha': 'alpha',
            'compat_d': 'tipo_donante', 'compat_r': 'tipo_receptor', 'Q': 'Q_t',
            'don_g': 'tipo_sangre', 'dem_h': 'hospital_id', 'dem_g': 'tipo_sangre',
            'inv_n': 'nodo_id', 'inv_g': 'tipo_sangre',
            'inv_b': 'inventario_inicial_bolsas', 'banco_id': '0',
        }
    else:
        COL = {
            'hospital': 'hospital', 'tipo': 'grupo', 'tau': 'tiempo_traslado_dias',
            'K_nodo': 'nodo', 'K_cap': 'capacidad_maxima_bolsas',
            'alpha': 'alpha_penalizacion_uso', 'compat_d': 'donante',
            'compat_r': 'receptor', 'Q': 'capacidad_envio_diaria_bolsas',
            'don_g': 'grupo', 'dem_h': 'hospital', 'dem_g': 'grupo',
            'inv_n': 'nodo', 'inv_g': 'grupo',
            'inv_b': 'inventario_inicial_bolsas', 'banco_id': 'Banco',
        }

    hospitales_df = lee('hospitales.csv')
    H = hospitales_df[COL['hospital']].tolist()
    tipos_df = lee('tipos_sangre.csv')
    G = tipos_df[COL['tipo']].tolist()
    N = [0] + H
    U = list(range(1, L + 1))
    T = list(range(1, T_horizonte + 1))

    C = [(row[COL['compat_d']], row[COL['compat_r']])
         for _, row in lee('compatibilidad.csv').iterrows()
         if int(row['compatible']) == 1]

    # tau se redondea hacia arriba a entero (math.ceil)
    tau = {row[COL['hospital']]: int(math.ceil(float(row[COL['tau']])))
           for _, row in hospitales_df.iterrows()}

    K = {}
    for _, row in lee('capacidad_nodos.csv').iterrows():
        nodo = row[COL['K_nodo']]
        n = 0 if str(nodo) == str(COL['banco_id']) else nodo
        K[n] = int(row[COL['K_cap']])

    alpha = {row[COL['tipo']]: float(row[COL['alpha']])
             for _, row in tipos_df.iterrows()}

    Q = {int(row['t']): int(row[COL['Q']])
         for _, row in lee('capacidad_transporte.csv').iterrows()
         if int(row['t']) <= T_horizonte}

    b = {(row[COL['don_g']], int(row['t'])):
         int(int(row['donaciones_bolsas']) * factor_donaciones)
         for _, row in lee('donaciones.csv').iterrows()
         if int(row['t']) <= T_horizonte}

    d = {(row[COL['dem_h']], row[COL['dem_g']], int(row['t'])):
         int(row['demanda_bolsas'])
         for _, row in lee('demanda.csv').iterrows()
         if int(row['t']) <= T_horizonte}

    I0 = {}
    for _, row in lee('inventario_inicial.csv').iterrows():
        nodo = row[COL['inv_n']]
        n = 0 if str(nodo) == str(COL['banco_id']) else nodo
        I0[(n, row[COL['inv_g']])] = int(row[COL['inv_b']])

    return {
        'H': H, 'G': G, 'N': N, 'U': U, 'T': T, 'L': L, 'C': C,
        'd': d, 'b': b, 'I0': I0, 'K': K, 'tau': tau, 'alpha': alpha,
        'p': p, 'eta': eta, 'M': M, 'Q': Q,
    }


# =============================================================================
# 2. CONSTRUCCION DEL MODELO
# =============================================================================

def construir_modelo(datos, enteras=False):
    """Construye el modelo (PDF v2, R1..R15). Devuelve (modelo, variables)."""
    H = datos['H']; G = datos['G']; N = datos['N']
    U = datos['U']; T = datos['T']; L = datos['L']; C = datos['C']
    d = datos['d']; b = datos['b']; I0 = datos['I0']
    K = datos['K']; tau = datos['tau']; alpha = datos['alpha']
    p = datos['p']; eta = datos['eta']; Q = datos['Q']

    m = gp.Model('distribucion_sangre')
    m.Params.Method = 2
    m.Params.Crossover = 0
    m.Params.BarConvTol = 1e-6
    m.Params.Threads = 0

    # Variables (R12 implementada por construccion: y solo existe para (g,g') in C)
    vtype = GRB.INTEGER if enteras else GRB.CONTINUOUS
    x = m.addVars(H, G, U, T, lb=0.0, vtype=vtype, name='x')
    I = m.addVars(N, G, U, T, lb=0.0, vtype=vtype, name='I')
    y = m.addVars(
        [(h, g, gpr, u, t) for h in H for (g, gpr) in C for u in U for t in T],
        lb=0.0, vtype=vtype, name='y'
    )
    s = m.addVars(H, G, T, lb=0.0, vtype=vtype, name='s')
    w = m.addVars(N, G, T, lb=0.0, vtype=vtype, name='w')

    # Funcion objetivo
    obj = gp.quicksum(
        ((L - u) + tau[h] + alpha[g]) * y[h, g, gpr, u, t]
        for t in T for h in H for (g, gpr) in C for u in U
    )
    obj += p   * gp.quicksum(s[h, g, t] for h in H for g in G for t in T)
    obj += eta * gp.quicksum(w[n, g, t] for n in N for g in G for t in T)
    m.setObjective(obj, GRB.MINIMIZE)

    # R1. Balance hospital, u < L, t >= 2
    for h in H:
        for g in G:
            for u in range(1, L):
                for t in T:
                    if t >= 2:
                        m.addConstr(
                            I[h, g, u, t] == I[h, g, u + 1, t - 1] + x[h, g, u, t]
                            - gp.quicksum(y[h, g, gpr, u, t]
                                          for gpr in G if (g, gpr) in C),
                            name=f'R1[{h},{g},{u},{t}]'
                        )

    # R2. Balance hospital a u = L, t >= 2
    for h in H:
        for g in G:
            for t in T:
                if t >= 2:
                    m.addConstr(
                        I[h, g, L, t] == x[h, g, L, t]
                        - gp.quicksum(y[h, g, gpr, L, t]
                                      for gpr in G if (g, gpr) in C),
                        name=f'R2[{h},{g},{t}]'
                    )

    # R3. Balance banco, u < L, t >= 2
    for g in G:
        for u in range(1, L):
            for t in T:
                if t >= 2:
                    m.addConstr(
                        I[0, g, u, t] == I[0, g, u + 1, t - 1]
                        - gp.quicksum(x[h, g, u, t] for h in H),
                        name=f'R3[{g},{u},{t}]'
                    )

    # R4. Donaciones al banco a u = L, t >= 2
    for g in G:
        for t in T:
            if t >= 2:
                m.addConstr(
                    I[0, g, L, t] == b[g, t]
                    - gp.quicksum(x[h, g, L, t] for h in H),
                    name=f'R4[{g},{t}]'
                )

    # R5. Balance hospital t = 1, u = L
    for h in H:
        for g in G:
            m.addConstr(
                I[h, g, L, 1] == I0[h, g] + x[h, g, L, 1]
                - gp.quicksum(y[h, g, gpr, L, 1] for gpr in G if (g, gpr) in C),
                name=f'R5[{h},{g}]'
            )

    # R6. Balance banco t = 1, u = L
    for g in G:
        m.addConstr(
            I[0, g, L, 1] == I0[0, g] + b[g, 1]
            - gp.quicksum(x[h, g, L, 1] for h in H),
            name=f'R6[{g}]'
        )

    # R7. A t = 1 y u < L todo es 0 (no hay stock, ni envios, ni uso)
    for g in G:
        for u in range(1, L):
            for n in N:
                m.addConstr(I[n, g, u, 1] == 0, name=f'R7_I[{n},{g},{u}]')
            for h in H:
                m.addConstr(x[h, g, u, 1] == 0, name=f'R7_x[{h},{g},{u}]')
                for gpr in G:
                    if (g, gpr) in C:
                        m.addConstr(y[h, g, gpr, u, 1] == 0,
                                    name=f'R7_y[{h},{g},{gpr},{u}]')

    # R8. Factibilidad del traslado
    for h in H:
        for g in G:
            for u in U:
                if u <= tau[h]:
                    for t in T:
                        m.addConstr(x[h, g, u, t] == 0,
                                    name=f'R8[{h},{g},{u},{t}]')

    # R9. Capacidad de almacenamiento
    for n in N:
        for t in T:
            m.addConstr(
                gp.quicksum(I[n, g, u, t] for g in G for u in U) <= K[n],
                name=f'R9[{n},{t}]'
            )

    # R10. Vencimiento en hospitales, t >= 2
    for h in H:
        for g in G:
            for t in T:
                if t >= 2:
                    m.addConstr(w[h, g, t] == I[h, g, 1, t - 1],
                                name=f'R10[{h},{g},{t}]')

    # R11. Vencimiento en banco, t >= 2
    for g in G:
        for t in T:
            if t >= 2:
                m.addConstr(w[0, g, t] == I[0, g, 1, t - 1],
                            name=f'R11[{g},{t}]')

    # R10/R11 caso t = 1 (vencimiento inicial = 0, robusto si eta = 0)
    for n in N:
        for g in G:
            m.addConstr(w[n, g, 1] == 0, name=f'R10R11_t1[{n},{g}]')

    # R13. Capacidad diaria de transporte
    for t in T:
        m.addConstr(
            gp.quicksum(x[h, g, u, t] for h in H for g in G for u in U) <= Q[t],
            name=f'R13[{t}]'
        )

    # R14. Satisfaccion de demanda
    for h in H:
        for gpr in G:
            for t in T:
                m.addConstr(
                    gp.quicksum(y[h, g, gpr, u, t]
                                for g in G for u in U if (g, gpr) in C)
                    + s[h, gpr, t] == d[h, gpr, t],
                    name=f'R14[{h},{gpr},{t}]'
                )

    m.update()
    return m, {'x': x, 'I': I, 'y': y, 's': s, 'w': w}


# =============================================================================
# 3. RESOLUCION E IMPRESION DE RESULTADOS
# =============================================================================

def resolver(modelo, variables, datos, verbose=False):
    """Optimiza el modelo e imprime el resumen agregado."""
    modelo.optimize()

    if modelo.Status != GRB.OPTIMAL:
        print(f"\n[!] No se encontro optimo. Status = {modelo.Status}")
        if modelo.Status == GRB.INFEASIBLE:
            modelo.computeIIS()
            modelo.write('modelo_iis.ilp')
            print("    IIS escrito en modelo_iis.ilp")
        return

    x = variables['x']; I = variables['I']; y = variables['y']
    s = variables['s']; w = variables['w']
    H = datos['H']; G = datos['G']; N = datos['N']
    U = datos['U']; T = datos['T']; L = datos['L']; C = datos['C']
    d = datos['d']; p = datos['p']; eta = datos['eta']; tau = datos['tau']
    alpha = datos['alpha']
    tol = 1e-6

    obj_calidad = sum(
        ((L - u) + tau[h] + alpha[g]) * y[h, g, gpr, u, t].X
        for t in T for h in H for (g, gpr) in C for u in U
    )
    obj_insatisf = p   * sum(s[h, g, t].X for h in H for g in G for t in T)
    obj_vencido  = eta * sum(w[n, g, t].X for n in N for g in G for t in T)

    total_d = sum(d.values())
    total_y = sum(var.X for var in y.values())
    total_s = sum(var.X for var in s.values())
    total_w_banco = sum(w[0, g, t].X for g in G for t in T)
    total_w_hosp  = sum(w[h, g, t].X for h in H for g in G for t in T)

    print("\n" + "=" * 70)
    print(f"  Solucion optima. Valor objetivo = {modelo.ObjVal:,.2f}")
    print("=" * 70)
    print(f"  Termino 1 (calidad de uso)     : {obj_calidad:>12,.2f}")
    print(f"  Termino 2 (demanda insatisf.)  : {obj_insatisf:>12,.2f}")
    print(f"  Termino 3 (vencimientos)       : {obj_vencido:>12,.2f}")

    print("\n--- Balance global ---")
    print(f"  Demanda total          : {total_d:>8,.0f}")
    print(f"  Demanda satisfecha     : {total_y:>8,.0f} ({100 * total_y / total_d:.1f}%)")
    print(f"  Demanda insatisfecha   : {total_s:>8,.0f} ({100 * total_s / total_d:.1f}%)")
    print(f"  Vencidas en banco      : {total_w_banco:>8,.0f}")
    print(f"  Vencidas en hospitales : {total_w_hosp:>8,.0f}")

    print("\n--- Insatisfecha por tipo ---")
    for g in G:
        s_g = sum(s[h, g, t].X for h in H for t in T)
        d_g = sum(d[h, g, t] for h in H for t in T)
        if d_g > 0:
            pct = 100 * s_g / d_g
            marca = "  <-- ALTO" if pct > 5 else ""
            print(f"  {g:>4} : {s_g:>6,.0f} / {d_g:>6,.0f} ({pct:5.1f}%){marca}")

    print("\n--- Vencimientos por tipo ---")
    for g in G:
        w_g = sum(w[n, g, t].X for n in N for t in T)
        if w_g > tol:
            print(f"  {g:>4} : {w_g:>6,.0f}")

    print("\n--- Eventos por dia (solo con incidentes) ---")
    print(f"  {'dia':>4} | {'insatisf.':>10} | {'vencida':>9}")
    for t in T:
        s_t = sum(s[h, g, t].X for h in H for g in G)
        w_t = sum(w[n, g, t].X for n in N for g in G)
        if s_t > tol or w_t > tol:
            print(f"  {t:>4} | {s_t:>10,.0f} | {w_t:>9,.0f}")

    if not verbose:
        return

    print("\n--- Envios x > 0 ---")
    for (h, g, u, t), var in x.items():
        if var.X > tol:
            print(f"  x[{h},{g},u={u},t={t}] = {var.X:.2f}")
    print("\n--- Usos y > 0 ---")
    for (h, g, gpr, u, t), var in y.items():
        if var.X > tol:
            print(f"  y[{h},{g}->{gpr},u={u},t={t}] = {var.X:.2f}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    # Datasets: './datos/datos_ross' | './datos/datos_guridi' | './datos/datos_nef'
    RUTA_DATOS = './datos/datos_nef'
    T_MAX = None
    FACTOR_DONACIONES = 1.0
    ETA_OVERRIDE = None

    print(f"\n>>> {RUTA_DATOS} | t_max={T_MAX} | "
          f"factor_donaciones={FACTOR_DONACIONES} | eta_override={ETA_OVERRIDE}\n")
    datos = cargar_datos(ruta=RUTA_DATOS, t_max=T_MAX,
                         factor_donaciones=FACTOR_DONACIONES,
                         eta_override=ETA_OVERRIDE)
    print(f"  H={len(datos['H'])} | G={len(datos['G'])} | "
          f"T={len(datos['T'])} | L={datos['L']} | |C|={len(datos['C'])}")
    print(f"  Donaciones: {sum(datos['b'].values()):,} | "
          f"p={datos['p']} | eta={datos['eta']}\n")

    modelo, variables = construir_modelo(datos, enteras=True)
    resolver(modelo, variables, datos, verbose=False)
