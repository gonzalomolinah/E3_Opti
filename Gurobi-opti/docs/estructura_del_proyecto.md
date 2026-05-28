# Estructura del proyecto

Este proyecto implementa un modelo de optimizacion para distribuir bolsas de sangre desde un banco central hacia hospitales usando Gurobi-Python. La formulacion matematica esta separada de los datos, la validacion y el codigo que construye/resuelve el modelo.

## Archivos principales

### `AGENTS.md`

Guia de trabajo del proyecto. Define reglas importantes para mantener consistencia entre la formulacion matematica y el codigo, por ejemplo:

- `formulation/model.tex` es la fuente de verdad del modelo.
- Los datos generados deben estar marcados como sinteticos.
- Toda instancia debe cumplir `formulation/data_contract.md`.
- Despues de cambios se deben correr validaciones y tests.

### `formulation/model.tex`

Contiene la formulacion matematica en LaTeX:

- conjuntos;
- parametros;
- variables de decision;
- funcion objetivo;
- restricciones.

Este archivo debe considerarse la referencia principal. Si el codigo Gurobi no coincide con este LaTeX, el codigo debe corregirse o la diferencia debe documentarse explicitamente.

### `formulation/data_contract.md`

Describe el contrato que deben cumplir los datos de entrada:

- que sets debe incluir una instancia;
- que parametros son obligatorios;
- indices esperados para cada parametro;
- unidades;
- reglas de validacion;
- advertencias de plausibilidad;
- fuentes externas que respaldan rangos razonables para datos sinteticos.

Es el documento que conecta la formulacion matematica con los archivos JSON en `data/`.

### `data/schema.json`

Es un esquema JSON formal para validar la estructura basica de una instancia:

- secciones obligatorias;
- nombres de campos;
- tipos de datos;
- valores no negativos;
- compatibilidad binaria.

Este esquema revisa la forma del archivo, pero no valida todos los productos cartesianos. Las validaciones completas estan en `src/validate_data.py`.

### `data/instances/tiny.json`

Instancia pequena y sintetica para probar el flujo completo del proyecto.

Incluye:

- un hospital;
- dos tipos de sangre;
- dos periodos;
- vida util maxima pequena;
- demanda, donaciones, inventario, compatibilidad y capacidades.

Esta instancia esta marcada como sintetica con `metadata.synthetic: true`.

### `data/csv/tiny`

Instancia pequena y sintetica equivalente a `data/instances/tiny.json`, pero expresada como carpeta de CSVs. Sirve para probar la ruta de carga CSV sin cambiar la logica del modelo.

### `docs/formato_csv.md`

Documenta los archivos CSV aceptados, columnas requeridas, aliases compatibles con nombres en espanol y comandos para validar o resolver una carpeta CSV.

## Codigo fuente

### `src/data.py`

Carga archivos JSON y los transforma al formato interno usado por el modelo.

Responsabilidades principales:

- leer una instancia desde disco;
- convertir listas de registros JSON a diccionarios indexados;
- construir el objeto `Data`;
- permitir una verificacion rapida con `python src/data.py data/instances/tiny.json`.

### `src/validate_data.py`

Valida que una instancia cumpla la formulacion y el contrato de datos.

Revisa, entre otras cosas:

- `N == ["0"] + H`;
- `T == [1, ..., Tmax]`;
- `U == [1, ..., L]`;
- parametros completos para todos los indices requeridos;
- valores numericos, finitos y no negativos;
- matriz de compatibilidad completa y binaria;
- `big_m` suficientemente grande;
- advertencias de factibilidad o plausibilidad.

Comando recomendado:

```bash
python src/validate_data.py data/instances/tiny.json
```

### `src/model.py`

Construye el modelo de Gurobi a partir de un objeto `Data`.

Incluye:

- variables `x`, `I`, `y`, `s`, `w`;
- funcion objetivo;
- restricciones de balance, capacidad, compatibilidad, transporte, vencimiento y demanda;
- funciones para imprimir solucion y totales.

Este archivo debe respetar exactamente los indices y restricciones de `formulation/model.tex`.

### `src/solve.py`

Entry point para resolver una instancia con Gurobi.

Flujo:

1. carga el JSON;
2. valida los datos;
3. construye el modelo;
4. resuelve con Gurobi;
5. llama al diagnostico segun el estado del solver.

Comando recomendado:

```bash
python src/solve.py data/instances/tiny.json
```

Si `gurobipy` no esta instalado o no hay licencia activa, muestra un error claro.

### `src/diagnose.py`

Maneja los estados principales de Gurobi:

- `OPTIMAL`;
- `INFEASIBLE`;
- `INF_OR_UNBD`;
- `UNBOUNDED`;
- `TIME_LIMIT`.

Para modelos infeasibles:

- calcula IIS;
- guarda archivos en `diagnostics/`;
- agrupa restricciones conflictivas por familia;
- ejecuta una relajacion de factibilidad sobre una copia del modelo.

Comando recomendado:

```bash
python src/diagnose.py data/instances/tiny.json
```

### `src/report_data.py`

Genera un resumen de escala para una instancia JSON o CSV antes de resolver:

- demanda total;
- demanda promedio diaria;
- donaciones;
- inventario inicial;
- demanda por hospital;
- capacidad en dias de demanda promedio;
- demanda y donaciones por tipo de sangre.

Comando recomendado:

```bash
python src/report_data.py data/csv/realistic_synthetic
```

### `docs/evaluacion_modelo.md`

Explica como evaluar si el modelo es bueno mas alla de obtener `OPTIMAL` en Gurobi. Incluye metricas de servicio, desperdicio, uso de recursos escasos, sensibilidad y fuentes externas para rangos realistas.

## Tests

### `tests/test_data_validation.py`

Prueba la validacion de datos.

Cubre casos como:

- instancia valida;
- indices faltantes;
- indices extra;
- valores no numericos;
- valores negativos;
- compatibilidad invalida;
- `big_m` insuficiente;
- inconsistencias entre `C` y la matriz de compatibilidad.

### `tests/test_model_dimensions.py`

Prueba la estructura del modelo Gurobi.

Verifica:

- cantidad de variables por familia;
- bounds no negativos;
- cantidad esperada de restricciones;
- restricciones de traslado solo cuando `u <= tau[h]`.

Estos tests se saltan automaticamente si `gurobipy` no esta instalado.

### `tests/test_tiny_solve.py`

Prueba resolver la instancia pequena si Gurobi esta disponible.

Si no existe `gurobipy` o no hay licencia, el test se salta con un mensaje explicito.

## Archivos auxiliares

### `.gitignore`

Evita versionar archivos generados o locales:

- `__pycache__/`;
- `*.pyc`;
- `.pytest_cache/`;
- `diagnostics/`;
- logs;
- artefactos de Gurobi como `.lp`, `.mps`, `.ilp`, `.sol`.

### `Entrega_3_Opti (5).pdf`

Documento original de la entrega. Sirve como respaldo del enunciado y contexto del problema.

## Comandos utiles

Validar datos:

```bash
python src/validate_data.py data/instances/tiny.json
```

Validar datos CSV:

```bash
python src/validate_data.py data/csv/tiny
```

Correr tests:

```bash
python -m pytest
```

Resolver instancia:

```bash
python src/solve.py data/instances/tiny.json
```

Resolver instancia CSV:

```bash
python src/solve.py data/csv/tiny
```

Diagnosticar instancia:

```bash
python src/diagnose.py data/instances/tiny.json
```
