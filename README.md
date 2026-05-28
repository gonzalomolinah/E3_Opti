# E3_Opti

Implementacion directa en Gurobi del modelo de distribucion de sangre del
Informe 3. `main.py` lee los CSV de la carpeta actual, construye el modelo y
lo resuelve.

## Requisitos

Este repositorio usa la instalacion local existente de **Gurobi 10.0.3** en
`C:\gurobi1003\win64`. Esa version incluye `gurobipy` para Python 3.8 a
3.11; en este equipo el binding ya esta disponible en Python 3.8. El script
solo requiere la biblioteca estandar de Python y ese binding local.

Si se necesita reinstalar el binding suministrado por Gurobi 10.0.3 en un
Python compatible, use la instalacion local:

```powershell
Push-Location C:\gurobi1003\win64
py -3.8 setup.py install
Pop-Location
```

La ejecucion requiere que la licencia de Gurobi este disponible para ese
binding local.

## Ejecucion

```powershell
py -3.8 main.py .
```

El modelo utiliza variables continuas no negativas, tal como se formula en el
informe. Para reducir el tamano de la instancia, solo crea variables de uso de
sangre para pares donante-receptor compatibles, lo que es equivalente a
forzar a cero los pares incompatibles mediante Big-M.
