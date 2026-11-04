# Procesamiento de datos (Paso 6.1)

Script que integra, limpia y unifica las 4 fuentes del LMS (trazabilidad, participación,
calificaciones y matriculados) de las 3 asignaturas, y deja un modelo listo para los KPIs
(6.2) y los dashboards.

## Cómo correrlo

```bash
pip install pandas openpyxl
python procesamiento/procesar_datos.py RUTA/Datos_LMS_Anonimizados datos_procesados
```

- `RUTA/Datos_LMS_Anonimizados` es la carpeta **ya descomprimida** que contiene las carpetas
  de las materias y `Matriculados`.
- Tarda unos segundos. Los resultados quedan en `datos_procesados/`.
- Los datos originales y `datos_procesados/` **no se suben al repositorio** (están en `.gitignore`).
  Cada integrante los regenera localmente.

## Tablas que genera

| Archivo | Contenido |
|---|---|
| `matricula.csv` | Una fila por alumno y materia (bajas y re-inscripciones resueltas) |
| `participacion.csv` | Resumen de participación por alumno y materia (solo alumnos) |
| `trazabilidad.csv` | Eventos del LMS sin duplicados, solo alumnos, con `tipo_interaccion`, `hora`, `dia_semana` |
| `calificaciones.csv` | Notas en formato largo (alumno, materia, instrumento, puntos, máximo, nota_100) |
| `notas_finales.csv` | Nota final y condición (Libre/Regular/Promociona) según la regla de cada materia |
| `situacion_estudiante.csv` | Tabla central: una fila por alumno y materia con todo lo anterior + `situacion_matricula` y `semaforo` |
| `personal_excluido.csv` | Docentes, tutores, coordinadores e invitados (IDs `DOC_`/`STAFF_`) apartados de los KPIs |
| `informe_calidad_datos.csv` | Cada problema detectado, cuántos registros afectó y qué decisión se tomó |

## Decisiones pendientes de confirmar con el docente

Mientras no haya respuesta, el script usa el criterio asumido. Todas se cambian fácil.

| # | Duda | Criterio asumido hoy | Dónde se cambia |
|---|---|---|---|
| 1 | Álgebra tiene solo 3 archivos de notas (45 de 120 pts posibles) | Se trabaja con esos y se proyecta lo rendido a 120 (`nota_final_rendidos`) | Columnas `*_rendidos` de `notas_finales` |
| 2 | Lo no rendido, ¿cuenta como 0? | Se promedia solo lo rendido; la versión con 0 queda como `*_estricta` | Usar `nota_final_rendidos` o `nota_final_estricta` |
| 3 | Recuperatorio de Probabilidad | Reemplaza la nota original | Constante `RECUPERATORIO_REEMPLAZA` en el script |
| 4 | Alumnos activos que no están en la matrícula (~110 por materia) | Se conservan y se marcan; los KPIs de rendimiento se calculan solo con `matriculado = True` | Filtro en los dashboards |

## Notas para el resto del equipo

- Para KPIs y dashboards de rendimiento, filtrar por `matriculado = True` en `situacion_estudiante`.
  El dashboard de Matrícula y Alertas usa todos los alumnos.
- "Activo" = al menos una interacción en el período (o hasta la fecha de corte seleccionada).
- Semáforo: Verde = Promociona, Amarillo = Regular, Rojo = Libre, "Sin notas" si no rindió nada.
