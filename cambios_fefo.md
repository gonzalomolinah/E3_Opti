# Cambio FEFO en `simple/main.py`

## Cambio aplicado

Se cambio el termino de edad de la sangre en la funcion objetivo:

```python
((L - u) + tau[h] + alpha[g]) * y[h, g, gpr, u, t]
```

por:

```python
(u + tau[h] + alpha[g]) * y[h, g, gpr, u, t]
```

El mismo cambio se aplico en el calculo posterior de `obj_calidad` para que el
reporte del objetivo sea consistente con el modelo optimizado.

## Motivo

En el modelo, `u` representa vida util restante. Por lo tanto:

- `u = 1` significa bolsa cercana a vencer.
- `u = L` significa bolsa fresca.

Con el termino anterior `(L - u)`, una bolsa fresca tenia menor costo que una
bolsa vieja:

```text
u = L  -> L - u = 0
u = 1  -> L - u = L - 1
```

Eso incentivaba usar primero bolsas frescas y dejar vencer bolsas antiguas.

Con el nuevo termino `u`, una bolsa con menor vida util restante tiene menor
costo:

```text
u = 1  -> costo menor
u = L  -> costo mayor
```

Esto implementa una politica FEFO: first expired, first out.

## Alcance

Este cambio modifica solo la preferencia de uso por edad de la sangre.

No se cambiaron:

- balances de inventario;
- restricciones de demanda;
- restricciones de compatibilidad;
- donaciones obligatorias;
- capacidad de transporte;
- capacidad de almacenamiento;
- parametros `p`, `eta`, `alpha` o `tau`.

## Interpretacion esperada

Al correr nuevamente `main.py`, se espera que el vencimiento baje respecto a la
version anterior, especialmente alrededor del dia 43, donde vencian muchas
bolsas asociadas al inventario inicial.

Si sigue habiendo mucho vencimiento, la causa probable ya no sera FEFO sino la
entrada obligatoria de todas las donaciones y la ausencia de una politica de
inventario objetivo.
