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
diaria = tabla("kpi_actividad_diaria")
instrumentos = tabla("kpi_notas_instrumento")
trazabilidad = cargar_trazabilidad(str(PROC / "trazabilidad.csv"))
# Solo estudiantes con matrícula vigente (mismo criterio que src/kpi.py).
# kpi_relacion_estudiante ya contiene únicamente matriculados.
matriculados = relacion[["id_estudiante", "asignatura"]].drop_duplicates()
trazabilidad = trazabilidad.merge(matriculados, on=["id_estudiante", "asignatura"], how="inner")


# -------------------------------------------------------------
# 3. SIDEBAR: FILTROS
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### Filtros")
    materias_all = sorted(resumen["asignatura"].unique())
    materias = st.multiselect("Asignatura:", materias_all, default=materias_all)
    fecha_min = trazabilidad["fecha"].min().date()
    fecha_max = trazabilidad["fecha"].max().date()
    fecha_corte = st.date_input("Fecha de corte:", value=fecha_max,
                                min_value=fecha_min, max_value=fecha_max, format="DD/MM/YYYY",
                                help="Muestra la actividad de los alumnos hasta esta fecha.")
    dias_recientes = st.select_slider("Activo reciente = ingresó en los últimos:",
                                      options=[7, 14, 30], value=14,
                                      format_func=lambda d: f"{d} días")
    st.divider()
    st.caption("La fecha de corte cambia los indicadores de **actividad**. Las notas y los "
               "estados corresponden a la última foto de datos (24/10), porque las "
               "calificaciones no tienen fecha.")
    st.caption("Los estados son **a la fecha** (cursada abierta): "
               "no son calificaciones finales.")
    st.caption("Población: alumnos con matrícula vigente (salvo en alertas).")

if not materias:
    st.warning("Elegí al menos una asignatura.")
    st.stop()

# -------------------------------------------------------------
# 3.b ACTIVIDAD A LA FECHA DE CORTE
# -------------------------------------------------------------
# Se calcula desde la trazabilidad de los matriculados: un alumno está
# "activo" si tiene al menos un evento hasta la fecha de corte, y
# "activo reciente" si su último evento está dentro de la ventana elegida.
corte = pd.Timestamp(fecha_corte) + pd.Timedelta(days=1)          # incluye todo el día de corte
traz_corte = trazabilidad[trazabilidad["fecha"] < corte]
ultimo = traz_corte.groupby(["id_estudiante", "asignatura"], as_index=False)["fecha"].max()
ultimo = ultimo.rename(columns={"fecha": "ultimo_ingreso"})
actividad_corte = matriculados.merge(ultimo, on=["id_estudiante", "asignatura"], how="left")
actividad_corte["dias_sin_ingresar"] = (corte - actividad_corte["ultimo_ingreso"]).dt.days
actividad_corte["situacion"] = "Sin actividad"
actividad_corte.loc[actividad_corte["ultimo_ingreso"].notna(), "situacion"] = "Sin actividad reciente"
actividad_corte.loc[actividad_corte["dias_sin_ingresar"] < dias_recientes, "situacion"] = "Activo reciente"
actividad_corte = actividad_corte[actividad_corte["asignatura"].isin(materias)]
COLOR_SITUACION = {"Activo reciente": "#4E8A6A", "Sin actividad reciente": "#D39B35",
                   "Sin actividad": "#C86460"}


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
activos = int((actividad_corte["situacion"] != "Sin actividad").sum())
recientes = int((actividad_corte["situacion"] == "Activo reciente").sum())
total_con_notas = res["con_notas"].sum()
nota_media = ((res["promedio_nota_pct_solo_con_notas"] * res["con_notas"]).sum() / total_con_notas
              if total_con_notas > 0 else None)
sin_part = int(ale.loc[ale["alerta"] == "Matriculado sin participación", "cantidad"].sum())
no_mat = int(ale.loc[ale["alerta"] == "No matriculado con actividad", "cantidad"].sum())

st.caption(f"Actividad a la fecha de corte: **{fecha_corte:%d/%m/%Y}**")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Matriculados", f"{matric:,}".replace(",", "."))
c2.metric("Activos", f"{activos / matric * 100:.1f}%" if matric else "-", f"{activos} de {matric}")
c3.metric(f"Activos últimos {dias_recientes} días",
          f"{recientes / matric * 100:.1f}%" if matric else "-",
          f"{recientes} de {matric}", delta_color="off")
