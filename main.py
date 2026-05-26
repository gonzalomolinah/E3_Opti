"""
=============================================================================
ICS1113 - Optimizacion
Informe 3 - Grupo 11
Distribucion optima de sangre desde un banco de sangre a hospitales
=============================================================================

Implementacion en Gurobi del modelo del PDF "Entrega_3_Opti".

ESTRUCTURA DEL ARCHIVO:
    cargar_datos(ruta)       -> lee Excel (o devuelve datos de prueba)
    construir_modelo(datos)  -> define variables, objetivo y restricciones
    resolver(modelo, ...)    -> optimiza e imprime resultados

El modelo esta alineado con la version v2 del PDF (la actualizada por el
grupo), que incorpora como restricciones formales todos los supuestos que
habiamos identificado en la version anterior. Las restricciones del codigo
estan numeradas R1..R15 igual que en el PDF.

UNICA decision de implementacion: las variables y_{h,g,g',u,t} solo se
crean para los pares (g,g') in C. Esto es matematicamente equivalente a
la formulacion del PDF (que las crea para todo g' in G y luego usa R12
con M grande para forzarlas a 0 si c_{g,g'}=0), pero mas eficiente. Ver
la nota junto a R12 en construir_modelo() si se quiere la version literal.
"""

import pandas as pd
import gurobipy as gp
from gurobipy import GRB


# =============================================================================
# 1. CARGA DE DATOS
# =============================================================================

def cargar_datos(ruta=None, escenario='basico', t_max=None):
    """
    Carga los parametros del modelo.

    Si `ruta` es None, devuelve un set de datos sinteticos:
        escenario='basico'  -> 2 hospitales, 2 tipos, T=7
        escenario='estres'  -> 4 hospitales, 8 tipos, T=30

    Si `ruta` apunta a la carpeta con los CSVs reales, lee los archivos:
        hospitales.csv            (hospital_id, tau_dias, capacidad_K_bolsas, ...)
        tipos_sangre.csv          (tipo_sangre, alpha, ...)
        compatibilidad.csv        (tipo_donante, tipo_receptor, compatible)
        inventario_inicial.csv    (nodo_id, tipo_sangre, inventario_inicial_bolsas, ...)
        capacidad_nodos.csv       (nodo_id, capacidad_K_bolsas)
        capacidad_transporte.csv  (t, Q_t)
        donaciones.csv            (tipo_sangre, t, donaciones_bolsas)
        demanda.csv               (hospital_id, tipo_sangre, t, demanda_bolsas)
        parametros_globales.csv   (parametro, valor) -> T, L, p, eta, M

    `t_max`: opcional, trunca el horizonte de planificacion a 1..t_max para
    correr pruebas rapidas (por defecto usa el T del CSV, 365 dias).
    """
    if ruta is None:
        if escenario == 'estres':
            return _datos_prueba_estres()
        return _datos_prueba()

    return _cargar_csvs(ruta, t_max=t_max)


