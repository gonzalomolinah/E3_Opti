# Modificacion del modelo

Este documento compara el modelo original de la entrega 3 con el modelo que se
esta usando actualmente en el proyecto. La fuente matematica viva del proyecto
es `formulation/model.tex`; el codigo Gurobi correspondiente esta en
`src/model.py`.

El modelo original corresponde al PDF `Entrega_3_Opti (5).pdf` y a la
formulacion inicial. El modelo actual mantiene la misma estructura principal,
pero incorpora correcciones y decisiones de implementacion para que el modelo
sea ejecutable, interpretable y defendible con datos sinteticos.

## Resumen comparativo

| Aspecto | Modelo original entrega 3 | Modelo actual del proyecto | Tipo de cambio |
|---|---|---|---|
| Horizonte | El PDF describe un horizonte de `T = 365` periodos. | La instancia principal `data/csv/realistic_synthetic` usa `T = 365`. | Alineacion con el PDF. |
| Vida util | `U = {1,...,L}` y `L` como vida util maxima. | Se mantiene igual; los datos usan `L = 42` para globulos rojos. | Sin cambio estructural. |
| Nodos | `N = {0} union H`, donde `0` es el banco central. | Se mantiene igual; los datos validan `N = ["0"] + H`. | Sin cambio. |
| Variables | `x`, `I`, `y`, `s`, `w` no negativas. | Las mismas variables, pero declaradas enteras no negativas. | Correccion operativa. |
| Funcion objetivo | Edad/tiempo de sangre usada, traslado, `alpha_g`, demanda insatisfecha y vencimiento. | Se mantiene y se agrega `beta_{g,g'}` para penalizar sustituciones compatibles. | Extension controlada. |
| Compatibilidad | `y <= M c_{g,g'}`. | Se mantiene igual. | Sin cambio. |
| Demanda insatisfecha | Variable `s_{h,g,t}` con penalizacion `p`. | Se mantiene igual. | Sin cambio. |
| Vencimiento | Definido para `t >= 2`. | Se agrega `w_{n,g,1} = 0`. | Correccion de condicion inicial. |
| Traslado `tau_h` | Aparece en objetivo y en restriccion `x = 0` si `u <= tau_h`; no modela llegada diferida. | Se mantiene como traslado simplificado y se documenta explicitamente. | Clarificacion. |
| Vida util durante traslado | El modelo no descuenta vida util durante el traslado. | Se mantiene esa aproximacion; `tau_h` solo filtra factibilidad y penaliza. | Clarificacion. |
| Capacidad | `sum I <= K_n`. | Se mantiene; se documenta que es inventario final de periodo. | Clarificacion. |
| Datos | No habia contrato operativo completo. | Se agregan JSON/CSV, validacion y contrato de datos. | Implementacion. |
| Diagnostico | No estaba automatizado. | Se agregan diagnosticos Gurobi, IIS y `feasRelax`. | Implementacion. |
| Output | Salida directa de variables o log solver. | Salida resumida con KPIs y opcion `--report`/`--details`. | Implementacion. |

## Cambios matematicos aplicados

### 1. Variables enteras

En el PDF, la naturaleza de variables aparece como:

```text
x, I, y, s, w >= 0
```

Eso permite soluciones fraccionales, por ejemplo `0.3` bolsas de sangre. En el
codigo actual todas las variables se declaran como enteras no negativas:

```python
vtype=GRB.INTEGER, lb=0
```

Criterio usado: las decisiones representan bolsas fisicas de sangre, por lo que
no tiene sentido operacional permitir fracciones.

### 2. Vencimiento inicial

El modelo original define vencimiento solo para `t >= 2`:

```text
w_{h,g,t} = I_{h,g,1,t-1}
w_{0,g,t} = I_{0,g,1,t-1}
```

El modelo actual agrega:

```text
w_{n,g,1} = 0
```

Criterio usado: antes de iniciar la planificacion no deberia registrarse sangre
vencida dentro del horizonte. Esto tambien evita que `w[n,g,1]` quede solo
determinado indirectamente por su penalizacion en la funcion objetivo.

### 3. Penalizacion por sustitucion compatible

El modelo original permitia usar cualquier tipo compatible sin costo extra
explicito por sustituir:

```text
[(L-u) + tau_h + alpha_g] y_{h,g,g',u,t}
```

El modelo actual usa:

```text
[(L-u) + tau_h + alpha_g + beta_{g,g'}] y_{h,g,g',u,t}
```

Donde normalmente:

```text
beta_{g,g} = 0
beta_{g,g'} > 0 si g != g'
```

Criterio usado: una transfusion compatible no es incorrecta, pero
operacionalmente conviene preferir el mismo tipo cuando sea posible y reservar
tipos flexibles o escasos para casos donde realmente ayuden a evitar demanda
insatisfecha o vencimiento.

## Decisiones de modelacion documentadas

### Traslado simplificado

El modelo original usa `tau_h`, pero no incorpora variables de transito ni
llegadas diferidas. Por lo tanto, un envio `x_{h,g,u,t}` queda disponible en el
mismo periodo agregado `t`.

El modelo actual mantiene esa decision y la deja explicita:

