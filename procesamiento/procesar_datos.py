#!/usr/bin/env python3
"""
TFI BI & Analytics - Paso 6.1: Procesamiento de datos (LMS)

Lee las 4 fuentes (trazabilidad, participación, calificaciones, matriculados) de las
3 asignaturas, las limpia, estandariza los IDs, trata duplicados / nulos /
inconsistencias y deja un modelo unificado listo para los KPIs (6.2) y dashboards (7).

Uso:
    python procesar_datos.py RUTA_A_DATOS_LMS [CARPETA_SALIDA]

    RUTA_A_DATOS_LMS: carpeta ya descomprimida que contiene las carpetas de las
                      asignaturas y la carpeta "Matriculados".

Salida (CSV UTF-8 con BOM, abre bien en Excel/Power BI/Tableau; + .parquet si hay pyarrow):
    matricula, participacion, trazabilidad, calificaciones (formato largo),
    notas_finales, situacion_estudiante, personal_excluido y informe_calidad_datos.

Requiere: pandas, openpyxl  (opcional: pyarrow)
"""
import glob
import html
import os
import re
import sys
import time

import pandas as pd

# --------------------------------------------------------------------------------------
# CONFIGURACIÓN: reglas académicas (diapositiva 4 de la consigna) y decisiones de limpieza
# --------------------------------------------------------------------------------------
ASIGNATURAS = ["Álgebra", "Algoritmos y Estructuras de Datos", "Probabilidad y Estadística"]

# umbrales: (promociona >=, regular >=) ; por debajo = Libre
UMBRALES = {
    "Álgebra": (85, 60),                              # sobre 120 pts, acumulativo
    "Probabilidad y Estadística": (85, 60),           # promedio sobre 100
    "Algoritmos y Estructuras de Datos": (90, 60),    # promedio sobre 100
}
ALGEBRA_MAX_TOTAL = 120

# En Probabilidad existe "Recuperatorio: Evaluación Semanal Nº1". Si True, la nota del
# recuperatorio REEMPLAZA a la del instrumento original (lo habitual). Si False, se
# promedia como un instrumento más.
RECUPERATORIO_REEMPLAZA = True

ID_ALUMNO = re.compile(r"^ALU_\d{4}$")
LOG = []  # registro de calidad de datos


def log(fuente, asignatura, problema, cantidad, decision):
    LOG.append(dict(fuente=fuente, asignatura=asignatura, problema=problema,
                    registros_afectados=int(cantidad), decision=decision))


def norm_id(s):
    return s.astype(str).str.strip().str.upper().replace({"NAN": pd.NA, "": pd.NA})


# --------------------------------------------------------------------------------------
# 1) MATRÍCULA
# --------------------------------------------------------------------------------------
def cargar_matricula(base):
    out = []
    for asig in ASIGNATURAS:
        df = pd.read_excel(os.path.join(base, "Matriculados", f"{asig}.xlsx"), header=1)
        n0 = len(df)
        df = df.rename(columns={"Alumno": "nombre_completo", "Identificación": "id_estudiante",
                                "Comisión": "comision", "Estado Insc.": "estado_insc",
                                "Instancia": "instancia", "Fecha inscripción": "fecha_inscripcion",
                                "Nro de Transacción": "nro_transaccion"})
        df["id_estudiante"] = norm_id(df["id_estudiante"])
        # fila pie "Cantidad de filas: N" y filas sin ID
        sin_id = df["id_estudiante"].isna().sum()
        df = df[df["id_estudiante"].notna()].copy()
        log("matricula", asig, "Filas sin ID (pie 'Cantidad de filas' / vacías)", sin_id, "Eliminadas")
        bad = (~df["id_estudiante"].str.match(ID_ALUMNO)).sum()
        if bad:
            log("matricula", asig, "IDs con formato distinto a ALU_####", bad, "Se conservan, revisar")
        df["fecha_inscripcion"] = pd.to_datetime(df["fecha_inscripcion"], format="%d/%m/%Y %H:%M:%S",
                                                 errors="coerce")
        df["nombre_completo"] = df["nombre_completo"].str.strip()
        df["asignatura"] = asig
        # duplicados: una fila por alumno y materia. Prioridad: Aceptada > Baja, luego la más reciente
        df["_prio"] = (df["estado_insc"] == "Aceptada").astype(int)
        df = df.sort_values(["id_estudiante", "_prio", "fecha_inscripcion"], ascending=[True, False, False])
        dup = df["id_estudiante"].duplicated().sum()
        log("matricula", asig, "IDs duplicados (baja + re-inscripción, o varias bajas)", dup,
            "Se conserva 1 fila: prioridad Aceptada y luego la inscripción más reciente")
        df = df.drop_duplicates("id_estudiante").drop(columns="_prio")
        df["matriculado"] = df["estado_insc"].eq("Aceptada")
        log("matricula", asig, "Alumnos finalmente en estado 'Baja'", (~df["matriculado"]).sum(),
            "Se marcan matriculado=False (no cuentan como inscriptos)")
        out.append(df)
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------------------
# 2) PARTICIPACIÓN
# --------------------------------------------------------------------------------------
def hhmm_a_minutos(s):
    if pd.isna(s):
        return pd.NA
    m = re.match(r"^\s*(\d+):(\d{2})(?::(\d{2}))?\s*$", str(s))
    if not m:
        return pd.NA
    h, mi, se = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return h * 60 + mi + se / 60