c4.metric("Nota media (%)", "Sin datos" if nota_media is None else f"{nota_media:.1f}",
          None if nota_media is None else "solo alumnos con notas")
c5.metric("Alertas de matrícula", f"{sin_part + no_mat}",
          f"{sin_part} sin part. · {no_mat} no matric.", delta_color="off")
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
        # Se arma desde la trazabilidad (no desde kpi_actividad_semanal) para que
        # incluya solo eventos hasta el día de corte, aunque caiga a mitad de semana.
        a = filtrar(traz_corte)
        dia = a["fecha"].dt.normalize()
        a = (a.assign(semana_inicio=dia - pd.to_timedelta(dia.dt.dayofweek, unit="D"))
             .groupby(["asignatura", "semana_inicio"], as_index=False).size()
             .rename(columns={"size": "eventos"}))
        if a.empty:
            st.info("No hay actividad registrada hasta la fecha de corte.")
        else:
            f = px.line(a, x="semana_inicio", y="eventos", color="asignatura",
                        labels={"semana_inicio": "Semana (inicio lunes)", "eventos": "Eventos",
                                "asignatura": "Asignatura"},
                        title="Actividad semanal (eventos del LMS)")
            f.update_layout(template="plotly_white")
            st.plotly_chart(f, use_container_width=True)
            if fecha_corte.weekday() != 6:
                st.caption("La última semana está incompleta: solo incluye eventos hasta la fecha de corte.")
    st.subheader("Actividad reciente de los estudiantes")
    st.caption(f"Situación de cada matriculado al {fecha_corte:%d/%m/%Y}: **activo reciente** si ingresó "
               f"en los últimos {dias_recientes} días, **sin actividad reciente** si ingresó antes pero "
               "no en ese período, y **sin actividad** si nunca ingresó.")
    act = (actividad_corte.groupby(["asignatura", "situacion"], as_index=False).size()
           .rename(columns={"size": "estudiantes"}))
    f = px.bar(act, x="asignatura", y="estudiantes", color="situacion", barmode="stack",
               color_discrete_map=COLOR_SITUACION,
               category_orders={"situacion": list(COLOR_SITUACION)},
               labels={"asignatura": "Asignatura", "estudiantes": "Estudiantes", "situacion": "Situación"},
               title="Situación de actividad por asignatura")
    f.update_layout(template="plotly_white")
    st.plotly_chart(f, use_container_width=True)
    sin_reciente = actividad_corte[actividad_corte["situacion"] != "Activo reciente"].sort_values(
        ["asignatura", "dias_sin_ingresar"], ascending=[True, False])
    with st.expander(f"Ver los {len(sin_reciente)} estudiantes sin actividad reciente (para contactar)"):
        st.dataframe(sin_reciente.assign(ultimo_ingreso=sin_reciente["ultimo_ingreso"].dt.strftime("%d/%m/%Y"))
                     [["asignatura", "id_estudiante", "situacion", "ultimo_ingreso", "dias_sin_ingresar"]]
                     .rename(columns={"asignatura": "Asignatura", "id_estudiante": "Estudiante",
                                      "situacion": "Situación", "ultimo_ingreso": "Último ingreso",
                                      "dias_sin_ingresar": "Días sin ingresar"}),
                     use_container_width=True, hide_index=True)
    conteo = actividad_corte.assign(
        activo=actividad_corte["situacion"] != "Sin actividad",
        reciente=actividad_corte["situacion"] == "Activo reciente").groupby(
        "asignatura", as_index=False)[["activo", "reciente"]].sum()
    tabla_general = res[["asignatura", "matriculados", "promedio_nota_pct_solo_con_notas", "con_notas"]].merge(
        conteo, on="asignatura")
    tabla_general["activo_pct"] = (tabla_general["activo"] / tabla_general["matriculados"] * 100).round(1)
    tabla_general["reciente_pct"] = (tabla_general["reciente"] / tabla_general["matriculados"] * 100).round(1)
    tabla_general = tabla_general[["asignatura", "matriculados", "activo", "activo_pct", "reciente", "reciente_pct",
                                   "promedio_nota_pct_solo_con_notas", "con_notas"]].rename(columns={
        "asignatura": "Asignatura", "matriculados": "Matriculados", "activo": "Activos",
        "activo_pct": "Activos (%)", "reciente": f"Activos últimos {dias_recientes} días",
        "reciente_pct": f"Activos últimos {dias_recientes} días (%)",
        "promedio_nota_pct_solo_con_notas": "Nota media (%)", "con_notas": "Alumnos con notas"})
    st.dataframe(tabla_general.round(1),
                 use_container_width=True, hide_index=True)

