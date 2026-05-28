# Instancia de datos adaptada al formato de los CSV subidos

Esta carpeta contiene los archivos CSV con los mismos nombres y esquemas principales que los archivos subidos al proyecto:

- tipos_sangre.csv
- compatibilidad.csv
- donaciones.csv
- demanda.csv
- hospitales.csv
- capacidad_nodos.csv
- inventario_inicial.csv
- parametros_globales.csv
- capacidad_transporte.csv

Adicionalmente se incluyen `fuentes.csv` y `resumen_instancia.csv` para documentar supuestos, fuentes y totales agregados.

## Criterio de construcción

- Horizonte: T = 365 días.
- Vida útil: L = 42 días.
- Demanda anual total calibrada: 14718 bolsas de glóbulos rojos.
- Donaciones anuales totales calibradas: 16418 bolsas de glóbulos rojos.
- Semilla aleatoria reproducible: 1113.
- La muestra diaria de demanda y donaciones incorpora variación por mes, día de semana y ruido aleatorio leve, manteniendo los totales anuales exactos.
- La matriz `compatibilidad.csv` está en sentido DONANTE -> RECEPTOR.
- El parámetro `alpha` usa la última tabla acordada en el chat: AB+ = 1, A+ = 2, B+ = 3, AB- = 4, O+ = 6, A- = 8, B- = 10, O- = 15.

## Notas de implementación

- `demanda.csv` contiene una fila por hospital, tipo sanguíneo y día.
- `donaciones.csv` contiene una fila por tipo sanguíneo y día.
- `inventario_inicial.csv` asume vida útil inicial máxima L, coherente con el supuesto del modelo.
- `capacidad_transporte.csv` usa Q_t = 60 en días hábiles, 52 sábado y 45 domingo.
