# Entrega 3 - Modelo de distribucion de sangre

## Como ejecutar

Desde la carpeta raiz del entregable:

```powershell
py main.py
```

El programa carga los datos desde:

```text
datos/
```

## Configuracion usada

- Horizonte: `T_MAX = 182` dias.
- Vida util maxima: `L = 42` dias.
- TimeLimit de Gurobi: `1800` segundos.
- Funcion objetivo con criterio FEFO: usa `u` como vida util restante en vez de `(L-u)`.

## Archivos principales

- `main.py`: carga datos, construye el modelo, resuelve con Gurobi e imprime resultados agregados.
- `datos/`: archivos CSV de la instancia.
- `resultados/resultados.txt`: resumen procesado de la corrida reportada.
- `cambios_fefo.md`: documentacion del cambio en la funcion objetivo.
