Sí. La forma correcta de presentar los datos es:

> “Usamos una instancia sintética, no real, construida para tener órdenes de magnitud plausibles según referencias públicas sobre glóbulos rojos, inventario hospitalario, vida útil, compatibilidad sanguínea y desperdicio esperado.”

**Resumen De La Instancia**

Archivo principal:

[data/csv/realistic_synthetic](C:/Users/benja/OneDrive/Documentos/Gurobi-opti/data/csv/realistic_synthetic)

```text
Horizonte: 365 días
Hospitales: 3
Tipos sanguíneos: 8
Vida útil RBC: 42 días
Demanda total anual: 23360 bolsas
Demanda promedio: 64.0 bolsas/día
Donaciones anuales: 23628 bolsas
Donaciones promedio: 64.7 bolsas/día
Inventario inicial: 448 bolsas
```

La instancia representa una **red regional pequeña**: un hospital de trauma, un hospital general y un hospital comunitario.

**1. Vida Útil: 42 Días**

Usamos:

```text
L = 42
```

Justificación: Canadian Blood Services indica que una unidad de glóbulos rojos tiene vida útil de **42 días desde la recolección**. También Red Cross menciona vida útil de hasta 42 días para RBC, dependiendo del anticoagulante.

Fuentes:  
[Canadian Blood Services - Blood components](https://professionaleducation.blood.ca/en/transfusion/clinical-guide/blood-components)  
[American Red Cross - Blood components](https://prod-www.redcrossblood.org/donate-blood/how-to-donate/types-of-blood-donations/blood-components.html)

**2. Escala De Demanda**

Nuestros datos:

```text
Demanda anual: 23360 bolsas
Promedio diario: 64.0 bolsas/día
```

Justificación: CDC reporta que el sistema de salud de EE.UU. necesita alrededor de **29.000 unidades de glóbulos rojos por día**. AABB reportó **10,32 millones de unidades RBC transfundidas en 2023**, equivalente a unas 28.000 diarias.

Nosotros no estamos modelando un país, sino una red chica de 3 hospitales. Por eso 64 bolsas/día es una escala sintética razonable.

Fuentes:  
[CDC Blood Safety Basics](https://www.cdc.gov/blood-safety/about/index.html)  
[AABB NBCUS 2023](https://www.aabb.org/news-resources/news/article/2025/03/17/results-of-2023-nbcus-suggest-continued-stabilization-of-the-blood-supply)

**3. Capacidades E Inventario**

Datos actuales:

```text
H_TRAUMA:      demanda promedio 37.9/día, capacidad 205, aprox. 5.4 días
H_GENERAL:     demanda promedio 18.0/día, capacidad 100, aprox. 5.6 días
H_COMUNITARIO: demanda promedio 8.1/día, capacidad 48, aprox. 5.9 días
```

Justificación: Canadian Blood Services recomienda como regla práctica mantener inventario equivalente a **4-6 días de uso promedio de glóbulos rojos**. Nuestros hospitales quedan dentro de ese rango.

Fuente:  
[Canadian Blood Services - Blood system inventory management](https://profedu.blood.ca/en/transfusion/best-practices/blood-utilization-best-practices/blood-system-inventory-management-best)

**4. Tipos Sanguíneos**

Demanda anual por tipo:

```text
O-:   1721
O+:   9177
A-:   1199
A+:   7978
B-:    365
B+:   2190
AB-:    52
AB+:   678
```

La lógica usada fue que `O+` y `A+` son los más frecuentes, mientras que `AB-`, `B-` y otros negativos son menos comunes. Red Cross indica que `O+` es el tipo más frecuente, aproximadamente **37%-38%**, y que `O-` es cercano a **7%**.

Fuente:  
[American Red Cross - Blood Types Explained](https://prod-www.redcrossblood.org/donate-blood/blood-types.html)

**5. Compatibilidad**

El archivo `compatibility.csv` usa reglas de compatibilidad de glóbulos rojos. Ejemplos:

```text
O- puede donar a todos.
O+ puede donar a receptores Rh positivos compatibles.
A- puede donar a A-, A+, AB-, AB+.
AB+ recibe de todos, pero como donante RBC es restrictivo.
```

Justificación: Red Cross identifica `O-` como el **donante universal de glóbulos rojos**.

Fuente:  
[American Red Cross - Blood Types Explained](https://prod-www.redcrossblood.org/donate-blood/blood-types.html)

**6. Donaciones**

Datos actuales:

```text
Donaciones anuales: 23628
Demanda anual: 23360
```

Es decir, la oferta anual es levemente mayor que la demanda. Esto fue intencional: no queríamos una instancia trivialmente infeasible, sino una donde el modelo tenga que decidir bien por vida útil, compatibilidad, transporte e inventario.

Esto no viene de una fuente directa; es una **decisión de diseño del escenario sintético**.

**7. Vencimiento Y Wastage**

El modelo penaliza vencimiento con:

```text
expiration_penalty = 150
```

Como referencia, Brown et al. reportan que la tasa nacional de desperdicio de productos sanguíneos emitidos a hospitales puede estar entre **0% y 6%**, y CAP TODAY menciona que una tasa de desperdicio RBC menor a 1% puede ser un benchmark alcanzable en algunos contextos.

Fuentes:  
[Brown et al., Transfusion - PubMed](https://pubmed.ncbi.nlm.nih.gov/23808486/)  
[CAP TODAY - Q&A column](https://www.captodayonline.com/qa-column-0222/)

**8. Penalizaciones Del Modelo**

Estas no son datos “reales”; son parámetros de calibración:

```text
shortage_penalty = 10000
expiration_penalty = 150
substitution_penalty = 5 para g != g'
```

Interpretación:

- `shortage_penalty` alto: dejar pacientes sin sangre debe ser muy malo.
- `expiration_penalty`: botar sangre es malo, pero menos grave que no satisfacer demanda.
- `substitution_penalty`: usar sangre compatible distinta está permitido, pero se prefiere usar el mismo tipo cuando se pueda.

Estas penalizaciones son justificables como criterios operacionales, no como valores monetarios reales.

**Conclusión**

Los datos son defendibles si los presentamos así:

```text
No son datos reales.
Son una instancia sintética escalada.
Respetan vida útil real de RBC: 42 días.
Usan inventarios hospitalarios cercanos a 4-6 días de demanda.
Usan compatibilidad RBC real.
Mantienen distribución sanguínea plausible.
Usan demanda anual consistente con una red regional pequeña.
Usan benchmarks reales de wastage como referencia.
```

La frase más segura para el informe sería:

> “La instancia utilizada es sintética y escalada. Sus valores fueron construidos para ser plausibles respecto de referencias públicas sobre demanda de glóbulos rojos, vida útil, compatibilidad sanguínea, niveles de inventario hospitalario y tasas esperadas de desperdicio. No representa datos reales de un hospital específico.”