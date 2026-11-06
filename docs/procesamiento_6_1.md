# Paso 6.1 – Procesamiento de datos (ETL del LMS)

Código: `src/etl/procesar_datos.py` · Pruebas: `tests/test_etl_6_1.py`

El procesamiento integra las 4 fuentes del LMS (trazabilidad, participación, calificaciones y
matriculados) de las 3 asignaturas, estandariza los IDs, trata duplicados, nulos e inconsistencias, y
deja un modelo listo para los KPIs (6.2) y los dashboards.

## Cómo ejecutarlo

Desde la raíz del repositorio:

```bash
pip install -r requirements.txt
python -m src.etl.procesar_datos data/raw data/processed
python -m pytest tests/ -v
```

- `data/raw/` contiene los 26 Excel originales (`.xlsx`, sin convertir) en las subcarpetas
  `algebra/`, `probabilidad/`, `algoritmos/` y `matriculados/` (ver `data/raw/README.md`).
- Los nombres se detectan sin importar tildes ni mayúsculas. Si falta un archivo, o hay más de un
  candidato para un reporte único, el programa **se detiene con un mensaje claro** (no elige uno al azar).
- Opciones: `--recuperatorio {reemplaza,mayor_nota,aparte}` y `--cursada-cerrada` (ver "Supuestos").
- Las salidas van a `data/processed/` (CSV, y Parquet si está instalado `pyarrow`). No se versionan.

## Principios

1. **No se oculta nada.** Cada filtro registra las cantidades antes y después en `informe_calidad_datos`,
   y las filas descartadas quedan en `descartados.csv`.
2. **Lo real se separa de lo estimado.** Una proyección o un promedio con faltantes nunca define un estado definitivo.
3. **Si falta información, el estado queda "Pendiente"**, no se asigna una promoción basada en un supuesto.

## Tablas generadas (resultados de la corrida con los 26 Excel)

| Tabla | Filas | Contenido |
|---|---:|---|
| `matricula` | 499 | Una fila por alumno y materia con el **estado vigente** (último movimiento) |
| `matricula_movimientos` | 513 | Auditoría: todos los movimientos (altas/bajas), con `es_vigente` y `caso_ambiguo` |
| `participacion` | 957 | Resumen de participación por alumno y materia (solo alumnos) |
| `trazabilidad` | 150.104 | Eventos de alumnos, con `duplicado_potencial`, `tipo_interaccion`, `hora`, `dia_semana` |
| `calificaciones` | 1.793 | Notas en formato largo; `usa_en_nota_final` indica qué fila vale tras el recuperatorio |
| `notas_finales` | 957 | Valores reales, estimaciones y estados (ver abajo) |
| `situacion_estudiante` | 957 | **Tabla central**: una fila por alumno y materia (única por `id_estudiante` + `asignatura`) |
| `personal_excluido` | 9.729 | Docentes, tutores, coordinadores e invitados (`DOC_`/`STAFF_`), con `motivo_exclusion` |
| `descartados` | 3 | Filas descartadas (hoy, los pies "Cantidad de filas" de la matrícula) |
| `informe_calidad_datos` | 92 | Cada problema, filas antes/después, cantidad afectada y decisión |
| `validaciones` | 11 | Chequeos automáticos del modelo (todos OK) |

Universo: 957 filas = 319 alumnos × 3 materias. Matriculados vigentes: 163 (Álgebra), 165 (Algoritmos) y 164 (Probabilidad).

## Reglas de limpieza

- **IDs:** se normalizan a mayúsculas y sin espacios (`ALU_####`). La clave es el ID, no el nombre
  (hay 9 nombres repetidos con IDs distintos por materia; se tratan como personas distintas).
- **Alumnos vs. personal:** es alumno quien tiene perfil `Alumnos` **e** ID `ALU_####`. Si una de las dos
  condiciones falla sin la otra, se marca como inconsistencia y se revisa (en estos datos hay 0). No
  se excluyó ningún alumno matriculado.
- **Matrícula:** el estado vigente es el del **movimiento más reciente**. Desempate: 1) fecha de inscripción,
  2) nro. de transacción, 3) si persiste, prevalece `Baja`. Los casos en que fecha y nro. de transacción no
  coinciden se marcan `caso_ambiguo` (hoy: 0). Hay 11 casos de IDs con más de un movimiento (por materia): 7
  son una baja seguida de una nueva inscripción aceptada (5 en Algoritmos, 2 en Probabilidad) y 4 son varias
  bajas seguidas (ALU_1193 en las 3 materias y ALU_1084 en Algoritmos), que quedan en `Baja`. No se supone
  que todo duplicado sea una reinscripción.
