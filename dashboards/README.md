# Dashboard de seguimiento académico (LMS)

Aplicación interactiva de Streamlit para explorar participación, trazabilidad y rendimiento académico a partir de los datos procesados del LMS.

## Archivo principal

`dashboards/app_TFI.py`

## Cómo ejecutarlo

Desde la raíz del repositorio:

```bash
pip install -r requirements.txt
python -m src.etl.procesar_datos data/raw data/processed
python -m src.kpi data/processed data/processed/kpi
python -m streamlit run dashboards/app_TFI.py
```

Se necesitan los archivos originales en `data/raw/`. Los datos procesados deben estar disponibles en `data/processed/`. Si falta una tabla KPI, la aplicación indica qué proceso ejecutar.

## Vistas del dashboard

| Pestaña | Qué muestra |
|---|---|
| **General** | Resumen por asignatura, estados académicos a la fecha, estudiantes activos e inactivos y actividad semanal. Incluye el promedio de notas en la tabla resumen. |
| **Participación** | Tiempo de uso, cobertura, estudiantes activos por día y evolución diaria de accesos. Permite filtrar por asignatura y rango de fechas, y consultar la actividad diaria de un estudiante. |
| **Trazabilidad** | Eventos por tipo de interacción y mapa de calor por día y hora. El gráfico de eventos usa escala logarítmica para facilitar la comparación entre categorías. |
| **Rendimiento** | Distribución de notas, cantidad de estudiantes por estado y promedio de notas por instrumento. |
| **Notas vs. Participación** | Gráfico de dispersión según la medida de participación elegida y correlaciones de Pearson por asignatura. Permite explorar patrones; no clasifica automáticamente grupos de riesgo. |
| **Ficha individual** | Selección de asignatura y estudiante, estado tipo semáforo, nota, tiempo de uso, interacciones, eventos, notas por instrumento y trazabilidad diaria y por tipo. |
| **Matrícula y alertas** | Comparación entre matriculados y activos, y alertas por asignatura para estudiantes matriculados sin participación y estudiantes no matriculados con actividad. |

## Tablas utilizadas

La aplicación lee las siguientes tablas KPI desde `data/processed/kpi/`:

- `kpi_resumen_asignatura.csv`
- `kpi_estados_a_la_fecha.csv`
- `kpi_alertas_matricula.csv`
- `kpi_histograma_notas.csv`
- `kpi_relacion_estudiante.csv`
- `kpi_interacciones_tipo.csv`
- `kpi_actividad_diaria.csv`
- `kpi_actividad_semanal.csv`
- `kpi_mapa_calor.csv`
- `kpi_notas_instrumento.csv`

También utiliza:

- `data/processed/trazabilidad.csv`, para la evolución de accesos y la actividad individual.
- `data/processed/calificaciones.csv`, para consultar las notas por instrumento en la ficha individual.

## Criterios de lectura

- La población principal corresponde a estudiantes con matrícula vigente. Las alertas también consideran actividad de estudiantes no matriculados.
- Los estados académicos se muestran **a la fecha** y no representan calificaciones finales.
- Las notas se expresan como porcentaje de la escala para facilitar la comparación entre asignaturas.
- Las correlaciones muestran asociación entre variables; no demuestran causalidad.
- Los archivos con datos de estudiantes deben mantenerse fuera del repositorio público.