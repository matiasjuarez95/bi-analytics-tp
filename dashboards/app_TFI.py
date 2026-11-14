"""
Seguimiento académico LMS - Dashboard (TFI Business Intelligence & Analytics)
Lee SOLO las tablas que generan el ETL (6.1) y los KPI (6.2); no calcula nada nuevo.

Ejecutar desde la raíz del repo:
    python -m streamlit run dashboards/app_TFI.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# -------------------------------------------------------------
# 1. CONFIGURACIÓN
# -------------------------------------------------------------
def encontrar_raiz() -> Path:
    """Encuentra la raíz aunque el script se ejecute desde Descargas."""
    candidatos = [Path(__file__).resolve().parent, *Path(__file__).resolve().parents,
                  Path.cwd(), *Path.cwd().parents]
    for candidato in candidatos:
        if (candidato / "data" / "processed").is_dir():
            return candidato
    raise FileNotFoundError("No encuentro data/processed. Ejecutá Streamlit desde la raíz del proyecto.")


RAIZ = encontrar_raiz()
PROC = RAIZ / "data" / "processed"
KPI = PROC / "kpi"
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
# Paleta unificada: azul petróleo, teal y acentos cálidos
PALETA_GRAFICOS = ["#4F7892", "#6FA6A1", "#D8A15D", "#CB746A", "#8C80A8", "#8B9A70"]
COLOR_ESTADO = {"Promociona": "#4E8A6A", "Regular": "#D39B35",
                "Libre": "#C86460", "Sin notas": "#98A3AF"}
COLOR_CONTINUA = ["#EEF4F7", "#9DBBC8", "#4F7892"]
COLOR_ACTIVIDAD = {"Activos": "#4E8A6A", "Inactivos": "#C86460"}
COLOR_MATRICULA = {"Matriculados": "#4F7892", "Activos": "#6FA6A1"}
COLOR_TIPOS = {"Acceso/navegación": "#4F7892", "Calificaciones": "#6FA6A1",
               "Comunicación/foros": "#D8A15D", "Evaluaciones": "#CB746A",
               "Lectura de materiales": "#8C80A8", "Otros": "#8B9A70"}
COLOR_ALERTA = {"Matriculado sin participación": "#6FA6A1",
                "No matriculado con actividad": "#CB746A"}
px.defaults.color_discrete_sequence = PALETA_GRAFICOS
SEMAFORO = {"Promociona": "🟢 Verde: promociona", "Regular": "🟡 Amarillo: regular",
            "Libre": "🔴 Rojo: libre", "Sin notas": "⚪ Sin notas"}

st.set_page_config(page_title="Seguimiento académico LMS", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-title { font-size: 2.0rem; font-weight: 700; color: #315A70; margin-bottom: 2px; }
    .sub-title { font-size: 0.95rem; color: #64748B; margin-bottom: 18px; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; color: #315A70; }
    div[data-testid="metric-container"] {
        background-color: #F8FAFC; border: 1px solid #DCE5EC;
        padding: 12px 18px; border-radius: 8px; box-shadow: 0 1px 3px rgba(49,90,112,0.08);
    }
    .alert-card { padding: 0.75rem 1rem; margin: 0.45rem 0; border-radius: 0.55rem;
                  border: 1px solid rgba(111,166,161,0.22); color: var(--text-color); }
    .alert-card--participacion { background: rgba(111,166,161,0.14); border-left: 4px solid #6FA6A1; }
    .alert-card--matricula { background: rgba(203,116,106,0.14); border-left: 4px solid #CB746A; }
</style>
""", unsafe_allow_html=True)


# -------------------------------------------------------------
# 2. CARGA DE DATOS (con caché)
# -------------------------------------------------------------
@st.cache_data(show_spinner="Cargando tabla...")
def cargar(carpeta: str, nombre: str) -> pd.DataFrame:
    archivo = Path(carpeta) / f"{nombre}.csv"
    if not archivo.is_file():
        raise FileNotFoundError(archivo)
    return pd.read_csv(archivo)


