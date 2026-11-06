# Datos originales del LMS (.xlsx)

Fuente oficial: [Drive del grupo](https://drive.google.com/drive/folders/1uOrWfHv7u-Sr4mhMpFOuWJr7FNXec7lA), subcarpeta **Datos_LMS_Anonimizados**.

Se trabaja **directamente con Excel** (pandas + openpyxl): no es necesario convertir a CSV.

Descargar los **26 archivos Excel** originales y guardarlos localmente en:
- `data/raw/algebra/` — Álgebra (5 archivos).
- `data/raw/probabilidad/` — Probabilidad y Estadística (11 archivos).
- `data/raw/algoritmos/` — Algoritmos y Estructuras de Datos (7 archivos).
- `data/raw/matriculados/` — matrículas (3 archivos).

Mantener los nombres originales, sin editar las fuentes. No copiar `desktop.ini`.

Por ahora los Excel **no se suben a GitHub**, para evitar duplicados y cambios accidentales; la fuente compartida y versionada por el equipo es la carpeta de Drive. Tras perfilar los archivos, podremos decidir si conviene incorporar una copia controlada al repo. `src/etl/` alojará la lectura, validación y transformación directa desde los Excel.

Ejemplo de lectura en Python:

```python
import pandas as pd

df = pd.read_excel("data/raw/algebra/reporte_participacion_20251024_115228.xlsx", engine="openpyxl")
```