# ---- Participación
with t_par:
    st.subheader("Participación")
    p1, p2 = st.columns(2)
    with p1:
        f = px.bar(res, x="asignatura", y="tiempo_uso_promedio_min_por_matriculado",
                   labels={"asignatura": "Asignatura",
                           "tiempo_uso_promedio_min_por_matriculado": "Minutos por matriculado"},
                   title="Tiempo de uso promedio por matriculado (min)")
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
        st.caption("⚠️ Acumulado de todo el período (hasta el 24/10): el reporte de participación "
                   "del LMS trae el tiempo total de cada alumno sin fechas, por lo que no puede "
                   "recortarse a la fecha de corte.")
    with p2:
        cob = actividad_corte.assign(
            con_actividad=actividad_corte["situacion"] != "Sin actividad",
            reciente=actividad_corte["situacion"] == "Activo reciente").groupby(
            "asignatura", as_index=False)[["con_actividad", "reciente"]].mean()
        cob = cob.melt(id_vars="asignatura", var_name="medida", value_name="pct")
        cob["pct"] = cob["pct"] * 100
        cob["medida"] = cob["medida"].map({"con_actividad": "Con actividad hasta el corte",
                                           "reciente": f"Activos últimos {dias_recientes} días"})
        f = px.bar(cob, x="asignatura", y="pct", color="medida", barmode="group",
                   color_discrete_sequence=["#4F7892", "#6FA6A1"],
                   labels={"asignatura": "Asignatura", "pct": "% de matriculados", "medida": ""},
                   title="Cobertura de participación (% de matriculados)")
        f.update_layout(template="plotly_white", yaxis_range=[0, 100])
        st.plotly_chart(f, use_container_width=True)
        st.caption(f"Calculado a la fecha de corte ({fecha_corte:%d/%m/%Y}) desde la trazabilidad.")

    d = filtrar(diaria).copy()
    d["dia"] = pd.to_datetime(d["dia"])
    d = d[d["dia"] < corte]
    if d.empty:
        # Puede pasar si la primera actividad de las materias elegidas es posterior al corte.
        st.info("No hay actividad en el período: las asignaturas seleccionadas no registran "
                "eventos hasta la fecha de corte.")
        tr_periodo = trazabilidad.iloc[0:0]
    else:
        dia_min, dia_max = d["dia"].min().date(), d["dia"].max().date()
        if dia_min < dia_max:
            rango = st.slider("Rango de fechas:", dia_min, dia_max, (dia_min, dia_max),
                              format="DD/MM/YYYY")
        else:
            # Con un solo día de datos no se puede armar un rango deslizable.
            rango = (dia_min, dia_max)
            st.caption(f"Hay actividad en un solo día ({dia_min:%d/%m/%Y}) hasta la fecha de corte.")
        d = d[(d["dia"].dt.date >= rango[0]) & (d["dia"].dt.date <= rango[1])]
        f = px.line(d, x="dia", y="estudiantes_activos", color="asignatura",
                    labels={"dia": "Día", "estudiantes_activos": "Estudiantes activos",
                            "asignatura": "Asignatura"},
                    title="Estudiantes activos por día")
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
        st.subheader("Evolución de accesos")
        tr_periodo = trazabilidad[(trazabilidad["asignatura"].isin(materias)) &
                                  (trazabilidad["fecha"].dt.date >= rango[0]) &
                                  (trazabilidad["fecha"].dt.date <= rango[1])]
        tr_rango = tr_periodo[tr_periodo["tipo_interaccion"] == "Acceso/navegación"]
        accesos = tr_rango.assign(dia=tr_rango["fecha"].dt.floor("D")).groupby(
            ["dia", "asignatura"], as_index=False).size().rename(columns={"size": "accesos"})
        f = px.line(accesos, x="dia", y="accesos", color="asignatura", markers=True,
                    labels={"dia": "Día", "accesos": "Accesos", "asignatura": "Asignatura"},
                    title="Accesos/navegación por día")
        f.update_layout(template="plotly_white")
        st.plotly_chart(f, use_container_width=True)
    st.subheader("Actividad por estudiante")
    asig_det = st.selectbox("Asignatura para consultar:", materias, key="participacion_asig")
    ids_det = sorted(relacion.loc[relacion["asignatura"] == asig_det, "id_estudiante"].dropna().unique())
    if ids_det:
        alumno_det = st.selectbox("Estudiante:", ids_det, key="participacion_alumno")
        detalle = tr_periodo[(tr_periodo["asignatura"] == asig_det) &
                             (tr_periodo["id_estudiante"] == alumno_det)]
        if detalle.empty:
            st.info("Este estudiante no tiene actividad en el período seleccionado.")
        else:
            serie = detalle.assign(dia=detalle["fecha"].dt.floor("D")).groupby(
                ["dia", "tipo_interaccion"], as_index=False).size().rename(columns={"size": "eventos"})
            f = px.bar(serie, x="dia", y="eventos", color="tipo_interaccion",
                       color_discrete_map=COLOR_TIPOS,
                       labels={"dia": "Día", "eventos": "Eventos", "tipo_interaccion": "Tipo de interacción"},
                       title=f"Eventos por día y tipo · {alumno_det}")
            f.update_layout(template="plotly_white")
            st.plotly_chart(f, use_container_width=True)
    else:
        st.info("No hay estudiantes disponibles para esta asignatura.")