def tabla(nombre: str, carpeta: Path = KPI) -> pd.DataFrame:
    try:
        return cargar(str(carpeta), nombre)
    except FileNotFoundError as e:
        st.error(f"Falta el archivo {e}. Ejecutá primero:\n\n"
                 "`python -m src.etl.procesar_datos data/raw data/processed`\n\n"
                 "`python -m src.kpi data/processed data/processed/kpi`")
        st.stop()


@st.cache_data(show_spinner="Cargando trazabilidad detallada...")
def cargar_trazabilidad(archivo: str) -> pd.DataFrame:
    """Carga solo las columnas usadas por las vistas de actividad individual."""
    columnas = ["fecha", "id_estudiante", "asignatura", "tipo_interaccion"]
    df = pd.read_csv(archivo, usecols=columnas, low_memory=False)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df.dropna(subset=["fecha", "id_estudiante", "asignatura"])


resumen = tabla("kpi_resumen_asignatura")
estados = tabla("kpi_estados_a_la_fecha")
alertas = tabla("kpi_alertas_matricula")
hist = tabla("kpi_histograma_notas")
relacion = tabla("kpi_relacion_estudiante")
tipos = tabla("kpi_interacciones_tipo")
semanal = tabla("kpi_actividad_semanal")
diaria = tabla("kpi_actividad_diaria")
mapa = tabla("kpi_mapa_calor")
instrumentos = tabla("kpi_notas_instrumento")
trazabilidad = cargar_trazabilidad(str(PROC / "trazabilidad.csv"))


# -------------------------------------------------------------
# 3. SIDEBAR: FILTROS
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### Filtros")
    materias_all = sorted(resumen["asignatura"].unique())
    materias = st.multiselect("Asignatura:", materias_all, default=materias_all)
    st.divider()
    st.caption("Los estados son **a la fecha** (cursada abierta): "
               "no son calificaciones finales.")
    st.caption("Población: alumnos con matrícula vigente (salvo en alertas).")

if not materias:
    st.warning("Elegí al menos una asignatura.")
    st.stop()


def filtrar(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["asignatura"].isin(materias)]


res, est, ale, his = filtrar(resumen), filtrar(estados), filtrar(alertas), filtrar(hist)


# -------------------------------------------------------------
# 4. ENCABEZADO Y TARJETAS
# -------------------------------------------------------------
st.markdown('<p class="main-title">Seguimiento académico LMS</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Participación, trazabilidad y rendimiento de estudiantes '
            'por asignatura.</p>', unsafe_allow_html=True)

