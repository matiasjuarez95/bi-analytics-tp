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

La aplicación incluye una página **Administración de datos** accesible desde la navegación de Streamlit. Se puede abrir incluso cuando todavía no existen KPI calculados.

1. Guardá los Excel originales en `data/raw/`, respetando la estructura que espera el ETL.
2. Abrí **Administración de datos** y presioná **Actualizar datos**.
3. La aplicación ejecutará ETL 6.1 → validaciones → KPI 6.2 → validaciones.
4. Regresá a la página principal y consultá los siete dashboards, incluidos los filtros de fecha de corte y grupos de riesgo.

Los datos se leen localmente de `data/processed/`. La aplicación no descarga fuentes desde Drive ni recalcula los indicadores al abrir un gráfico.

### Alternativa por terminal

El orquestador ofrece un único comando para regenerar ETL y KPI:

```bash
python -m src.pipeline
```

También admite `--raw data/raw --processed data/processed`. Los comandos individuales del ETL y los KPI se conservan para desarrollo y depuración.

### Integridad y seguridad

- Las etapas procesan archivos en una carpeta temporal y solo publican las salidas al terminar correctamente. Si falla la ejecución, se mantienen los resultados anteriores.
- La fecha UTC y las filas por tabla de la última actualización exitosa se registran en `data/processed/ultima_actualizacion.json`.
- Un bloqueo local en `data/.pipeline.lock` evita ejecutar dos actualizaciones simultáneas. Tras una interrupción abrupta se debe verificar que no haya otra ejecución antes de quitarlo manualmente.
- **Administración está diseñada para uso local de confianza**. No exponerla a internet sin autenticación y autorización.
- No subir Excel ni CSV con información de alumnos al repositorio.
- Para cargar datos se necesitan los Excel de origen y permisos de escritura en `data/processed/`.

## Despliegue en Streamlit Community Cloud con datos reales

La aplicación puede iniciarse en Streamlit Cloud con los **Excel originales del TP**, almacenados en un ZIP privado de Google Drive. Si al iniciar no encuentra los CSV procesados en el servidor, descarga el ZIP con permisos de solo lectura, ejecuta el ETL 6.1, valida las salidas y calcula los KPI 6.2. No requiere una base de datos ni incorporar los Excel a GitHub.

### Configuración

1. Crear una cuenta de servicio en Google Cloud y habilitar **Google Drive API** en su proyecto. Generar una clave JSON de esa cuenta.
2. En Google Drive, compartir el archivo `Datos_LMS_Anonimizados.zip` (únicamente permiso de lectura) con el correo `client_email` de la cuenta de servicio. El ZIP debe conservar la estructura de asignaturas y matrícula requerida por el ETL.
3. En Streamlit Community Cloud, crear una aplicación desde el repositorio GitHub privado, rama `main`, archivo de entrada `dashboards/app_TFI.py`.
4. En **Advanced settings → Secrets**, añadir la configuración siguiente y reemplazar los valores de ejemplo por los de la cuenta de servicio; mantener la clave **exclusivamente en Secrets**, nunca en Git:

```toml
drive_zip_file_id = "1nQtOmzI0o8G3tXJ-CrzUPnyk5npweO7b"
admin_password = "ELEGIR_UNA_CLAVE_LARGA_Y_UNICA"

[gcp_service_account]
type = "service_account"
project_id = "TU_PROJECT_ID"
private_key_id = "TU_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
client_email = "CUENTA@PROYECTO.iam.gserviceaccount.com"
client_id = "TU_CLIENT_ID"
token_uri = "https://oauth2.googleapis.com/token"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/CUENTA"
```

Los campos deben copiarse fielmente del JSON de la cuenta de servicio. La aplicación utiliza el scope `drive.readonly`; no escribe ni modifica el Drive. El ID configurado apunta al ZIP real de la carpeta de trabajo.

La primera apertura de un servidor nuevo puede demorar porque ejecuta la carga inicial. Los resultados se guardan en `data/processed/` del servidor y se recalculan automáticamente cuando un servidor se inicia sin esos archivos. No se garantiza persistencia del disco de Streamlit Cloud entre reinicios.

La página **Administración de datos** permite volver a descargar y procesar las fuentes desde Drive únicamente si se ingresa la clave `admin_password`. La clave evita ejecuciones accidentales, pero no reemplaza la configuración de acceso privado a la app.

**Privacidad:** aunque el conjunto de archivos se denomine anonimizado, verificar la ausencia de datos personales identificables y limitar quién puede acceder a la app antes de compartir el enlace. No subir la clave JSON, archivos Excel ni CSV procesados a GitHub.

