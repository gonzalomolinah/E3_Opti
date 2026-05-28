# Evaluacion del modelo

Que Gurobi encuentre `OPTIMAL` significa que resolvio correctamente el MILP codificado. No significa, por si solo, que el modelo sea operacionalmente bueno. Para evaluar calidad se deben mirar datos, solucion, sensibilidad y limitaciones.

## Criterios principales

1. **Validez de datos**
   - Todos los parametros indexados deben estar completos.
   - Las cantidades de bolsas deben ser enteras no negativas.
   - La compatibilidad debe ser binaria y completa en `G x G`.
   - `big_m` debe ser suficientemente grande.
   - Toda instancia sintetica debe declararse como sintetica.

2. **Nivel de servicio**
   - Fill rate total: `uso total / demanda total`.
   - Fill rate por hospital, tipo de sangre y periodo.
   - Demanda insatisfecha total y maxima por periodo.
   - Cuidado: el modelo siempre puede ser factible usando `s`, pero una solucion con mucha demanda insatisfecha es mala.

3. **Desperdicio**
   - Tasa de vencimiento: `bolsas vencidas / (inventario inicial + donaciones)`.
   - Vencimiento por nodo, tipo y periodo.
   - Inventario final cercano al vencimiento, especialmente con vida util `u=1`.

4. **Uso de recursos escasos**
   - Cuanto se usa O- para demandas no O-.
   - Cuanto se sustituyen tipos exactos por tipos compatibles.
   - Si se agotan tipos raros mientras tipos comunes vencen, hay que revisar penalizaciones y compatibilidad.
   - La penalizacion de sustitucion `beta[g,g']` deberia reducir sustituciones innecesarias sin impedir transfusiones compatibles cuando evitan faltantes o vencimiento.

5. **Restricciones activas**
   - Capacidad de transporte usada sobre `Q_t`.
   - Capacidad de almacenamiento usada sobre `K_n`.
   - Restricciones de traslado `u <= tau_h`.

6. **Sensibilidad**
   - Cambiar demanda, donaciones, `Q_t`, `K_n`, `p`, `eta`, `alpha_g`.
   - Revisar si la solucion cambia de forma razonable.
   - Probar escenarios: abundancia, escasez, transporte apretado, almacenamiento apretado, alta demanda y alto inventario viejo.

## Limitaciones actuales

- `tau_h` no retrasa llegadas entre periodos; solo penaliza y bloquea envios con vida util insuficiente.
- La vida util no se descuenta durante el traslado bajo esta aproximacion.
- La capacidad se evalua sobre inventario al final del periodo.
- Los datos `tiny` solo prueban que el pipeline corre; no validan comportamiento realista.
- Una solucion optima puede ser operacionalmente pobre si los parametros de penalizacion no reflejan prioridades reales.

## Fuentes para rangos realistas

- CDC reporta que el sistema de salud de EE.UU. necesita aproximadamente 29.000 unidades de globulos rojos por dia: <https://www.cdc.gov/blood-safety/about/index.html>.
- Canadian Blood Services indica vida util de 42 dias para unidades RBC y almacenamiento a 1-6 C: <https://profedu.blood.ca/en/transfusion/clinical-guide/blood-components>.
- Canadian Blood Services recomienda inventario hospitalario cercano a 4-6 dias de uso promedio de RBC: <https://profedu.blood.ca/en/transfusion/best-practices/blood-utilization-best-practices/blood-system-inventory-management-best>.
- American Red Cross resume compatibilidad ABO/Rh y O- como donante universal de globulos rojos: <https://prod-www.redcrossblood.org/donate-blood/blood-types.html>.
- Estudios de desperdicio reportan rangos usuales bajos y escenarios con mayor desperdicio; por ejemplo Brown et al. reporta desperdicio hospitalario nacional entre 0% y 6% para productos emitidos: <https://pubmed.ncbi.nlm.nih.gov/23808486/>.

## Interpretacion de una buena corrida

Una corrida razonable deberia reportar:

- `OPTIMAL` o solucion factible con gap pequeno.
- Demanda insatisfecha baja o explicada por escenarios de escasez.
- Vencimiento bajo en escenario normal.
- Sin vencimiento alto al mismo tiempo que hay alta demanda insatisfecha, salvo por incompatibilidad o transporte/capacidad apretada.
- Uso limitado de tipos raros para demandas que podrian satisfacerse con tipos mas comunes.
- Resultados estables ante cambios pequenos de parametros.