def _cargar_csvs(ruta, t_max=None):
    """Lee los 9 CSVs de la carpeta `ruta` y devuelve el dict de datos."""
    import os

    def lee(nombre):
        return pd.read_csv(os.path.join(ruta, nombre))

    # --- escalares ---
    params = lee('parametros_globales.csv').set_index('parametro')['valor']
    L = int(params['L'])
    T_csv = int(params['T'])
    p = float(params['p'])
    eta = float(params['eta'])
    M = float(params['M'])

    if t_max is None:
        T_horizonte = T_csv
    else:
        T_horizonte = min(int(t_max), T_csv)

    # --- conjuntos ---
    hospitales_df = lee('hospitales.csv')
    H = hospitales_df['hospital_id'].tolist()

    tipos_df = lee('tipos_sangre.csv')
    G = tipos_df['tipo_sangre'].tolist()

    N = [0] + H
    U = list(range(1, L + 1))
    T = list(range(1, T_horizonte + 1))

    # --- compatibilidad ---
    compat_df = lee('compatibilidad.csv')
    C = [(row['tipo_donante'], row['tipo_receptor'])
         for _, row in compat_df.iterrows() if int(row['compatible']) == 1]

    # --- parametros por hospital ---
    # tau viene en dias fraccionarios (~0.02 a 0.05 -> minutos). Como el
    # periodo del modelo es 1 dia, R8 con tau_h < 1 NO bloquea ningun envio:
    # la restriccion x = 0 si u <= tau_h nunca se activa porque u es entero
    # >= 1 > tau_h. Esto es coherente: el traslado dura < 1 dia, no envejece
    # la bolsa. Si el grupo prefiere bloquear u=1, redondear hacia arriba.
    tau = {row['hospital_id']: float(row['tau_dias'])
           for _, row in hospitales_df.iterrows()}

    # --- capacidades por nodo ---
    cap_df = lee('capacidad_nodos.csv')
    K = {}
    for _, row in cap_df.iterrows():
        nodo = row['nodo_id']
        # El CSV trae 0 como string "0" para el banco central
        if nodo == '0' or nodo == 0:
            K[0] = int(row['capacidad_K_bolsas'])
        else:
            K[nodo] = int(row['capacidad_K_bolsas'])

    # --- alpha por tipo ---
    alpha = {row['tipo_sangre']: float(row['alpha'])
             for _, row in tipos_df.iterrows()}

    # --- capacidad de transporte por dia ---
    transp_df = lee('capacidad_transporte.csv')
    Q = {int(row['t']): int(row['Q_t'])
         for _, row in transp_df.iterrows() if int(row['t']) <= T_horizonte}

    # --- donaciones b[g, t] ---
    donaciones_df = lee('donaciones.csv')
    b = {(row['tipo_sangre'], int(row['t'])): int(row['donaciones_bolsas'])
         for _, row in donaciones_df.iterrows()
         if int(row['t']) <= T_horizonte}

    # --- demanda d[h, g, t] ---
    demanda_df = lee('demanda.csv')
    d = {(row['hospital_id'], row['tipo_sangre'], int(row['t'])):
         int(row['demanda_bolsas'])
         for _, row in demanda_df.iterrows()
         if int(row['t']) <= T_horizonte}

    # --- inventario inicial I0[n, g] ---
    inv_df = lee('inventario_inicial.csv')
    I0 = {}
    for _, row in inv_df.iterrows():
        nodo = row['nodo_id']
        if nodo == '0' or nodo == 0:
            n = 0
        else:
            n = nodo
        I0[(n, row['tipo_sangre'])] = int(row['inventario_inicial_bolsas'])

    return {
        'H': H, 'G': G, 'N': N, 'U': U, 'T': T, 'L': L, 'C': C,
        'd': d, 'b': b, 'I0': I0, 'K': K, 'tau': tau, 'alpha': alpha,
        'p': p, 'eta': eta, 'M': M, 'Q': Q,
    }


def _datos_prueba():
    """
    Datos de prueba minimos:
      - 2 hospitales
      - 2 tipos de sangre (O, A) con compatibilidad O->O, O->A, A->A
      - L = 5 dias de vida util
      - T = 7 periodos (una semana)
    Valores escogidos para que el modelo tenga una solucion no trivial
    (demanda > 0, donaciones > 0, vencimiento posible).
    """
    H = ['H1', 'H2']
    G = ['O', 'A']
    L = 5
    T_horizonte = 7

    N = [0] + H                       # 0 = banco central
    U = list(range(1, L + 1))         # niveles de vida util 1..L
    T = list(range(1, T_horizonte + 1))

    # Compatibilidad (g, g') en C: el tipo g PUEDE satisfacer demanda del tipo g'
    # Subconjunto reducido para mantener el ejemplo simple:
    #   O dona a O y a A,  A dona solo a A
    C = [('O', 'O'), ('O', 'A'), ('A', 'A')]

    # Demanda d_{h,g,t}
    d = {(h, g, t): 5 for h in H for g in G for t in T}

    # Donaciones b_{g,t}
    b = {(g, t): 8 for g in G for t in T}

    # Inventario inicial I^0_{n,g} (todo a vida util L per supuesto 10 del PDF)
    I0 = {(0, 'O'): 20, (0, 'A'): 15,
          ('H1', 'O'): 5, ('H1', 'A'): 5,
          ('H2', 'O'): 5, ('H2', 'A'): 5}

    # Capacidad maxima K_n
    K = {0: 200, 'H1': 50, 'H2': 50}

    # Tiempo de traslado tau_h
    tau = {'H1': 1, 'H2': 2}

    # Penalizaciones / ponderadores
    p = 100                          # demanda insatisfecha
    eta = 50                         # bolsa vencida
    alpha = {'O': 1, 'A': 1}         # costo de oportunidad por usar tipo g
    M = 10_000                       # constante grande

    # Capacidad diaria de transporte del banco central Q_t
    Q = {t: 50 for t in T}

    return {
        'H': H, 'G': G, 'N': N, 'U': U, 'T': T, 'L': L, 'C': C,
        'd': d, 'b': b, 'I0': I0, 'K': K, 'tau': tau, 'alpha': alpha,
        'p': p, 'eta': eta, 'M': M, 'Q': Q,
    }