### Ejecución local

Sin Secrets, se conserva el flujo de trabajo local con archivos en `data/raw/` y el botón **Actualizar datos** de Administración. No se necesita Google Cloud para ejecutar el proyecto localmente.

## Vistas del dashboard

| Pestaña | Qué muestra |
|---|---|
| **General** | Resumen por asignatura, estados académicos a la fecha, actividad semanal y situación de actividad de cada matriculado a la fecha de corte (activo reciente, sin actividad reciente o sin actividad), con el listado de estudiantes para contactar. Incluye el promedio de notas en la tabla resumen. |
| **Participación** | Tiempo de uso, cobertura, estudiantes activos por día y evolución diaria de accesos. Permite filtrar por asignatura y rango de fechas, y consultar la actividad diaria de un estudiante. |
| **Trazabilidad** | Eventos por tipo de interacción y mapa de calor por día y hora. El gráfico de eventos usa escala logarítmica para facilitar la comparación entre categorías. |
| **Rendimiento** | Distribución de notas, cantidad de estudiantes por estado y promedio de notas por instrumento. |
| **Notas vs. Participación** | Grupos de riesgo (riesgo alto, con dificultades, autónomos y sin riesgo), gráfico de dispersión según la medida de participación elegida, coloreado por grupo de riesgo o por estado, listado de estudiantes en riesgo y correlaciones de Pearson por asignatura. |
| **Ficha individual** | Selección de asignatura y estudiante, estado tipo semáforo, nota, tiempo de uso, interacciones, eventos, notas por instrumento y trazabilidad diaria y por tipo. |
| **Matrícula y alertas** | Comparación entre matriculados y activos, y alertas por asignatura para estudiantes matriculados sin participación y estudiantes no matriculados con actividad. |

## Tablas utilizadas

La aplicación lee las siguientes tablas KPI desde `data/processed/kpi/`:

- `kpi_resumen_asignatura.csv`
- `kpi_estados_a_la_fecha.csv`
- `kpi_alertas_matricula.csv`
- `kpi_histograma_notas.csv`
- `kpi_relacion_estudiante.csv`
- `kpi_actividad_diaria.csv`
- `kpi_notas_instrumento.csv`

También utiliza:

- `data/processed/trazabilidad.csv`, para todo lo que depende de la fecha de corte: actividad a la fecha, actividad semanal, eventos por tipo, mapa de calor, evolución de accesos y actividad individual. Coincide con `kpi_actividad_semanal`, `kpi_interacciones_tipo` y `kpi_mapa_calor` cuando la fecha de corte es el último día de datos.
- `data/processed/calificaciones.csv`, para consultar las notas por instrumento en la ficha individual.

## Filtros

- **Asignatura:** una, dos o las tres materias.
- **Fecha de corte:** muestra la actividad de los alumnos hasta ese día inclusive (tarjetas de actividad, actividad semanal y diaria, cobertura, situación de actividad, eventos por tipo, mapa de calor, ficha individual y matriculados vs. activos). Quedan acumulados al 24/10, y así se indica en cada vista: el tiempo de uso (el reporte de participación no trae fechas), las notas y estados (las calificaciones no tienen fecha) y las alertas de matrícula.
- **Activo reciente:** ventana de 7, 14 o 30 días antes de la fecha de corte para considerar que un alumno participa actualmente.

## Grupos de riesgo

Se calculan sobre los alumnos con notas, combinando dos criterios: participación alta o baja según la mediana de interacciones de cada asignatura, y nota mayor o menor al 60% de la escala.

| Grupo | Participación | Nota | Acción sugerida |
|---|---|---|---|
| Riesgo alto | Baja | < 60% | Contactar para evitar el abandono |
| Con dificultades | Alta | < 60% | Ofrecer apoyo académico |
| Autónomos | Baja | ≥ 60% | Seguimiento habitual |
| Sin riesgo | Alta | ≥ 60% | Seguimiento habitual |

## Criterios de lectura

- La población principal corresponde a estudiantes con matrícula vigente. Las alertas también consideran actividad de estudiantes no matriculados.
- Los estados académicos se muestran **a la fecha** y no representan calificaciones finales.
- Las notas se expresan como porcentaje de la escala para facilitar la comparación entre asignaturas.
- Las correlaciones muestran asociación entre variables; no demuestran causalidad.
- Los archivos con datos de estudiantes deben mantenerse fuera del repositorio público.