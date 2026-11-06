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
- Opciones: `--recuperatorio {docente,mayor_nota,reemplaza,aparte}` (por defecto `docente`) y
  `--cursada-cerrada` (habilita los estados definitivos Regular/Libre; ver "Decisiones").
- Las salidas van a `data/processed/` (CSV, y Parquet si está instalado `pyarrow`). No se versionan.

## Principios

1. **No se oculta nada.** Cada filtro registra las cantidades antes y después en `informe_calidad_datos`,
   y las filas descartadas quedan en `descartados.csv`.
2. **Lo real se separa de lo estimado.** Una proyección o un promedio con faltantes se identifica como
   estimación y nunca define un estado *definitivo*.
3. **Si falta información para un estado definitivo, queda "Pendiente"**, no se asigna una promoción basada en un supuesto.

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
| `informe_calidad_datos` | 91 | Cada problema, filas antes/después, cantidad afectada y decisión |
| `validaciones` | 10 | Chequeos automáticos del modelo (todos OK) |

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

## Cálculo de la nota (criterios confirmados por el docente)

- **Un examen que existe y el alumno no rindió vale 0.** Existe = lo rindió algún otro alumno, es decir, está
  presente en los datos. El cálculo usa los instrumentos presentes en los datos.
- **Álgebra:** los archivos faltantes son a propósito (solo hay 3 de los 8 instrumentos, 45 de 120 puntos).
  Se trabaja con los instrumentos disponibles, proyectando a la escala de 120 puntos. Como alternativa
  se calcula también la normalización de cada instrumento a 10 (p. ej. 25/25 × 10).
- **Recuperatorio (Probabilidad, "Evaluación Semanal Nº1"):** si el alumno no tenía nota original, queda el
  recuperatorio; si la original estaba aprobada, se conserva la original (no debería recuperar); si estaba
  desaprobada, queda la mejor de las dos. Las filas que no se usan **no se borran**: quedan en `calificaciones`
  con `usa_en_nota_final = False`.
  En los datos: 21 alumnos lo rindieron; en 8 no había nota original (queda el recuperatorio), en 5 la
  original estaba aprobada (se conserva) y en 8 estaba desaprobada, de los cuales 6 mejoraron. En total,
  14 recuperatorios pasan a ser la nota de la evaluación y 7 no se usan.
- **Estado definitivo vs. a la fecha:** la cursada no está confirmada como cerrada, así que no se asignan
  `Regular`/`Libre` definitivos. El semáforo usa el estado "a la fecha" (`estado_provisorio`).

### Columnas de `notas_finales` / `situacion_estudiante`

**Álgebra** (acumulativo, 120 puntos; promociona ≥ 85, regular ≥ 60):

| Columna | Qué es |
|---|---|
| `puntos_acumulados` | **Real**: suma de puntos obtenidos |
| `puntos_maximos_observados` | Puntos posibles de los instrumentos presentes en los datos (hoy 45 de 120) |
| `proyeccion_120_observados` | **Estimación**: puntos acumulados / 45 × 120 (lo no rendido cuenta 0). Es la `nota_a_la_fecha` |
| `proyeccion_120_rendidos` | Estimación solo sobre lo que el alumno rindió (informativa) |
| `promedio_normalizado_10` | Promedio de los instrumentos llevados a 10 (lo no rendido cuenta 0) |
| `completitud_datos` / `completitud_alumno` | Instrumentos en los datos / esperados (3/8 = 0,375); rendidos / en los datos |

**Probabilidad y Algoritmos** (promedio de instrumentos presentes en los datos):

| Columna | Qué es |
|---|---|
| `promedio_con_faltantes` | Lo no rendido cuenta 0. Es la `nota_a_la_fecha` |
| `promedio_observados` | Promedio solo de lo rendido (informativo) |

**Comunes:** `nota_a_la_fecha` y `escala_nota_a_la_fecha` (120 en Álgebra, 100 en las demás),
`rendimiento_observado_pct`, `estado_provisorio` (según `nota_a_la_fecha`), `estado_definitivo`,
`semaforo` (Verde = Promociona, Amarillo = Regular, Rojo = Libre, "Sin notas") y `semaforo_definitivo`.

`estado_definitivo`: solo es `Promociona` en Álgebra si ya hay ≥ 85 puntos acumulados **reales** (no bajan).
El resto queda `Pendiente` hasta ejecutar con `--cursada-cerrada`.

**Sin notas:** los alumnos sin ninguna nota quedan como "Sin notas" (421 casos; 21 en Álgebra, 58 en Algoritmos y
22 en Probabilidad entre los matriculados), nunca como Libre.

### Distribución del estado a la fecha (solo matriculados)

| Asignatura | Promociona | Regular | Libre | Sin notas |
|---|---:|---:|---:|---:|
| Álgebra | 100 | 18 | 24 | 21 |
| Algoritmos y Estructuras de Datos | 18 | 35 | 54 | 58 |
| Probabilidad y Estadística | 19 | 59 | 64 | 22 |

## Decisiones

| # | Tema | Estado |
|---|---|---|
| 1 | Álgebra: faltan instrumentos | **Confirmado**: es a propósito; se trabaja con lo disponible (proyección a 120 y/o normalización a 10) |
| 2 | Lo no rendido en Probabilidad y Algoritmos | **Confirmado**: si el examen existe y el alumno no lo rindió, vale 0 |
| 3 | Recuperatorio de Probabilidad | **Confirmado**: regla del docente (ver arriba) |
| 4 | No matriculados con actividad (332 en total) | **Confirmado**: se conservan y se marcan en `situacion_matricula`; los KPIs de rendimiento usan `matriculado = True` |
| 5 | Definición de "activo" (KPI activos vs. inactivos) | **Confirmado**: al menos una interacción hasta la fecha de corte |
| 6 | ¿Está cerrada la cursada? | **Pendiente**: hasta confirmarlo (`CURSADA_CERRADA = False`) los estados Regular/Libre no son definitivos |
| 7 | Alumno matriculado sin ninguna nota | **Pendiente**: se informa como "Sin notas" (no como Libre) para no confundir "no rindió nada" con un resultado de evaluación; por la regla de los 0 podría corresponder Libre |

## Validaciones y pruebas

El programa se detiene si falla alguna de estas validaciones (todas OK en la corrida): `situacion_estudiante`
única por `id_estudiante` + `asignatura`; los merges no multiplican filas (957 = 957); notas dentro de
rango; "Sin notas" no termina como Libre; con la cursada abierta no hay Regular/Libre definitivos ni
Promociona sin puntos reales suficientes; el personal excluido no incluye alumnos matriculados.

`tests/test_etl_6_1.py` (43 pruebas) cubre: baja posterior a una inscripción y reinscripción; umbrales de las
tres materias; Álgebra (estimación vs. real, faltantes en 0, normalización a 10); alumno sin notas; lo no
rendido como 0; recuperatorio (regla del docente y los otros modos); duplicados de trazabilidad y de notas;
separación de personal; matriculado sin actividad y actividad sin matrícula; detección de archivos
(faltantes, duplicados, tildes).