- **Trazabilidad:** el Excel no trae ID de evento, así que dos eventos reales pueden ser idénticos. **No se
  eliminan**: los repetidos se marcan `duplicado_potencial` (646 entre alumnos: 190 Álgebra, 171 Algoritmos,
  285 Probabilidad). Cada KPI decide si los excluye. Hay 6 y 13 acciones nulas (Álgebra y Probabilidad),
  que pasan a "Sin dato" sin descartar el evento. Las acciones sin categoría quedan como `Otros`
  (el informe lista las más frecuentes).
- **Participación:** los usuarios que nunca ingresaron conservan los nulos y se marcan `nunca_ingreso`
  (no se imputan).
- **Calificaciones:** se verificó que no hay alumnos con dos notas en un mismo instrumento. Si apareciera
  alguno, el programa lo registra, deja la fila no usada en `descartados.csv` y aplica el criterio
  `mayor_nota` (supuesto, porque no se sabe si son intentos o correcciones).

## Nota real vs. estimación

**Álgebra** (acumulativo, 120 puntos; promociona ≥ 85, regular ≥ 60):

| Columna | Qué es |
|---|---|
| `puntos_acumulados` | **Real**: suma de puntos obtenidos |
| `puntos_maximos_observados` | Puntos posibles de los instrumentos que hay en los datos (hoy 45 de 120) |
| `completitud_datos` | Instrumentos en los datos / esperados por la consigna (hoy 3/8 = 0,375) |
| `completitud_alumno` | Instrumentos que rindió el alumno / instrumentos en los datos |
| `proyeccion_120_rendidos`, `proyeccion_120_observados` | **Estimaciones** (no son nota final) |
| `estado_provisorio`, `estado_definitivo` | Se calculan **sin usar las proyecciones** |

`estado_definitivo` es `Promociona` solo si el alumno ya acumuló ≥ 85 (los puntos no bajan). `Regular` o
`Libre` solo se asignan si los datos están completos **y** la cursada está cerrada. Hoy no se cumple
ninguna de las dos condiciones, por lo que los 196 alumnos con notas quedan en **Pendiente** (semáforo gris).

**Probabilidad y Algoritmos** (promedio; el total de instrumentos esperados no figura en la consigna):

| Columna | Qué es |
|---|---|
| `promedio_observados` | Promedio de lo efectivamente rendido |
| `promedio_con_faltantes` | Estimación: lo no rendido cuenta 0, dividido por los instrumentos **presentes en los datos** |
| `denominador_confirmado` | `False` mientras no se confirme el total oficial |
| `estado_provisorio` | Según `promedio_observados` |
| `estado_definitivo` | `Pendiente` hasta que la cursada esté cerrada y el total esté confirmado |

**Sin notas:** los alumnos sin ninguna nota quedan como "Sin notas" (421 casos), nunca como Libre.

## Supuestos pendientes de confirmar con el docente

| # | Tema | Supuesto actual | Cómo se cambia |
|---|---|---|---|
| 1 | Álgebra: solo hay 3 de los 8 instrumentos (45 de 120 pts) | Se trabaja con lo disponible; estados `Pendiente` | Al recibir los archivos faltantes, agregarlos a `data/raw/algebra/` |
| 2 | Lo no rendido en Probabilidad y Algoritmos | Se informan ambos promedios; el estado provisorio usa lo rendido | `denominador_confirmado` / `REGLAS[...]["instrumentos_esperados"]` |
| 3 | Recuperatorio de Probabilidad | Reemplaza a la original. De los 21 alumnos que lo rindieron: 7 mejoran, 6 empeoran y 8 no tenían nota original | `--recuperatorio` o `RECUPERATORIO_MODO` |
| 4 | No matriculados con actividad (332 en total) | Se conservan y se marcan en `situacion_matricula`; los KPIs de rendimiento se calculan con `matriculado = True` | Filtro en 6.2 |
| 5 | ¿Está cerrada la cursada? | No (`CURSADA_CERRADA = False`) | `--cursada-cerrada` |

## Validaciones y pruebas

El programa se detiene si falla alguna de estas validaciones (todas OK en la corrida): `situacion_estudiante`
única por `id_estudiante` + `asignatura`; los merges no multiplican filas (957 = 957); notas dentro de
rango; "Sin notas" no termina como Libre; Álgebra con datos incompletos no tiene Regular/Libre definitivo;
el personal excluido no incluye alumnos matriculados.

`tests/test_etl_6_1.py` (39 pruebas) cubre: baja posterior a una inscripción y reinscripción; umbrales de las
tres materias; Álgebra sin proyección como nota definitiva; alumno sin notas; recuperatorio en sus tres
modos; duplicados de trazabilidad y de notas; separación de personal; matriculado sin actividad y actividad
sin matrícula; detección de archivos (faltantes, duplicados, tildes).
