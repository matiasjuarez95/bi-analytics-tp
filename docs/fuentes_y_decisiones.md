# Fuentes, alcance y decisiones pendientes

## Material de referencia

- [Consigna oficial del TFI](https://docs.google.com/document/d/11AAnctgYEXbOcAUvmsXw2j_GH00fOjt80c4mry4-yAg/edit)
- [Drive de datos originales](https://drive.google.com/drive/folders/1uOrWfHv7u-Sr4mhMpFOuWJr7FNXec7lA)

El inventario visible contiene **26 Excel (.xlsx)**, distribuidos así:

| Materia | Matrícula | Participación | Trazabilidad | Calificaciones | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Álgebra | 1 | 1 | 1 | 3 | 6 |
| Probabilidad y Estadística | 1 | 1 | 1 | 9 | 12 |
| Algoritmos y Estructuras de Datos | 1 | 1 | 1 | 5 | 8 |
| **Total** | **3** | **3** | **3** | **17** | **26** |

**Formato de trabajo:** leer los `.xlsx` directamente con `pandas.read_excel` y `openpyxl`, sin conversión obligatoria a CSV. Conservar los Excel originales.

## Reglas académicas de la consigna

- **Álgebra:** sistema acumulativo, con Parcial 1 (25), Parcial 2 (25), cinco autoevaluaciones (10 cada una) y recuperatorio (20), máximo 120. Libre <60, regular 60–84, promociona >=85.
- **Probabilidad y Estadística:** promedio de los instrumentos, cada uno sobre 100. Libre <60, regular 60–84, promociona >=85.
- **Algoritmos y Estructuras de Datos:** promedio de autoevaluaciones sobre 100. Libre <60, regular 60–89, promociona >=90.

No asumir cómo impactan notas faltantes ni recuperatorios hasta inspeccionar cada instrumento y consensuar su tratamiento.

## Antes de modelar

1. Auditar hojas, encabezados, tipos, granularidad y cantidad de registros de los 26 Excel.
2. Identificar las claves para cruzar matrícula, participación, trazabilidad y calificaciones.
3. Definir inactividad, sesiones, cobertura y unidad temporal de cada KPI.
4. Detectar duplicados, nulos, registros de actividad sin matrícula y matrículas sin actividad.
5. Diseñar un modelo analítico que evite multiplicar filas y distorsionar métricas.
6. Definir las transformaciones ETL y las pruebas correspondientes.
7. Acordar si se versionarán datasets en GitHub o se mantendrán solo en Drive.

## Entregables

Regularización: al menos tres dashboards funcionales y un informe de avance con KPI calculados.
TFI final: siete vistas interactivas, informe técnico, análisis y defensa.