matric = int(res["matriculados"].sum())
activos = int(res["activos"].sum())
nota_media = (res["promedio_nota_pct_solo_con_notas"] * res["con_notas"]).sum() / max(res["con_notas"].sum(), 1)
sin_part = int(ale.loc[ale["alerta"] == "Matriculado sin participación", "cantidad"].sum())
no_mat = int(ale.loc[ale["alerta"] == "No matriculado con actividad", "cantidad"].sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Matriculados", f"{matric:,}".replace(",", "."))
c2.metric("Activos", f"{activos / matric * 100:.1f}%" if matric else "-", f"{activos} de {matric}")
c3.metric("Nota media (%)", f"{nota_media:.1f}", "solo alumnos con notas")
c4.metric("Alertas de matrícula", f"{sin_part + no_mat}",
          f"{sin_part} sin participar · {no_mat} no matric.", delta_color="off")
st.write("")

# -------------------------------------------------------------
# 5. PESTAÑAS
# -------------------------------------------------------------
t_gen, t_par, t_tra, t_ren, t_rel, t_ind, t_mat = st.tabs([
    "General", "Participación", "Trazabilidad", "Rendimiento",
    "Notas vs. Participación", "Ficha individual", "Matrícula y alertas"])

# ---- General
with t_gen:
    st.subheader("Resumen por asignatura")
    g1, g2 = st.columns(2)
    with g1:
        f = px.bar(est, x="asignatura", y="porcentaje_sobre_matriculados",
                   color="estado_a_la_fecha", color_discrete_map=COLOR_ESTADO,
                   barmode="stack", title="Estado a la fecha (% de matriculados)",
                   labels={"porcentaje_sobre_matriculados": "%", "estado_a_la_fecha": "Estado"})
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
    with g2:
        a = filtrar(semanal)
        f = px.line(a, x="semana_inicio", y="eventos", color="asignatura",
                    title="Actividad semanal (eventos del LMS)")
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
    st.subheader("Estudiantes activos e inactivos")
    act = res.melt(id_vars="asignatura", value_vars=["activos", "inactivos"],
                   var_name="situacion", value_name="estudiantes")
    act["situacion"] = act["situacion"].map({"activos": "Activos", "inactivos": "Inactivos"})
    f = px.bar(act, x="asignatura", y="estudiantes", color="situacion", barmode="group",
               color_discrete_map=COLOR_ACTIVIDAD,
               title="Activos vs. inactivos por asignatura")
    f.update_layout(template="plotly_white")
    st.plotly_chart(f, use_container_width=True)
    tabla_general = res[["asignatura", "matriculados", "activos", "activos_pct", "inactivos", "inactivos_pct",
                         "promedio_nota_pct_solo_con_notas", "con_notas"]].rename(columns={
        "asignatura": "Asignatura", "matriculados": "Matriculados", "activos": "Activos",
        "activos_pct": "Activos (%)", "inactivos": "Inactivos", "inactivos_pct": "Inactivos (%)",
        "promedio_nota_pct_solo_con_notas": "Nota media (%)", "con_notas": "Alumnos con notas"})
    st.dataframe(tabla_general,
                 use_container_width=True, hide_index=True)

# ---- Participación
with t_par:
    st.subheader("Participación")
    p1, p2 = st.columns(2)
    with p1:
        f = px.bar(res, x="asignatura", y="tiempo_uso_promedio_min_por_matriculado",
                   title="Tiempo de uso promedio por matriculado (min)")
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
    with p2:
        f = px.bar(res, x="asignatura", y="cobertura_participacion_pct",
                   title="Cobertura de participación (% de matriculados activos)")
        f.update_layout(template="plotly_white", yaxis_range=[0, 100])
        st.plotly_chart(f, use_container_width=True)
    d = filtrar(diaria).copy()
    d["dia"] = pd.to_datetime(d["dia"])
    rango = st.slider("Rango de fechas:", d["dia"].min().date(), d["dia"].max().date(),
                      (d["dia"].min().date(), d["dia"].max().date()))
    d = d[(d["dia"].dt.date >= rango[0]) & (d["dia"].dt.date <= rango[1])]
    f = px.line(d, x="dia", y="estudiantes_activos", color="asignatura",
                title="Estudiantes activos por día")
    f.update_layout(template="plotly_white")
    st.plotly_chart(f, use_container_width=True)
    st.subheader("Evolución de accesos")
    tr_rango = trazabilidad[(trazabilidad["asignatura"].isin(materias)) &
                            (trazabilidad["fecha"].dt.date >= rango[0]) &
                            (trazabilidad["fecha"].dt.date <= rango[1]) &
                            (trazabilidad["tipo_interaccion"] == "Acceso/navegación")]
    accesos = tr_rango.assign(dia=tr_rango["fecha"].dt.floor("D")).groupby(
        ["dia", "asignatura"], as_index=False).size().rename(columns={"size": "accesos"})
    f = px.line(accesos, x="dia", y="accesos", color="asignatura", markers=True,
                title="Accesos/navegación por día")
    f.update_layout(template="plotly_white")
    st.plotly_chart(f, use_container_width=True)
    st.subheader("Actividad por estudiante")
    asig_det = st.selectbox("Asignatura para consultar:", materias, key="participacion_asig")
    ids_det = sorted(relacion.loc[relacion["asignatura"] == asig_det, "id_estudiante"].dropna().unique())
    if ids_det:
        alumno_det = st.selectbox("Estudiante:", ids_det, key="participacion_alumno")
        detalle = tr_rango[(tr_rango["asignatura"] == asig_det) &
                           (tr_rango["id_estudiante"] == alumno_det)]
        serie = detalle.assign(dia=detalle["fecha"].dt.floor("D")).groupby(
            "dia", as_index=False).size().rename(columns={"size": "eventos"})
        f = px.bar(serie, x="dia", y="eventos", title=f"Eventos por día · {alumno_det}")
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
    else:
        st.info("No hay estudiantes disponibles para esta asignatura.")

# ---- Trazabilidad
with t_tra:
    st.subheader("Trazabilidad")
    tp = filtrar(tipos)
    f = px.bar(tp, x="eventos", y="asignatura", color="tipo_interaccion",
               color_discrete_map=COLOR_TIPOS, barmode="group", orientation="h",
               log_x=True, height=430,
               labels={"eventos": "Eventos (escala logarítmica)", "asignatura": "Asignatura",
                       "tipo_interaccion": "Tipo de interacción"},
               title="Eventos por tipo de interacción · comparación legible")
    f.update_layout(template="plotly_white", legend_title_text="Tipo de interacción")
    st.plotly_chart(f, use_container_width=True)
    m = filtrar(mapa).groupby(["dia_semana", "hora"], as_index=False)["eventos"].sum()
    pivote = m.pivot(index="dia_semana", columns="hora", values="eventos").reindex(range(7)).fillna(0)
    pivote.index = DIAS
    f = px.imshow(pivote, aspect="auto", color_continuous_scale=COLOR_CONTINUA,
                  labels=dict(x="Hora", y="Día", color="Eventos"),
                  title="Mapa de calor: actividad por día y hora")
    st.plotly_chart(f, use_container_width=True)

# ---- Rendimiento
with t_ren:
    st.subheader("Rendimiento académico")
    r1, r2 = st.columns(2)
    with r1:
        f = px.bar(his, x="rango_nota_pct", y="cantidad", color="asignatura", barmode="group",
                   title="Distribución de notas (% sobre la escala)")
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
    with r2:
        f = px.bar(est, x="asignatura", y="cantidad", color="estado_a_la_fecha",
                   color_discrete_map=COLOR_ESTADO, barmode="group",
                   title="Cantidad de alumnos por estado a la fecha")
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
    ins = filtrar(instrumentos)
    f = px.bar(ins, x="promedio_nota_100", y="instrumento", color="asignatura",
               orientation="h", title="Nota media por instrumento (sobre 100)")
    f.update_layout(template="plotly_white", height=max(350, 28 * len(ins)))
    st.plotly_chart(f, use_container_width=True)

# ---- Notas vs participación
with t_rel:
    st.subheader("Relación entre participación y notas")
    rel = filtrar(relacion).dropna(subset=["nota_pct"])
    variable = st.selectbox("Medida de participación:",
                            ["tiempo_uso_min", "interacciones", "eventos_trazabilidad"])
    f = px.scatter(rel, x=variable, y="nota_pct", color="estado_a_la_fecha",
                   color_discrete_map=COLOR_ESTADO, hover_data=["id_estudiante", "asignatura"],
                   title="Nota (%) vs. participación")
    f.update_layout(template="plotly_white")
    st.plotly_chart(f, use_container_width=True)
    cor = res[["asignatura", "correlacion_tiempo_nota",
               "correlacion_interacciones_nota", "correlacion_eventos_nota"]]
    st.markdown("**Correlación de Pearson** (relación, no causalidad):")
    st.dataframe(cor, use_container_width=True, hide_index=True)

# ---- Ficha individual
with t_ind:
    st.subheader("Ficha individual")
    i1, i2 = st.columns(2)
    asig = i1.selectbox("Asignatura:", materias, key="ficha_asig")
    ids = sorted(relacion.loc[relacion["asignatura"] == asig, "id_estudiante"].unique())
    alumno = i2.selectbox("Estudiante:", ids, key="ficha_alumno")   # el primero queda preseleccionado
    fila = relacion[(relacion["asignatura"] == asig) & (relacion["id_estudiante"] == alumno)].iloc[0]
    estado = fila["estado_a_la_fecha"]
    st.markdown(f"### {SEMAFORO.get(estado, estado)}")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Nota (%)", "-" if pd.isna(fila["nota_pct"]) else f"{fila['nota_pct']:.1f}")
    k2.metric("Tiempo de uso (min)", "-" if pd.isna(fila["tiempo_uso_min"]) else f"{fila['tiempo_uso_min']:.0f}")
    k3.metric("Interacciones", "-" if pd.isna(fila["interacciones"]) else f"{fila['interacciones']:.0f}")
    k4.metric("Eventos", "-" if pd.isna(fila["eventos_trazabilidad"]) else f"{fila['eventos_trazabilidad']:.0f}")
    cal = tabla("calificaciones", PROC)
    mis_notas = cal[(cal["id_estudiante"] == alumno) & (cal["asignatura"] == asig)]
    if "usa_en_nota_final" in mis_notas.columns:
        mis_notas = mis_notas[mis_notas["usa_en_nota_final"] == True]
    st.markdown("**Notas por instrumento**")
    if mis_notas.empty:
        st.info("Este estudiante no tiene notas registradas.")
    else:
        f = px.bar(mis_notas, x="instrumento", y="nota_100", title="Notas (sobre 100)")
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
    detalle = trazabilidad[(trazabilidad["asignatura"] == asig) &
                           (trazabilidad["id_estudiante"] == alumno)]
    st.markdown("**Trazabilidad individual**")
    if detalle.empty:
        st.info("No hay eventos de trazabilidad para este estudiante.")
    else:
        tr1, tr2 = st.columns(2)
        with tr1:
            serie = detalle.assign(dia=detalle["fecha"].dt.floor("D")).groupby(
                "dia", as_index=False).size().rename(columns={"size": "eventos"})
            f = px.line(serie, x="dia", y="eventos", markers=True, title="Eventos por día")
            f.update_layout(template="plotly_white")
            st.plotly_chart(f, use_container_width=True)
        with tr2:
            por_tipo = detalle.groupby("tipo_interaccion", as_index=False).size().rename(columns={"size": "eventos"})
            f = px.bar(por_tipo, x="eventos", y="tipo_interaccion", orientation="h",
                       title="Eventos por tipo")
            f.update_layout(template="plotly_white")
            st.plotly_chart(f, use_container_width=True)

# ---- Matrícula y alertas
with t_mat:
    st.subheader("Matrícula y alertas")
    st.markdown("**Comparación de estudiantes matriculados y activos**")
    comparacion = res[["asignatura", "matriculados", "activos"]].melt(
        id_vars="asignatura", var_name="grupo", value_name="estudiantes")
    comparacion["grupo"] = comparacion["grupo"].map({"matriculados": "Matriculados", "activos": "Activos"})
    f = px.bar(comparacion, x="asignatura", y="estudiantes", color="grupo", barmode="group",
               color_discrete_map=COLOR_MATRICULA,
               title="Matriculados vs. activos por asignatura")
    f.update_layout(template="plotly_white")
    st.plotly_chart(f, use_container_width=True)
    for _, r in ale.iterrows():
        if r["cantidad"] > 0:
            clase = ("alert-card--matricula" if r["alerta"] == "No matriculado con actividad"
                     else "alert-card--participacion")
            st.markdown(
                f'<div class="alert-card {clase}"><strong>{r["asignatura"]}</strong>: '
                f'{int(r["cantidad"])} · {r["alerta"]}</div>',
                unsafe_allow_html=True)
    f = px.bar(ale, x="asignatura", y="cantidad", color="alerta", barmode="group",
               color_discrete_map=COLOR_ALERTA,
               title="Alertas de matrícula por asignatura")
    f.update_layout(template="plotly_white")
    st.plotly_chart(f, use_container_width=True)

st.divider()
st.caption("Universidad de Palermo • Business Intelligence & Analytics • TFI")