# ---- Trazabilidad
with t_tra:
    st.subheader("Trazabilidad")
    st.caption(f"Eventos hasta la fecha de corte ({fecha_corte:%d/%m/%Y}).")
    tc = filtrar(traz_corte)
    tp = tc.groupby(["asignatura", "tipo_interaccion"], as_index=False).size().rename(
        columns={"size": "eventos"})
    f = px.bar(tp, x="eventos", y="asignatura", color="tipo_interaccion",
               color_discrete_map=COLOR_TIPOS, barmode="group", orientation="h",
               log_x=True, height=430,
               labels={"eventos": "Eventos (escala logarítmica)", "asignatura": "Asignatura",
                       "tipo_interaccion": "Tipo de interacción"},
               title="Eventos por tipo de interacción · comparación legible")
    f.update_layout(template="plotly_white", legend_title_text="Tipo de interacción")
    st.plotly_chart(f, use_container_width=True)
    m = tc.assign(dia_semana=tc["fecha"].dt.dayofweek, hora=tc["fecha"].dt.hour).groupby(
        ["dia_semana", "hora"], as_index=False).size().rename(columns={"size": "eventos"})
    pivote = m.pivot(index="dia_semana", columns="hora", values="eventos").reindex(range(7)).fillna(0)
    pivote.index = DIAS
    f = px.imshow(pivote, aspect="auto", color_continuous_scale=COLOR_CONTINUA,
                  labels=dict(x="Hora", y="Día", color="Eventos"),
                  title="Mapa de calor: actividad por día y hora")
    st.plotly_chart(f, use_container_width=True)