- `tau_h` penaliza operar con hospitales mas lejanos;
- `tau_h` impide enviar bolsas cuya vida util no alcanza para llegar;
- no existe inventario en transito;
- no se descuenta vida util durante el traslado.

La alternativa mas realista seria modelar que un despacho realizado en `t`
llega en `t + tau_h` y que la vida util baja durante el traslado. Esa opcion
no se implemento porque cambia la formulacion y aumenta la complejidad.

### Capacidad de almacenamiento

La restriccion se mantiene como:

```text
sum_{g,u} I_{n,g,u,t} <= K_n
```

El modelo actual documenta que `I_{n,g,u,t}` representa inventario al final del
periodo. Por lo tanto, la capacidad limita inventario final, no necesariamente
el maximo inventario fisico intra-dia.

## Datos actuales

El proyecto ahora soporta datos en JSON y CSV. La instancia principal es:

```text
data/csv/realistic_synthetic
```

Estado actual de esa instancia:

```text
T = 365 dias
L = 42 dias
Hospitales = 3
Tipos sanguineos = 8
Demanda total anual = 23360 bolsas
Donaciones anuales = 23628 bolsas
Inventario inicial = 448 bolsas
```

La instancia es sintetica y escalada. No representa hospitales reales. Sus
valores se justifican por ordenes de magnitud y reglas publicas:

- vida util RBC de 42 dias;
- inventario hospitalario cercano a 4-6 dias de uso promedio;
- compatibilidad ABO/Rh para globulos rojos;
- demanda anual plausible para una red regional pequena;
- desperdicio esperado comparado contra referencias de wastage hospitalario.

El patron de demanda, donaciones y transporte se construyo repitiendo un patron
sintetico de 14 dias hasta completar 365 dias. Esto permite estudiar un
horizonte anual sin afirmar que la serie sea historica.

## Validacion agregada

El proyecto valida:

- `N = ["0"] + H`;
- `T = [1,...,Tmax]`;
- `U = [1,...,L]`;
- completitud de parametros indexados;
- no negatividad de cantidades, costos y capacidades;
- compatibilidad binaria completa en `G x G`;
- `big_m` positivo y suficientemente grande;
- tiempos de traslado enteros no negativos;
- penalizacion de sustitucion completa y no negativa;
- advertencias de plausibilidad sobre inventario, vencimiento y traslado.

Comandos:

```bash
python src/validate_data.py data/instances/tiny.json
python src/validate_data.py data/csv/tiny
python src/validate_data.py data/csv/realistic_synthetic
python -m pytest
```

## Output actual del solver

Con `T = 365`, imprimir todas las variables positivas no es practico. Por eso
`solve.py` ahora imprime por defecto un resumen operacional:

- estado de Gurobi;
- valor objetivo;
- demanda total, demanda satisfecha, demanda insatisfecha y fill rate;
- sangre vencida total y tasas de wastage;
- despachos totales y uso total;
- inventario final y dias de inventario final;
- uso con mismo tipo, uso por sustitucion compatible y tasa de sustitucion;
- utilizacion de transporte y dias saturados;
- descomposicion del objetivo;
- uso de `O-` para `O-` y para otros receptores.

Uso recomendado:

```bash
python src/solve.py data/csv/realistic_synthetic --quiet
```

Para ver desagregados por hospital, tipo, nodo y top periodos:

```bash
python src/solve.py data/csv/realistic_synthetic --quiet --report
```

Para ver todas las variables positivas de despacho y uso:

```bash
python src/solve.py data/csv/realistic_synthetic --details
```

## Resultado anual observado

Con la instancia anual, Gurobi encontro una solucion optima con:

```text
Demanda total anual: 23360
Demanda insatisfecha: 23
Uso total: 23337
Sangre vencida: 530
Despachos totales: 23608
Valor objetivo: 454337
```

Interpretacion:

- el nivel de servicio es aproximadamente `99.90%`;
- el wastage respecto al uso es aproximadamente `2.27%`;
- la solucion ya no es artificialmente perfecta como en horizontes cortos;
- aunque la oferta anual supera la demanda anual, las restricciones de tiempo,
  tipo sanguineo, vida util, transporte y capacidad pueden generar demanda
  insatisfecha puntual.

## Estado actual frente al modelo original

El modelo actual preserva la estructura central del modelo de la entrega 3:

- mismo sistema banco central-hospitales;
- mismos conjuntos principales;
- mismas variables principales;
- mismos balances de inventario;
- misma satisfaccion de demanda;
- misma compatibilidad por Big-M;
- misma capacidad de transporte;
- misma capacidad de almacenamiento.

Las diferencias relevantes son:

1. variables enteras para representar bolsas;
2. restriccion inicial `w[n,g,1] = 0`;
3. penalizacion `beta[g,g']` para sustituciones compatibles;
4. documentacion explicita de traslado simplificado;
5. documentacion explicita de capacidad como inventario final;
6. datos CSV/JSON validados;
7. diagnosticos y reportes para interpretar soluciones.

Con estos cambios, el modelo queda mas consistente para correr en Gurobi y mas
defendible para explicar resultados, sin redisenar la estructura matematica base
de la entrega.