def _datos_prueba_estres():
    """
    Datos de prueba realistas y estresados para ejercitar todas las
    funcionalidades del modelo:

      - 4 hospitales con distintos tau (cercanos y lejanos)
      - 8 tipos de sangre con matriz de compatibilidad ABO/Rh real
      - L = 8 dias (corto, para forzar vencimientos en horizonte de 30 dias)
      - T = 30 dias

    Eventos disenados para gatillar cada feature del modelo:
      * Pico de demanda dias 12-15 (x3)        -> fuerza s > 0
      * Bajon de donaciones dias 25-30 (x0.7)  -> presion al final
      * Q_t reducida dias 14-15 (80 vs 150)    -> cuello de botella
      * Inventario inicial alto en O+/A+       -> fuerza vencimientos w > 0
      * alpha alto en tipos raros (O-, AB-)    -> penaliza mal uso
    """
    H = ['H1', 'H2', 'H3', 'H4']
    G = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']
    L = 8
    T_horizonte = 30

    N = [0] + H
    U = list(range(1, L + 1))
    T = list(range(1, T_horizonte + 1))

    # Matriz de compatibilidad ABO/Rh real (g donante -> g' receptor)
    compat = {
        'O-':  ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],  # universal donor
        'O+':  ['O+', 'A+', 'B+', 'AB+'],
        'A-':  ['A-', 'A+', 'AB-', 'AB+'],
        'A+':  ['A+', 'AB+'],
        'B-':  ['B-', 'B+', 'AB-', 'AB+'],
        'B+':  ['B+', 'AB+'],
        'AB-': ['AB-', 'AB+'],
        'AB+': ['AB+'],
    }
    C = [(g, gpr) for g in G for gpr in compat[g]]

    # Demanda base diaria (proporcional a distribucion poblacional chilena)
    demanda_base = {
        'H1': {'O+': 19, 'A+': 17, 'B+': 5, 'AB+': 2,
               'O-': 3,  'A-': 3,  'B-': 1, 'AB-': 0},
        'H2': {'O+': 11, 'A+': 10, 'B+': 3, 'AB+': 1,
               'O-': 2,  'A-': 2,  'B-': 1, 'AB-': 0},
        'H3': {'O+': 9,  'A+': 8,  'B+': 2, 'AB+': 1,
               'O-': 2,  'A-': 1,  'B-': 1, 'AB-': 0},
        'H4': {'O+': 6,  'A+': 5,  'B+': 1, 'AB+': 1,
               'O-': 1,  'A-': 1,  'B-': 0, 'AB-': 0},
    }
    d = {}
    for h in H:
        for g in G:
            for t in T:
                base = demanda_base[h][g]
                # Pico de demanda dias 12-15 (emergencia masiva, x3)
                d[(h, g, t)] = base * 3 if 12 <= t <= 15 else base

    # Donaciones base (bolsas/dia/tipo, proporcional a poblacion)
    donaciones_base = {'O+': 45, 'A+': 40, 'B+': 11, 'AB+': 4,
                       'O-': 8,  'A-': 7,  'B-': 2,  'AB-': 1}
    b = {}
    for g in G:
        for t in T:
            # Bajon de donaciones los ultimos 6 dias
            factor = 0.7 if t >= 25 else 1.0
            b[(g, t)] = int(donaciones_base[g] * factor)

    # Inventario inicial: alto en tipos comunes (presion de uso) y muy alto
    # en AB+ (nicho: solo puede satisfacer demanda AB+, sin escape -> fuerza
    # vencimientos porque la demanda diaria de AB+ no alcanza a absorberlo
    # antes de los L=8 dias de vida util)
    I0 = {
        (0, 'O+'): 180, (0, 'A+'): 160, (0, 'B+'): 40, (0, 'AB+'): 80,
        (0, 'O-'): 30,  (0, 'A-'): 25,  (0, 'B-'): 8,  (0, 'AB-'): 5,
    }
    for h in H:
        for g in G:
            # ~medio dia de demanda como stock inicial en cada hospital
            I0[(h, g)] = max(1, demanda_base[h][g] // 2)

    # Capacidad de almacenamiento (apretadas vs flujo diario)
    K = {0: 750, 'H1': 100, 'H2': 70, 'H3': 60, 'H4': 40}

    # Tiempo de traslado banco -> hospital
    tau = {'H1': 1, 'H2': 1, 'H3': 2, 'H4': 3}

    # Costo de oportunidad por usar 1 bolsa de tipo g (mas alto = mas valioso)
    alpha = {'O+': 1, 'A+': 1, 'B+': 1.5, 'AB+': 3,
             'O-': 5, 'A-': 2, 'B-': 2.5, 'AB-': 4}

    # Penalizaciones
    p = 1000     # demanda insatisfecha: critica para pacientes
    eta = 500    # vencimiento: desperdicio caro
    M = 100_000

    # Capacidad diaria de transporte del banco central
    Q = {t: (80 if 14 <= t <= 15 else 150) for t in T}

    return {
        'H': H, 'G': G, 'N': N, 'U': U, 'T': T, 'L': L, 'C': C,
        'd': d, 'b': b, 'I0': I0, 'K': K, 'tau': tau, 'alpha': alpha,
        'p': p, 'eta': eta, 'M': M, 'Q': Q,
    }


# =============================================================================
# 2. CONSTRUCCION DEL MODELO
# =============================================================================

def construir_modelo(datos):
    """
    Construye el modelo Gurobi fiel al PDF v2 (15 restricciones).
    Devuelve (modelo, variables).
    """
    H = datos['H']; G = datos['G']; N = datos['N']
    U = datos['U']; T = datos['T']; L = datos['L']; C = datos['C']
    d = datos['d']; b = datos['b']; I0 = datos['I0']
    K = datos['K']; tau = datos['tau']; alpha = datos['alpha']
    p = datos['p']; eta = datos['eta']; Q = datos['Q']
    # M se usa solo si se activa la restriccion 10 explicita (ver nota mas abajo).

    m = gp.Model('distribucion_sangre')

    # -------------------------------------------------------------------------
    # Variables de decision (seccion 2.5 del PDF)
    # -------------------------------------------------------------------------
    # x_{h,g,u,t} : bolsas tipo g, vida util u, enviadas banco -> hospital h en t
    x = m.addVars(H, G, U, T, lb=0.0, name='x')

    # I_{n,g,u,t} : inventario en nodo n, tipo g, vida util u, periodo t
    I = m.addVars(N, G, U, T, lb=0.0, name='I')

    # y_{h,g,g',u,t} : bolsas donante g (vida util u) usadas en h en t para
    # satisfacer demanda receptor g'. Solo se crean para (g,g') in C: esto
    # implementa R12 (y <= M * c_{g,g'}) por construccion sin necesidad de
    # variables / restricciones extra. Las sumatorias sobre g' in G en R1,
    # R2, R5, R14 y la funcion objetivo se restringen a (g,g') in C; el
    # resultado es matematicamente identico a la formulacion literal del PDF.
    y = m.addVars(
        [(h, g, gpr, u, t) for h in H for (g, gpr) in C for u in U for t in T],
        lb=0.0, name='y'
    )

    # s_{h,g,t} : demanda insatisfecha
    s = m.addVars(H, G, T, lb=0.0, name='s')

    # w_{n,g,t} : bolsas vencidas
    w = m.addVars(N, G, T, lb=0.0, name='w')

    # -------------------------------------------------------------------------
    # Funcion objetivo (seccion 2.6 del PDF)
    # -------------------------------------------------------------------------
    obj = gp.quicksum(
        ((L - u) + tau[h] + alpha[g]) * y[h, g, gpr, u, t]
        for t in T for h in H for (g, gpr) in C for u in U
    )
    obj += p   * gp.quicksum(s[h, g, t] for h in H for g in G for t in T)
    obj += eta * gp.quicksum(w[n, g, t] for n in N for g in G for t in T)
    m.setObjective(obj, GRB.MINIMIZE)

    # -------------------------------------------------------------------------
    # Restricciones (seccion 2.7 del PDF v2, numeradas igual: R1..R15)
    # -------------------------------------------------------------------------

    # R1. Balance de inventario en hospitales (u = 1..L-1, t >= 2)
    for h in H:
        for g in G:
            for u in range(1, L):
                for t in T:
                    if t >= 2:
                        m.addConstr(
                            I[h, g, u, t] ==
                                I[h, g, u + 1, t - 1]
                              + x[h, g, u, t]
                              - gp.quicksum(
                                    y[h, g, gpr, u, t]
                                    for gpr in G if (g, gpr) in C
                                ),
                            name=f'R1_balance_hosp[{h},{g},{u},{t}]'
                        )

    # R2. Balance de inventario en hospitales a vida util maxima (u = L, t >= 2)
    # A u = L no hay aporte desde u+1 (L es el maximo) -> solo entran las
    # recien recibidas via x y se descuentan las usadas via y.
    for h in H:
        for g in G:
            for t in T:
                if t >= 2:
                    m.addConstr(
                        I[h, g, L, t] ==
                            x[h, g, L, t]
                          - gp.quicksum(
                                y[h, g, gpr, L, t]
                                for gpr in G if (g, gpr) in C
                            ),
                        name=f'R2_balance_hosp_uL[{h},{g},{t}]'
                    )

    # R3. Balance de inventario en banco central (u = 1..L-1, t >= 2)
    for g in G:
        for u in range(1, L):
            for t in T:
                if t >= 2:
                    m.addConstr(
                        I[0, g, u, t] ==
                            I[0, g, u + 1, t - 1]
                          - gp.quicksum(x[h, g, u, t] for h in H),
                        name=f'R3_balance_banco[{g},{u},{t}]'
                    )

    # R4. Sangre que recien ingresa al banco central (u = L, t >= 2)
    for g in G:
        for t in T:
            if t >= 2:
                m.addConstr(
                    I[0, g, L, t] ==
                        b[g, t] - gp.quicksum(x[h, g, L, t] for h in H),
                    name=f'R4_donaciones[{g},{t}]'
                )

    # R5. Balance de inventario en hospitales para t = 1 (u = L)
    for h in H:
        for g in G:
            m.addConstr(
                I[h, g, L, 1] ==
                    I0[h, g]
                  + x[h, g, L, 1]
                  - gp.quicksum(
                        y[h, g, gpr, L, 1] for gpr in G if (g, gpr) in C
                    ),
                name=f'R5_balance_hosp_t1[{h},{g}]'
            )

    # R6. Balance de inventario en banco central para t = 1 (u = L)
    for g in G:
        m.addConstr(
            I[0, g, L, 1] ==
                I0[0, g] + b[g, 1]
              - gp.quicksum(x[h, g, L, 1] for h in H),
            name=f'R6_balance_banco_t1[{g}]'
        )

    # R7. Condicion inicial para vida util menor a la maxima (u != L, t = 1):
    # como todo el inventario inicial esta a u = L (supuesto 10 del PDF),
    # a t = 1 no hay stock a u < L, ni envios a u < L, ni uso a u < L.
    for g in G:
        for u in range(1, L):                           # u = 1..L-1
            for n in N:
                m.addConstr(
                    I[n, g, u, 1] == 0,
                    name=f'R7_I_inicial[{n},{g},{u}]'
                )
            for h in H:
                m.addConstr(
                    x[h, g, u, 1] == 0,
                    name=f'R7_x_inicial[{h},{g},{u}]'
                )
                for gpr in G:
                    if (g, gpr) in C:
                        m.addConstr(
                            y[h, g, gpr, u, 1] == 0,
                            name=f'R7_y_inicial[{h},{g},{gpr},{u}]'
                        )

    # R8. Factibilidad del traslado: x = 0 si u <= tau_h
    for h in H:
        for g in G:
            for u in U:
                if u <= tau[h]:
                    for t in T:
                        m.addConstr(
                            x[h, g, u, t] == 0,
                            name=f'R8_traslado[{h},{g},{u},{t}]'
                        )

    # R9. Capacidad de almacenamiento
    for n in N:
        for t in T:
            m.addConstr(
                gp.quicksum(I[n, g, u, t] for g in G for u in U) <= K[n],
                name=f'R9_capacidad[{n},{t}]'
            )

    # R10. Vencimiento en hospitales (t >= 2)
    # Toda bolsa que termina el periodo t-1 a u = 1 vence al pasar a t
    # (su vida util pasa a 0). El uso a u = 1 dentro del periodo t se
    # cuenta en R1, sobre las bolsas que envejecieron de u = 2 a u = 1.
    for h in H:
        for g in G:
            for t in T:
                if t >= 2:
                    m.addConstr(
                        w[h, g, t] == I[h, g, 1, t - 1],
                        name=f'R10_vencimiento_hosp[{h},{g},{t}]'
                    )

    # R11. Vencimiento en banco central (t >= 2)
    for g in G:
        for t in T:
            if t >= 2:
                m.addConstr(
                    w[0, g, t] == I[0, g, 1, t - 1],
                    name=f'R11_vencimiento_banco[{g},{t}]'
                )

    # R12. Compatibilidad entre tipos de sangre
    # No se agrega como restriccion explicita: las variables y solo se
    # crearon para (g,g') in C, asi que las que tendrian c_{g,g'} = 0
    # simplemente no existen. Equivalente a y <= M * 0 = 0.

    # R13. Capacidad diaria de transporte del banco central
    for t in T:
        m.addConstr(
            gp.quicksum(x[h, g, u, t] for h in H for g in G for u in U) <= Q[t],
            name=f'R13_transporte[{t}]'
        )

    # R14. Satisfaccion de demanda
    for h in H:
        for gpr in G:                                   # g' = receptor
            for t in T:
                m.addConstr(
                    gp.quicksum(
                        y[h, g, gpr, u, t]
                        for g in G for u in U if (g, gpr) in C
                    ) + s[h, gpr, t] == d[h, gpr, t],
                    name=f'R14_demanda[{h},{gpr},{t}]'
                )

    # R15. Naturaleza de variables: ya esta dada por lb=0.0 al crear las vars.

    m.update()
    variables = {'x': x, 'I': I, 'y': y, 's': s, 'w': w}
    return m, variables


# =============================================================================
# 3. RESOLUCION E IMPRESION DE RESULTADOS
# =============================================================================

def resolver(modelo, variables, datos, verbose=False):
    """
    Optimiza el modelo e imprime resultados.
      verbose=False -> solo resumen agregado (recomendado para T grande)
      verbose=True  -> tambien imprime cada variable > 0 (puede ser muy largo)
    """
    modelo.optimize()

    status = modelo.Status
    if status != GRB.OPTIMAL:
        print(f"\n[!] El solver no encontro optimo. Status = {status}")
        if status == GRB.INFEASIBLE:
            print("    Modelo infactible. Calculando IIS para diagnosticar...")
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

    # Desglose del objetivo en sus 3 terminos
    obj_envejecimiento = sum(
        ((L - u) + tau[h] + alpha[g]) * y[h, g, gpr, u, t].X
        for t in T for h in H for (g, gpr) in C for u in U
    )
    obj_insatisfecha = p   * sum(s[h, g, t].X for h in H for g in G for t in T)
    obj_vencimiento  = eta * sum(w[n, g, t].X for n in N for g in G for t in T)

    total_demanda = sum(d.values())
    total_y = sum(var.X for var in y.values())
    total_s = sum(var.X for var in s.values())
    total_w_banco  = sum(w[0, g, t].X for g in G for t in T)
    total_w_hosp   = sum(w[h, g, t].X for h in H for g in G for t in T)

    print("\n" + "=" * 70)
    print(f"  Solucion optima. Valor objetivo = {modelo.ObjVal:,.2f}")
    print("=" * 70)
    print(f"  Termino 1 (tiempo+traslado+alpha de bolsas usadas) : {obj_envejecimiento:>12,.2f}")
    print(f"  Termino 2 (p * demanda insatisfecha)               : {obj_insatisfecha:>12,.2f}")
    print(f"  Termino 3 (eta * bolsas vencidas)                  : {obj_vencimiento:>12,.2f}")

    print("\n--- Balance global ---")
    print(f"  Demanda total          : {total_demanda:>8,.0f} bolsas")
    print(f"  Demanda satisfecha     : {total_y:>8,.0f} bolsas "
          f"({100 * total_y / total_demanda:.1f}%)")
    print(f"  Demanda insatisfecha   : {total_s:>8,.0f} bolsas "
          f"({100 * total_s / total_demanda:.1f}%)")
    print(f"  Vencidas en banco      : {total_w_banco:>8,.0f} bolsas")
    print(f"  Vencidas en hospitales : {total_w_hosp:>8,.0f} bolsas")

    # Insatisfecha por tipo de sangre
    print("\n--- Demanda insatisfecha por tipo de sangre ---")
    for g in G:
        s_g = sum(s[h, g, t].X for h in H for t in T)
        d_g = sum(d[h, g, t] for h in H for t in T)
        if d_g > 0:
            pct = 100 * s_g / d_g
            marca = "  <-- ALTO" if pct > 5 else ""
            print(f"  {g:>4} : insatisf={s_g:>6,.0f} / demanda={d_g:>6,.0f} "
                  f"({pct:5.1f}%){marca}")

    # Vencimientos por tipo de sangre
    print("\n--- Vencimientos por tipo de sangre ---")
    for g in G:
        w_g = sum(w[n, g, t].X for n in N for t in T)
        if w_g > tol:
            print(f"  {g:>4} : {w_g:>6,.0f} bolsas vencidas")

    # Patrones diarios: insatisfaccion y vencimiento por dia
    print("\n--- Eventos por dia (solo dias con incidentes) ---")
    print(f"  {'dia':>4} | {'insatisfecha':>13} | {'vencida':>9}")
    for t in T:
        s_t = sum(s[h, g, t].X for h in H for g in G)
        w_t = sum(w[n, g, t].X for n in N for g in G)
        if s_t > tol or w_t > tol:
            print(f"  {t:>4} | {s_t:>13,.0f} | {w_t:>9,.0f}")

    if not verbose:
        return

    print("\n--- Envios banco -> hospital (x > 0) ---")
    for (h, g, u, t), var in x.items():
        if var.X > tol:
            print(f"  x[h={h}, g={g}, u={u}, t={t}] = {var.X:.2f}")

    print("\n--- Bolsas utilizadas (y > 0) ---")
    for (h, g, gpr, u, t), var in y.items():
        if var.X > tol:
            print(f"  y[h={h}, donante={g}, receptor={gpr}, u={u}, t={t}] = {var.X:.2f}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    # ----- Configuracion de la corrida -----
    # Opciones:
    #   ruta='.' (o ruta a la carpeta con los CSVs) -> usa datos reales
    #   ruta=None + escenario='basico' / 'estres'   -> datos sinteticos
    # t_max trunca el horizonte; util para probar antes de correr T=365 completo.
    # ----------------------------------------
    RUTA_DATOS = '.'        # carpeta con los CSVs
    T_MAX = None          # None = 365 dias completo; usar 30 para test rapido

    print(f"\n>>> Datos reales desde '{RUTA_DATOS}', t_max = {T_MAX}\n")
    datos = cargar_datos(ruta=RUTA_DATOS, t_max=T_MAX)
    print(f"  H = {len(datos['H'])} hospitales | G = {len(datos['G'])} tipos")
    print(f"  T = {len(datos['T'])} dias        | L = {datos['L']} vida util")
    print(f"  |C| = {len(datos['C'])} pares compatibles\n")

    modelo, variables = construir_modelo(datos)
    resolver(modelo, variables, datos, verbose=False)
