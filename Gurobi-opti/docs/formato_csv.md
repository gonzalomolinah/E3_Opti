# Formato CSV de instancias

El proyecto puede cargar datos desde un archivo JSON o desde una carpeta de CSVs. En ambos casos el flujo es el mismo:

```text
datos CSV -> instancia normalizada -> validacion -> modelo Gurobi
```

Esto evita mantener dos logicas de validacion distintas. Si una instancia CSV se carga correctamente, debe cumplir las mismas reglas de `formulation/data_contract.md`.

## Uso

Validar una carpeta CSV:

```bash
python src/validate_data.py data/csv/tiny
```

Resolver una carpeta CSV:

```bash
python src/solve.py data/csv/tiny
```

Por defecto, `solve.py` imprime solo el resumen de la solucion. Para ocultar el
log de Gurobi y ver una salida compacta:

```bash
python src/solve.py data/csv/realistic_synthetic --quiet
```

La salida compacta incluye:

- demanda total, demanda satisfecha, demanda insatisfecha y fill rate;
- sangre vencida total y tasas de wastage;
- despachos, uso, inventario final y dias de inventario final;
- uso con mismo tipo, uso por sustitucion compatible y tasa de sustitucion;
- uso de capacidad de transporte y dias saturados;
- descomposicion del objetivo.

Para agregar desagregados por hospital, tipo sanguineo, nodo y top periodos:

```bash
python src/solve.py data/csv/realistic_synthetic --quiet --report
```

Para imprimir todas las variables positivas de despacho y uso:

```bash
python src/solve.py data/csv/realistic_synthetic --details
```

## Archivos requeridos

### `metadata.csv`

Opcional. Si no existe, se genera metadata sintetica por defecto.

Columnas:

```csv
name,synthetic,description
tiny_csv_synthetic,true,Synthetic CSV instance.
```

Para datos generados, `synthetic` debe ser `true`.

### `global_parameters.csv`

Tambien se aceptan los nombres `scalars.csv` o `parametros_globales.csv`.

Columnas:

```csv
parameter,value
L,2
T,2
shortage_penalty,1000
expiration_penalty,50
big_m,100
```

Aliases aceptados:

- `p` para `shortage_penalty`;
- `eta` para `expiration_penalty`;
- `M` para `big_m`.

### `hospitals.csv`

Tambien se acepta `hospitales.csv`.

Columnas canonicas:

```csv
h,travel_time,storage_capacity
H1,1,10
```

Aliases aceptados:

- `hospital_id` para `h`;
- `tau` o `tau_dias` para `travel_time`;
- `capacidad_K_bolsas` para `storage_capacity`.

Si se usa un archivo separado `storage_capacity.csv`, la columna `storage_capacity` puede omitirse de `hospitals.csv`.

Si se usa un archivo separado `travel_time.csv`, la columna `travel_time` puede omitirse de `hospitals.csv`.

### `blood_types.csv`

Tambien se acepta `tipos_sangre.csv`.

Columnas canonicas:

```csv
g,use_penalty
O-,0
O+,0
```

Aliases aceptados:

- `tipo_sangre` para `g`;
- `alpha` para `use_penalty`.

Si se usa un archivo separado `use_penalty.csv`, la columna `use_penalty` puede omitirse de `blood_types.csv`.

### `compatibility.csv`

Tambien se acepta `compatibilidad.csv`.

Columnas:

```csv
donor,receiver,value
O-,O-,1
O-,O+,1
O+,O-,0
O+,O+,1
```

Aliases aceptados:

- `tipo_donante` para `donor`;
- `tipo_receptor` para `receiver`;
- `compatible` para `value`.

Debe incluir la matriz completa `G x G`, con valores `0` o `1`.

### `demand.csv`

Tambien se acepta `demanda.csv`.

Columnas:

```csv
h,g,t,value
H1,O-,1,1
```

Aliases aceptados:

- `hospital_id` para `h`;
- `tipo_sangre` para `g`;
- `demanda_bolsas` para `value`.

Debe incluir todos los indices `H x G x T`.

### `donations.csv`

Tambien se acepta `donaciones.csv`.

Columnas:

```csv
g,t,value
O-,1,1
```

Aliases aceptados:

- `tipo_sangre` para `g`;
- `donaciones_bolsas` para `value`.

Debe incluir todos los indices `G x T`.

### `initial_inventory.csv`

Tambien se acepta `inventario_inicial.csv`.

Columnas:

```csv
n,g,value
0,O-,1
H1,O-,0
```

Aliases aceptados:

- `nodo_id` para `n`;
- `tipo_sangre` para `g`;
- `inventario_inicial_bolsas` para `value`.

Debe incluir todos los indices `N x G`.

### `storage_capacity.csv`

Opcional si la capacidad viene en `hospitals.csv` y el banco central viene como `K0` en `global_parameters.csv`. Tambien se acepta `capacidad_nodos.csv`.

Columnas:

```csv
n,value
0,10
H1,10
```

Aliases aceptados:

- `nodo_id` para `n`;
- `capacidad_K_bolsas` para `value`.

### `travel_time.csv`

Opcional si `travel_time` viene en `hospitals.csv`.

Columnas:

```csv
h,value
H1,1
```

El valor debe ser entero no negativo, porque el modelo usa periodos discretos.

### `use_penalty.csv`

Opcional si `use_penalty` viene en `blood_types.csv`.

Columnas:

```csv
g,value
O-,0
O+,0
```

### `substitution_penalty.csv`

Opcional. Si no existe, se genera automaticamente con valor `0` para mismo tipo y `5` para sustituciones `donor != receiver`.

Columnas:

```csv
donor,receiver,value
O-,O-,0
O-,O+,5
O+,O-,5
O+,O+,0
```

Aliases aceptados:

- `tipo_donante` para `donor`;
- `tipo_receptor` para `receiver`;
- `penalty` o `penalizacion` para `value`.

Esta penalizacion no prohibe transfusiones compatibles. Solo incentiva usar el mismo tipo sanguineo cuando sea posible y reservar tipos mas flexibles o escasos.

### `max_transport.csv`

Tambien se acepta `capacidad_transporte.csv`.

Columnas:

```csv
t,value
1,5
2,5
```

Alias aceptado:

- `Q_t` para `value`.

Debe incluir todos los periodos `T`.

## Validaciones importantes

La carga CSV reutiliza `src/validate_data.py`, por lo que se revisa:

- indices completos;
- indices extra fuera de los conjuntos;
- duplicados;
- cantidades enteras no negativas;
- compatibilidad binaria;
- `N = ["0"] + H`;
- `U = [1, ..., L]`;
- `T = [1, ..., Tmax]`;
- `big_m` suficientemente grande;
- warnings de factibilidad y plausibilidad.
