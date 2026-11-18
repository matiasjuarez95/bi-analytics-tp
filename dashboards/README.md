# Dashboard de seguimiento académico (LMS)

Aplicación interactiva de Streamlit para explorar participación, trazabilidad y rendimiento académico a partir de los datos procesados del LMS.

## Archivo principal

`dashboards/app_TFI.py`

## Ejecución integrada (local)

Desde la raíz del repositorio:

```bash
python -m pip install -r requirements.txt
python -m streamlit run dashboards/app_TFI.py
```

En Streamlit elegí **Administración de datos** desde la navegación lateral.
La aplicación puede abrirse incluso si todavía no hay indicadores calculados.

1. Colocá los Excel originales dentro de `data/raw/`, respetando la estructura que espera el ETL.
2. En **Administración de datos**, pulsá **Actualizar datos**.
3. Esperá a que finalice el procesamiento. Se ejecutan ETL 6.1, validaciones y KPI 6.2.
4. Volvé a **app_TFI** para navegar los siete dashboards.

La aplicación utiliza los CSV locales de `data/processed/`. No se conecta automáticamente con Drive ni se recalcula en cada apertura. El botón requiere acceso a los Excel originales en el equipo que ejecuta Streamlit.

### Alternativa por terminal

Si preferís trabajar desde una terminal, el orquestador ejecuta ambos módulos en el orden correcto:

```bash
python -m src.pipeline
```

Opcionalmente: `python -m src.pipeline --raw data/raw --processed data/processed`.

Los comandos individuales de ETL y KPI siguen disponibles para desarrollo y depuración, pero ya no es necesario ejecutarlos por separado.

### Seguridad y recuperación

- El pipeline primero escribe todo en una carpeta temporal y valida antes de publicar. Si falla el ETL o los KPI, no reemplaza los CSV anteriores.
- El estado de la última publicación exitosa queda en `data/processed/ultima_actualizacion.json` con fecha UTC y cantidad de filas por tabla.
- El archivo `data/.pipeline.lock` evita dos actualizaciones simultáneas. Si el proceso se interrumpe abruptamente, comprobá que no haya otro pipeline activo antes de borrar manualmente ese bloqueo.
- Esta interfaz de administración **está pensada para un servidor local de confianza**: si se despliega remotamente o se expone a otros usuarios, debe agregarse autenticación y autorización antes de habilitar actualizaciones.
- Los Excel y CSV de alumnos no deben incorporarse a Git ni a repositorios públicos.
- El procesamiento completo requiere permisos de escritura sobre `data/processed` y puede consumir memoria según el tamaño de los datos.

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