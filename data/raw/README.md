# Datos originales del LMS

Las fuentes oficiales están disponibles en el [Drive del grupo](https://drive.google.com/drive/folders/1uOrWfHv7u-Sr4mhMpFOuWJr7FNXec7lA), subcarpeta **Datos_LMS_Anonimizados**. Son archivos Excel, no CSV.

Descargar las carpetas de las tres materias y **Matriculados**, conservando los nombres de los archivos originales. Ubicarlas bajo `data/raw/`:

- `data/raw/algebra/` — Excel de Álgebra.
- `data/raw/algoritmos/` — Excel de Algoritmos y Estructuras de Datos.
- `data/raw/probabilidad/` — Excel de Probabilidad y Estadística.
- `data/raw/matriculados/` — Excel de matriculados (tres materias).

Los directorios pueden crearse manualmente. No modificar los Excel originales. No subir archivos `desktop.ini`.

Los Excel se excluyen de Git con `.gitignore`; los CSV generados en `data/interim/csv/` tampoco se versionan inicialmente, hasta validar columnas, tipos, identificadores y tamaños.

Ejecutar desde la raíz del repositorio:

```bash
python -m pip install -r requirements.txt
python -m src.etl.excel_to_csv
```

Este proceso **convierte** cada hoja de cada Excel a CSV preservando valores, sin limpiar ni calcular métricas; el modelado vendrá después. Ver `docs/fuentes_y_decisiones.md`.