# ---- Rendimiento
with t_ren:
    st.subheader("Rendimiento académico")
    st.caption("Notas y estados al 24/10 (última foto de datos): no dependen de la fecha de corte, "
               "porque las calificaciones no tienen fecha.")
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
    rel = filtrar(relacion).dropna(subset=["nota_pct"]).copy()

    # Grupos de riesgo: participación alta/baja según la mediana de interacciones
    # de cada asignatura, y nota por encima o por debajo del 60% de la escala.
    mediana = rel.groupby("asignatura")["interacciones"].transform("median")
    part_alta = rel["interacciones"] >= mediana
    nota_ok = rel["nota_pct"] >= 60
    rel["grupo_riesgo"] = "Sin riesgo"
    rel.loc[~part_alta & ~nota_ok, "grupo_riesgo"] = "Riesgo alto"
    rel.loc[part_alta & ~nota_ok, "grupo_riesgo"] = "Con dificultades"
    rel.loc[~part_alta & nota_ok, "grupo_riesgo"] = "Autónomos"
    COLOR_RIESGO = {"Riesgo alto": "#C86460", "Con dificultades": "#D39B35",
                    "Autónomos": "#6FA6A1", "Sin riesgo": "#4E8A6A"}
    DESCRIPCION_RIESGO = {
        "Riesgo alto": "Participan poco y tienen nota menor a 60%. Acción: contactarlos para evitar el abandono.",
        "Con dificultades": "Participan, pero no alcanzan el 60%. Acción: ofrecer apoyo académico.",
        "Autónomos": "Aprueban con poco uso del campus. Acción: seguimiento habitual.",
        "Sin riesgo": "Participan y aprueban. Acción: seguimiento habitual."}

    st.caption("Notas e interacciones acumuladas al 24/10: esta vista no depende de la fecha de corte.")
    st.markdown("**Grupos de riesgo**")
    st.caption("Participación alta o baja según la mediana de interacciones de cada asignatura; "
               "nota por encima o por debajo del 60% de la escala.")
    columnas = st.columns(4)
    for col, grupo in zip(columnas, COLOR_RIESGO):
        cant = int((rel["grupo_riesgo"] == grupo).sum())
        col.metric(grupo, cant, f"{cant / len(rel) * 100:.0f}% de los alumnos con notas" if len(rel) else None,
                   delta_color="off", help=DESCRIPCION_RIESGO[grupo])

    NOMBRES_MEDIDA = {"interacciones": "Interacciones en el LMS", "tiempo_uso_min": "Tiempo de uso (min)",
                      "eventos_trazabilidad": "Eventos de trazabilidad"}
    m1, m2 = st.columns(2)
    variable = m1.selectbox("Medida de participación:", list(NOMBRES_MEDIDA),
                            format_func=NOMBRES_MEDIDA.get)
    colorear = m2.radio("Colorear por:", ["Grupo de riesgo", "Estado a la fecha"], horizontal=True)
    if colorear == "Grupo de riesgo":
        color, mapa_color = "grupo_riesgo", COLOR_RIESGO
    else:
        color, mapa_color = "estado_a_la_fecha", COLOR_ESTADO
    f = px.scatter(rel, x=variable, y="nota_pct", color=color,
                   color_discrete_map=mapa_color, category_orders={color: list(mapa_color)},
                   hover_data=["id_estudiante", "asignatura"],
                   labels={variable: NOMBRES_MEDIDA[variable], "nota_pct": "Nota (% de la escala)",
                           "grupo_riesgo": "Grupo de riesgo", "estado_a_la_fecha": "Estado a la fecha",
                           "id_estudiante": "Estudiante", "asignatura": "Asignatura"},
                   title="Nota (%) vs. participación")
    f.add_hline(y=60, line_dash="dot", line_color="#94A3B8")
    f.update_layout(template="plotly_white")
    st.plotly_chart(f, use_container_width=True)
    if variable != "interacciones":
        st.caption("Los grupos se calculan con las interacciones; con otra medida en el eje, "
                   "algunos puntos pueden aparecer del otro lado de la mitad.")

    a_contactar = rel[rel["grupo_riesgo"].isin(["Riesgo alto", "Con dificultades"])].sort_values(
        ["grupo_riesgo", "asignatura", "nota_pct"], ascending=[False, True, True])
    with st.expander(f"Ver los {len(a_contactar)} estudiantes en riesgo alto o con dificultades"):
        st.dataframe(a_contactar[["grupo_riesgo", "asignatura", "id_estudiante", "nota_pct", "interacciones",
                                  "estado_a_la_fecha"]].rename(columns={
            "grupo_riesgo": "Grupo", "asignatura": "Asignatura", "id_estudiante": "Estudiante",
            "nota_pct": "Nota (%)", "interacciones": "Interacciones", "estado_a_la_fecha": "Estado"}).round(1),
            use_container_width=True, hide_index=True)
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
    detalle = traz_corte[(traz_corte["asignatura"] == asig) &
                         (traz_corte["id_estudiante"] == alumno)]
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
    comparacion = res[["asignatura", "matriculados"]].merge(
        actividad_corte[actividad_corte["situacion"] != "Sin actividad"].groupby(
            "asignatura", as_index=False).size().rename(columns={"size": "activos"}),
        on="asignatura", how="left").fillna(0).melt(
        id_vars="asignatura", var_name="grupo", value_name="estudiantes")
    comparacion["grupo"] = comparacion["grupo"].map({"matriculados": "Matriculados", "activos": "Activos"})
    f = px.bar(comparacion, x="asignatura", y="estudiantes", color="grupo", barmode="group",
               color_discrete_map=COLOR_MATRICULA,
               title="Matriculados vs. activos por asignatura")
    f.update_layout(template="plotly_white")
    st.plotly_chart(f, use_container_width=True)
    st.caption("El gráfico de arriba usa la fecha de corte. Las alertas de abajo se calculan sobre "
               "todo el período (hasta el 24/10).")
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
