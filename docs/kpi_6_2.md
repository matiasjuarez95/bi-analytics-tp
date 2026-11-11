# Punto 6.2 — KPI de participación, trazabilidad, rendimiento y matrícula

## Alcance y fuentes

Implementación: `src/kpi.py` · pruebas: `tests/test_kpi_6_2.py`.

El módulo consume **solo** las salidas del ETL 6.1:
`situacion_estudiante.csv`, `trazabilidad.csv` y `calificaciones.csv`.
No transforma nuevamente los Excel ni cambia las reglas académicas.

Desde la raíz:

```bash
python -m src.etl.procesar_datos data/raw data/processed
python -m src.kpi data/processed data/processed/kpi
python -m pytest tests/ -q
```

En Colab, después de ejecutar `salidas = etl.ejecutar(...)`:

```python
from src.kpi import calcular_kpis
kpis = calcular_kpis(salidas["situacion_estudiante"],
                     salidas["trazabilidad"],
                     salidas["calificaciones"])
display(kpis["kpi_resumen_asignatura"])
```

Las tablas KPI CSV se guardan bajo `data/processed/kpi/`, que sigue excluida del control de versiones.

## Definiciones y denominadores

**Unidad de análisis:** una fila por `(id_estudiante, asignatura)`. Una persona que cursa tres materias aporta tres inscripciones, no tres personas distintas.

**Población estándar:** `matriculado == True` (matrícula vigente). Los indicadores de rendimiento, participación, trazabilidad e instrumentos excluyen a los no matriculados, pero las alertas los incluyen expresamente.

**Estados:** se usa `estado_provisorio`, que indica **situación a la fecha de corte**, no calificación final ni acreditación definitiva. El conjunto académico incluye «Sin notas» en el denominador de los porcentajes por estado, sin clasificarlo como Libre.

**Escala de nota:** se normaliza `nota_a_la_fecha / escala_nota_a_la_fecha * 100`. Esto permite comparar Álgebra (0 a 120) con Probabilidad/Algoritmos (0 a 100), pero no elimina las diferencias entre sus reglas ni la naturaleza estimada de la proyección de Álgebra. La nota promedio excluye filas «Sin notas» y reporta su número por separado.

**Actividad:** `tiene_actividad` es la definición oficial del ETL (`interacciones` de participación > 0 o eventos de trazabilidad > 0). Para la cobertura, la unidad y denominador es una inscripción vigente; la tasa = activos / matriculados × 100.

**Tiempo medio de uso:** minutos estimados registrados por el LMS / total de matriculados vigentes, con cero para quienes no tienen registro. No equivale a duración medida de sesiones. También se informa el número de activos.

**Sesiones:** la consigna menciona promedio de sesiones, pero el ETL no cuenta con un identificador de sesión o un criterio consensuado de separación temporal. **No se publica un KPI de sesiones inventado**. Es posible agregar sesiones estimadas a partir de intervalos de inactividad, siempre que se acuerde un umbral y se rotule como estimación.

**Eventos temporales:** cada fila de trazabilidad representa un evento, no un ingreso o sesión. Se conservan eventos con `duplicado_potencial=True` por decisión de ETL; las sumas de eventos los incluyen. Se muestran eventos por día, semana (inicio lunes), mes, tipo y mapa de calor día/hora. Las series solo contienen días/semanas/meses con al menos un evento, no fechas rellenadas artificialmente con cero.

**Correlaciones:** coeficiente de Pearson entre nota porcentual y tiempo/interacciones/eventos para matriculados con nota y variables no nulas. No es causalidad; devuelve NaN si hay menos de 3 pares o alguna variable es constante.

## Salidas para los dashboards

| Tabla CSV | Granularidad | Contenido |
|---|---|---|
| `kpi_resumen_asignatura` | asignatura | estudiantes matriculados, activos/inactivos, tasas, interacciones y tiempo medios, nota media, Pearson |
| `kpi_estados_a_la_fecha` | asignatura × estado | cantidades y porcentajes Promociona/Regular/Libre/Sin notas (provisorios) |
| `kpi_alertas_matricula` | asignatura × alerta | matriculados sin participación y no matriculados con actividad |
| `kpi_histograma_notas` | asignatura × intervalo | histograma porcentual 0–100 entre matriculados con nota |
| `kpi_relacion_estudiante` | estudiante × asignatura | base anonimizada por ID para dispersión y selección individual |
| `kpi_interacciones_tipo` | asignatura × tipo | eventos por categoría LMS |
| `kpi_actividad_diaria` | asignatura × fecha | eventos y estudiantes distintos activos ese día |
| `kpi_actividad_semanal` | asignatura × lunes | eventos y estudiantes distintos activos esa semana |
| `kpi_actividad_mensual` | asignatura × mes | eventos y estudiantes distintos activos ese mes |
| `kpi_mapa_calor` | asignatura × día semanal × hora | eventos para mapa de calor temporal |
| `kpi_notas_instrumento` | asignatura × instrumento | nota media y cantidad de evaluaciones utilizadas en la calificación |

## Mapeo de dashboards de la consigna

1. **General:** resumen, estados y actividad semanal.
2. **Participación:** resumen y actividad por fecha. El nivel estudiante puede derivarse desde la tabla central del ETL.
3. **Trazabilidad:** tipos, actividad temporal y mapa de calor.
4. **Rendimiento:** estados, histogramas y notas por instrumento.
5. **Relación notas–participación:** tabla `kpi_relacion_estudiante` y correlaciones.
6. **Individual:** `situacion_estudiante` + `calificaciones` + `trazabilidad` filtradas por ID y asignatura.
7. **Matrícula y alertas:** alertas y tasas del resumen.

## Comprobaciones

`tests/test_kpi_6_2.py` verifica poblaciones, porcentajes, escala de nota,
eventos sin matrícula, recuperatorios descartados, alertas, duplicación de claves y fechas inválidas.

**Pendiente antes de considerar 6.2 cerrado:** ejecutar los tests y los KPI con los CSV reales del último Colab, revisar los valores obtenidos, fijar política de sesiones estimadas (si se requiere) y decidir tratamiento de filtros temporales en los dashboards.
