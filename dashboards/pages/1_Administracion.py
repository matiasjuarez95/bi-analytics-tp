"""Administración local del pipeline de datos del TFI BI & Analytics."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit ejecuta páginas desde dashboards/pages, no necesariamente desde la raíz.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import actualizar, leer_estado

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

st.set_page_config(page_title="Administración · BI & Analytics", layout="wide")
st.title("Administración de datos")
st.caption("Actualizá la base analítica de la aplicación sin ejecutar el ETL y los KPI a mano.")

archivos = sorted(
    (p for p in RAW.rglob("*") if p.suffix.lower() in {".xlsx", ".xls", ".xlsm"}),
) if RAW.is_dir() else []
estado = leer_estado(PROCESSED)

c1, c2, c3 = st.columns(3)
c1.metric("Fuentes Excel encontradas", len(archivos))
c2.metric("Última carga", estado.get("fecha_utc", "Sin ejecutar") if estado else "Sin ejecutar")
c3.metric("Estado", "Correcto" if estado else "Sin publicación registrada")

with st.expander("Ubicaciones locales", expanded=not RAW.exists()):
    st.code(str(RAW), language=None)
    st.code(str(PROCESSED), language=None)
    if not RAW.exists():
        st.info("Creá data/raw y colocá allí los Excel originales con la estructura del ETL.")

if estado:
    st.subheader("Resumen de la última actualización")
    st.write("Fecha expresada en UTC. Las cifras representan filas por tabla, no alumnos únicos.")
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("**Salidas ETL**")
        st.dataframe(pd.DataFrame(
            [{"Tabla": k, "Filas": v} for k, v in estado.get("tablas_etl", {}).items()]
        ), hide_index=True, use_container_width=True)
    with e2:
        st.markdown("**Tablas KPI**")
        st.dataframe(pd.DataFrame(
            [{"Tabla": k, "Filas": v} for k, v in estado.get("tablas_kpi", {}).items()]
        ), hide_index=True, use_container_width=True)
elif (PROCESSED / "kpi").is_dir():
    st.info(
        "Se encontraron CSV procesados anteriormente, pero no existe un registro "
        "de publicación. Podés seguir navegándolos o ejecutar una actualización nueva."
    )

st.divider()
st.subheader("Actualizar datos")
st.write(
    "El botón ejecuta en orden: **ETL 6.1 → validaciones → KPI 6.2 → validaciones**. "
    "Solo publica los resultados nuevos cuando todas las etapas finalizan bien. "
    "Si ocurre un error, los CSV anteriores permanecen disponibles."
)
st.caption("La actualización puede tardar según el tamaño de los Excel. No cierres el servidor durante el proceso.")
puede_actualizar = RAW.is_dir() and bool(archivos)
if not puede_actualizar:
    st.error("No hay archivos Excel disponibles en data/raw para iniciar una actualización.")

if st.button("Actualizar datos", type="primary", disabled=not puede_actualizar):
    try:
        with st.spinner("Procesando fuentes y calculando indicadores..."):
            resultado = actualizar(RAW, PROCESSED)
        st.cache_data.clear()
        st.session_state["pipeline_ultimo_resultado"] = resultado
        st.rerun()
    except Exception as exc:
        st.error(f"No se pudo actualizar: {type(exc).__name__}: {exc}")
        st.info("No se publicaron los resultados de la ejecución fallida. Revisá los Excel o el archivo de bloqueo.")

if "pipeline_ultimo_resultado" in st.session_state:
    st.success("Actualización finalizada: ETL, validaciones y KPI publicados correctamente.")
    st.session_state.pop("pipeline_ultimo_resultado")

st.page_link("app_TFI.py", label="Ir a los dashboards", icon="📊")