def cargar_participacion(base):
    cols = {"Usuario": "id_estudiante", "Apellido": "apellido", "Nombre": "nombre", "Perfil": "perfil",
            "Fecha alta": "fecha_alta", "Avance": "avance_pct", "Interacciones": "interacciones",
            "Primera interacción": "primera_interaccion", "Última interacción": "ultima_interaccion",
            "Tiempo estimado de uso": "tiempo_uso_hhmm", "Cantidad de emails enviados": "emails_enviados"}
    out = []
    for asig in ASIGNATURAS:
        f = glob.glob(os.path.join(base, asig, "reporte_participacion*.xlsx"))[0]
        df = pd.read_excel(f, header=5)
        df = df.iloc[1:]  # segunda fila de encabezado (Cantidad/Cargados...)
        df = df[list(cols)].rename(columns=cols)
        df = df[df["id_estudiante"].notna()].copy()
        df["id_estudiante"] = norm_id(df["id_estudiante"])
        df["asignatura"] = asig
        for c in ["avance_pct", "interacciones", "emails_enviados"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["fecha_alta"] = pd.to_datetime(df["fecha_alta"], format="%d/%m/%Y", errors="coerce")
        for c in ["primera_interaccion", "ultima_interaccion"]:
            df[c] = pd.to_datetime(df[c], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        df["tiempo_uso_min"] = df["tiempo_uso_hhmm"].map(hhmm_a_minutos).astype("Float64")
        dup = df["id_estudiante"].duplicated().sum()
        log("participacion", asig, "IDs duplicados", dup, "Se conserva la fila con más interacciones")
        df = df.sort_values("interacciones", ascending=False).drop_duplicates("id_estudiante")
        nunca = df["primera_interaccion"].isna().sum()
        log("participacion", asig, "Usuarios sin primera/última interacción (nunca ingresaron)", nunca,
            "Se dejan nulos y se crea la bandera nunca_ingreso (no se imputan)")
        df["nunca_ingreso"] = df["primera_interaccion"].isna() | (df["interacciones"].fillna(0) == 0)
        out.append(df)
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------------------
# 3) TRAZABILIDAD
# --------------------------------------------------------------------------------------
def cargar_trazabilidad(base):
    cols = {"Fecha": "fecha", "IP Usuario": "ip", "Usuario": "id_estudiante", "Perfil": "perfil",
            "Sección": "seccion", "Acción": "accion", "Descripción": "descripcion"}
    out = []
    for asig in ASIGNATURAS:
        t0 = time.time()
        f = glob.glob(os.path.join(base, asig, "reporte_trazabilidad*.xlsx"))[0]
        df = pd.read_excel(f, header=5)
        n0 = len(df)
        df = df[list(cols)].rename(columns=cols)
        df["id_estudiante"] = norm_id(df["id_estudiante"])
        dup = df.duplicated().sum()
        df = df.drop_duplicates()
        log("trazabilidad", asig, "Filas exactamente duplicadas", dup, "Eliminadas")
        nulos = df["accion"].isna().sum()
        df["accion"] = df["accion"].fillna("Sin dato")
        log("trazabilidad", asig, "Acción nula", nulos, "Reemplazada por 'Sin dato' (no se borra el evento)")
        df["fecha"] = pd.to_datetime(df["fecha"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        log("trazabilidad", asig, "Fechas no interpretables", df["fecha"].isna().sum(), "Eliminadas")
        df = df[df["fecha"].notna()]
        df["asignatura"] = asig
        df["fecha_dia"] = df["fecha"].dt.date
        df["hora"] = df["fecha"].dt.hour
        df["dia_semana"] = df["fecha"].dt.dayofweek  # 0 = lunes
        # tipo de interacción agrupado (para el KPI "interacciones por tipo")
        a = df["accion"].str.lower()
        df["tipo_interaccion"] = "Otros"
        df.loc[a.str.startswith("acceder") | a.str.startswith("navegar"), "tipo_interaccion"] = "Acceso/navegación"
        df.loc[a.str.contains("ver texto|ver archivo|ver tópico|ver tema|ver noticia|descargar|ver unidad"),
               "tipo_interaccion"] = "Lectura de materiales"
        df.loc[a.str.contains("evaluaci|realización|realizacion|encuesta"), "tipo_interaccion"] = "Evaluaciones"
        df.loc[a.str.contains("intervencion|mensaje|responder|redactar|enviar"), "tipo_interaccion"] = "Comunicación/foros"
        df.loc[a.str.contains("calificaci|notas"), "tipo_interaccion"] = "Calificaciones"
        out.append(df)
        print(f"   trazabilidad {asig}: {n0:,} filas leídas en {time.time() - t0:.0f}s")
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------------------
# 4) CALIFICACIONES
# --------------------------------------------------------------------------------------
def limpiar_nombre_instrumento(s):
    s = html.unescape(str(s))
    s = re.sub(r"^\s*Calificación:\s*", "", s)
    s = re.sub(r"[^\w\sº°\-:·.ÁÉÍÓÚáéíóúñÑ]", "", s)   # quita emojis/símbolos
    return re.sub(r"\s+", " ", s).strip()


def cargar_calificaciones(base):
    out = []
    for asig in ASIGNATURAS:
        for f in sorted(glob.glob(os.path.join(base, asig, "calificaciones_alumnos*.xlsx"))):
            raw = pd.read_excel(f, header=None, nrows=4)
            instrumento = limpiar_nombre_instrumento(raw.iloc[2, 0])
            df = pd.read_excel(f, header=6)
            df = df.rename(columns={"Usuario": "id_estudiante", "Nota": "nota_texto",
                                    "Observaciones": "observacion"})
            df = df[["id_estudiante", "nota_texto", "observacion"]]
            df = df[df["id_estudiante"].notna()].copy()
            df["id_estudiante"] = norm_id(df["id_estudiante"])
            pts = df["nota_texto"].astype(str).str.extract(r"^\s*([\d.]+)\s*/\s*([\d.]+)\s*$")
            df["puntos"] = pd.to_numeric(pts[0], errors="coerce")
            df["maximo"] = pd.to_numeric(pts[1], errors="coerce")
            sin_nota = df["puntos"].isna().sum()
            if sin_nota:
                log("calificaciones", asig, f"Nota no numérica en '{instrumento}'", sin_nota,
                    "Se elimina (equivale a no rendido)")
            df = df[df["puntos"].notna()]
            dup = df["id_estudiante"].duplicated().sum()
            if dup:
                log("calificaciones", asig, f"Alumnos duplicados en '{instrumento}'", dup,
                    "Se conserva la mayor nota")
                df = df.sort_values("puntos", ascending=False).drop_duplicates("id_estudiante")
            df["asignatura"] = asig
            df["instrumento"] = instrumento
            df["es_recuperatorio"] = instrumento.lower().startswith("recuperatorio")
            if instrumento.lower().startswith("recuperatorio"):
                tipo = "Recuperatorio"
            elif re.search(r"parcial", instrumento, re.I):
                tipo = "Parcial"
            elif re.search(r"autoevaluaci", instrumento, re.I):
                tipo = "Autoevaluación"
            else:
                tipo = "Actividad/Evaluación"
            df["tipo_instrumento"] = tipo
            df["nota_100"] = (df["puntos"] / df["maximo"] * 100).round(2)
            out.append(df)
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------------------
# 5) NOTAS FINALES SEGÚN REGLA DE CADA ASIGNATURA
# --------------------------------------------------------------------------------------
def condicion(nota, asig):
    prom, reg = UMBRALES[asig]
    if pd.isna(nota):
        return pd.NA
    return "Promociona" if nota >= prom else ("Regular" if nota >= reg else "Libre")


def calcular_notas_finales(cal, universo):
    """
    universo: DataFrame (id_estudiante, asignatura) a evaluar.
    Dos variantes, porque el enunciado no define qué pasa con lo no rendido:
      - nota_final_estricta : lo no rendido cuenta como 0
      - nota_final_rendidos : se promedia solo lo efectivamente rendido
    En Álgebra (acumulativo) ambas coinciden: la suma de puntos obtenidos.
    """
    res = []
    for asig in ASIGNATURAS:
        c = cal[cal["asignatura"] == asig].copy()
        ids = universo[universo["asignatura"] == asig][["id_estudiante"]].drop_duplicates()
        if asig == "Álgebra":
            suma = c.groupby("id_estudiante")["puntos"].sum().rename("nota_final_estricta")
            r = ids.merge(suma, on="id_estudiante", how="left")
            r["nota_final_estricta"] = r["nota_final_estricta"].fillna(0)
            # "rendidos": lo obtenido se proyecta a la escala de 120 según lo efectivamente rendido
            # (puntos obtenidos / puntos posibles de lo rendido * 120)
            pos = c.groupby("id_estudiante")["maximo"].sum()
            r["nota_final_rendidos"] = (r["nota_final_estricta"] / r["id_estudiante"].map(pos) * ALGEBRA_MAX_TOTAL).round(2)
            r["instrumentos_rendidos"] = r["id_estudiante"].map(c.groupby("id_estudiante").size()).fillna(0)
            r["instrumentos_totales"] = c["instrumento"].nunique()
            r["escala_maxima"] = ALGEBRA_MAX_TOTAL
            max_disp = c.drop_duplicates("instrumento")["maximo"].sum()
            if max_disp < ALGEBRA_MAX_TOTAL:
                log("calificaciones", asig,
                    f"Faltan instrumentos: solo hay {max_disp:.0f} de {ALGEBRA_MAX_TOTAL} puntos posibles "
                    f"({c['instrumento'].nunique()} archivos de notas)", 0,
                    "La nota 'estricta' no puede superar ese tope: usar 'rendidos' o pedir los archivos faltantes")
        else:
            if asig == "Probabilidad y Estadística" and RECUPERATORIO_REEMPLAZA:
                c["base"] = c["instrumento"].str.replace(r"^Recuperatorio:\s*", "", regex=True)
                # por alumno e instrumento base: si hay recuperatorio, vale el recuperatorio
                c = (c.sort_values("es_recuperatorio")
                      .groupby(["id_estudiante", "base"], as_index=False).last())
            else:
                c["base"] = c["instrumento"]
            n_inst = c["base"].nunique()
            prom = c.groupby("id_estudiante")["nota_100"].mean().rename("nota_final_rendidos")
            suma = c.groupby("id_estudiante")["nota_100"].sum()
            r = ids.merge(prom, on="id_estudiante", how="left")
            r["nota_final_estricta"] = (r["id_estudiante"].map(suma).fillna(0) / n_inst).round(2)
            r["nota_final_rendidos"] = r["nota_final_rendidos"].round(2)
            r["instrumentos_rendidos"] = r["id_estudiante"].map(c.groupby("id_estudiante").size()).fillna(0)
            r["instrumentos_totales"] = n_inst
            r["escala_maxima"] = 100
        r["asignatura"] = asig
        r["condicion_estricta"] = r["nota_final_estricta"].map(lambda x: condicion(x, asig))
        r["condicion_rendidos"] = r["nota_final_rendidos"].map(lambda x: condicion(x, asig))
        res.append(r)
    return pd.concat(res, ignore_index=True)


# --------------------------------------------------------------------------------------
# 6) MODELO UNIFICADO
# --------------------------------------------------------------------------------------
def main(base, salida):
    os.makedirs(salida, exist_ok=True)
    print("1/6 Matrícula...");        mat = cargar_matricula(base)
    print("2/6 Participación...");    par = cargar_participacion(base)
    print("3/6 Trazabilidad (tarda un poco)..."); tra = cargar_trazabilidad(base)
    print("4/6 Calificaciones...");   cal = cargar_calificaciones(base)

    # --- separar alumnos de personal (docentes, tutores, coordinadores, invitados) ---
    def es_alumno(df):
        return df["perfil"].eq("Alumnos") & df["id_estudiante"].str.match(ID_ALUMNO, na=False)
    for nombre, df in [("participacion", par), ("trazabilidad", tra)]:
        for asig in ASIGNATURAS:
            n = (~es_alumno(df[df["asignatura"] == asig])).sum()
            log(nombre, asig, "Registros de personal (Tutores/Coordinadores/Invitados, IDs DOC_/STAFF_)", n,
                "Excluidos de los KPIs de alumnos; guardados en personal_excluido")
    personal = pd.concat([
        par[~es_alumno(par)].assign(fuente="participacion"),
        tra[~es_alumno(tra)].assign(fuente="trazabilidad")], ignore_index=True)
    par = par[es_alumno(par)].copy()
    tra = tra[es_alumno(tra)].copy()

    print("5/6 Notas finales y situación...")
    # universo: todo alumno que aparezca en alguna fuente de esa asignatura
    universo = pd.concat([
        mat[["id_estudiante", "asignatura"]], par[["id_estudiante", "asignatura"]],
        cal[["id_estudiante", "asignatura"]], tra[["id_estudiante", "asignatura"]].drop_duplicates()
    ]).drop_duplicates()
    notas = calcular_notas_finales(cal, universo)

    eventos = tra.groupby(["id_estudiante", "asignatura"]).agg(
        eventos_trazabilidad=("fecha", "size"), dias_activos=("fecha_dia", "nunique"),
        primer_evento=("fecha", "min"), ultimo_evento=("fecha", "max")).reset_index()

    sit = (universo
           .merge(mat[["id_estudiante", "asignatura", "nombre_completo", "estado_insc", "matriculado",
                       "fecha_inscripcion"]], on=["id_estudiante", "asignatura"], how="left")
           .merge(par.drop(columns=["perfil"]), on=["id_estudiante", "asignatura"], how="left")
           .merge(eventos, on=["id_estudiante", "asignatura"], how="left")
           .merge(notas, on=["id_estudiante", "asignatura"], how="left"))
    sit["matriculado"] = sit["matriculado"].fillna(False).astype(bool)
    sit["en_padron"] = sit["estado_insc"].notna()
    sit["tiene_actividad"] = (sit["interacciones"].fillna(0) > 0) | (sit["eventos_trazabilidad"].fillna(0) > 0)
    sit["tiene_notas"] = sit["instrumentos_rendidos"].fillna(0) > 0
    sit["situacion_matricula"] = pd.NA
    sit.loc[sit["matriculado"] & sit["tiene_actividad"], "situacion_matricula"] = "Matriculado con actividad"
    sit.loc[sit["matriculado"] & ~sit["tiene_actividad"], "situacion_matricula"] = "Matriculado sin participación"
    sit.loc[~sit["matriculado"] & sit["tiene_actividad"], "situacion_matricula"] = "NO matriculado con actividad"
    sit.loc[~sit["matriculado"] & ~sit["tiene_actividad"], "situacion_matricula"] = "No matriculado sin actividad"
    # semáforo para el dashboard individual (variante 'rendidos' = más justa durante la cursada)
    sit["semaforo"] = sit["condicion_rendidos"].map({"Promociona": "Verde", "Regular": "Amarillo", "Libre": "Rojo"})
    sit.loc[sit["semaforo"].isna(), "semaforo"] = "Sin notas"
    log("modelo", "todas", "Alumnos NO matriculados (o en Baja) con actividad en el LMS",
        (sit["situacion_matricula"] == "NO matriculado con actividad").sum(),
        "Se conservan y se marcan (insumo de la alerta de matrícula)")
    log("modelo", "todas", "Alumnos matriculados sin ninguna participación",
        (sit["situacion_matricula"] == "Matriculado sin participación").sum(),
        "Se conservan y se marcan (mapa de inscriptos sin participación)")

    # --- guardar ---
    print("6/6 Guardando...")
    salidas = {"matricula": mat, "participacion": par, "trazabilidad": tra, "calificaciones": cal,
               "notas_finales": notas, "situacion_estudiante": sit, "personal_excluido": personal,
               "informe_calidad_datos": pd.DataFrame(LOG)}
    for nombre, df in salidas.items():
        df.to_csv(os.path.join(salida, f"{nombre}.csv"), index=False, encoding="utf-8-sig")
        try:
            df.to_parquet(os.path.join(salida, f"{nombre}.parquet"), index=False)
        except Exception:
            pass
        print(f"   {nombre}: {len(df):,} filas")
    print(f"\nListo. Archivos en: {os.path.abspath(salida)}")
    return salidas


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "datos_procesados")
