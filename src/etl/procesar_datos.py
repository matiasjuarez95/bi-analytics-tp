# -*- coding: utf-8 -*-
"""
TFI BI & Analytics - Paso 6.1: Procesamiento de datos (ETL del LMS)

Integra, limpia y unifica las 4 fuentes del LMS (trazabilidad, participación,
calificaciones y matriculados) de las 3 asignaturas y deja un modelo listo para
los KPIs (6.2) y los dashboards.

Uso (desde la raíz del repositorio):
    python -m src.etl.procesar_datos data/raw data/processed

    data/raw/        Excel originales (.xlsx) en las subcarpetas algebra/, probabilidad/,
                     algoritmos/ y matriculados/ (no se convierten ni se suben al repo).
    data/processed/  Salidas (CSV, y Parquet si hay pyarrow). Tampoco se suben al repo.

Principios (ver docs/procesamiento_6_1.md):
  * Nada se descarta en silencio: todo filtro registra cantidades antes/después en
    informe_calidad_datos y las filas descartadas quedan en descartados.csv.
  * Se separa lo REAL (puntos acumulados, promedio de lo rendido) de lo ESTIMADO
    (proyecciones, promedio con faltantes). Una estimación nunca define un estado definitivo.
  * Si falta información para un estado definitivo, queda "Pendiente" (no se asume).
"""
from __future__ import annotations

import argparse
import glob
import html
import os
import re
import sys
import unicodedata

import numpy as np
import pandas as pd

# =====================================================================================
# CONFIGURACIÓN (reglas de la consigna y supuestos pendientes de confirmar con el docente)
# =====================================================================================
ASIGNATURAS = ["Álgebra", "Algoritmos y Estructuras de Datos", "Probabilidad y Estadística"]

# Texto que debe aparecer (sin tildes, en minúsculas) en el nombre de la carpeta / archivo
CLAVE_ASIGNATURA = {
    "Álgebra": "algebra",
    "Algoritmos y Estructuras de Datos": "algoritmos",
    "Probabilidad y Estadística": "probabilidad",
}
CLAVE_MATRICULADOS = "matriculados"

# Reglas académicas (consigna). instrumentos_esperados=None => la consigna no fija cuántos son.
REGLAS = {
    "Álgebra": dict(tipo="acumulativo", maximo=120, promociona=85, regular=60, instrumentos_esperados=8),
    "Probabilidad y Estadística": dict(tipo="promedio", maximo=100, promociona=85, regular=60,
                                       instrumentos_esperados=None),
    "Algoritmos y Estructuras de Datos": dict(tipo="promedio", maximo=100, promociona=90, regular=60,
                                              instrumentos_esperados=None),
}

# DECISIONES (las confirmadas por el docente se detallan en docs/procesamiento_6_1.md)
#  - Instrumentos faltantes: un examen que existe y el alumno no rindió vale 0 (confirmado).
#  - Álgebra: se trabaja con los instrumentos disponibles (los faltantes son a propósito, confirmado).
#  - Recuperatorio (confirmado): sin nota original queda el recuperatorio; con original aprobada se conserva
#    la original (no debería recuperar); con original desaprobada queda la mejor de las dos.
CURSADA_CERRADA = False          # SIN CONFIRMAR: mientras sea False, ningún estado Regular/Libre es definitivo
RECUPERATORIO_MODO = "docente"   # "docente" | "mayor_nota" | "reemplaza" | "aparte"
NOTAS_DUPLICADAS_CRITERIO = "mayor_nota"  # solo se aplica si aparecen duplicados (hoy hay 0; supuesto)

ID_ALUMNO = re.compile(r"^ALU_\d{4}$")
ESTADOS_DEFINIDOS = ("Promociona", "Regular", "Libre")

# Registro de calidad y de filas descartadas (se reinicia en cada ejecución)
LOG: list[dict] = []
DESCARTADOS: list[pd.DataFrame] = []


class DatosError(Exception):
    """Problema con los archivos de entrada (falta uno, hay varios candidatos, columnas ausentes)."""


# =====================================================================================
# Utilidades de registro
# =====================================================================================
def reiniciar_registro():
    LOG.clear()
    DESCARTADOS.clear()


def registrar(fuente, asignatura, problema, afectados, decision, antes=None, despues=None):
    LOG.append(dict(fuente=fuente, asignatura=asignatura, problema=problema,
                    filas_antes=antes, filas_despues=despues,
                    registros_afectados=int(afectados), decision=decision))


def descartar(df, fuente, asignatura, motivo):
    """Guarda las filas descartadas para poder auditarlas."""
    if len(df):
        DESCARTADOS.append(df.assign(fuente=fuente, asignatura=asignatura, motivo=motivo))


def _norm(texto):
    """Minúsculas, sin tildes ni símbolos: 'Álgebra.xlsx' -> 'algebraxlsx'."""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", t.lower())


def norm_id(serie):
    """IDs en mayúsculas y sin espacios; vacíos -> NaN."""
    out = serie.astype(str).str.strip().str.upper()
    return out.where(~out.isin(["", "NAN", "NONE", "<NA>"]), np.nan)


def _exigir_columnas(df, columnas, archivo):
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise DatosError(f"{os.path.basename(archivo)}: faltan las columnas {faltan}. "
                         f"Se encontraron: {list(df.columns)[:12]}")


# =====================================================================================
# 0) DETECCIÓN DETERMINÍSTICA DE ARCHIVOS
# =====================================================================================
def _xlsx(carpeta):
    return sorted(f for f in glob.glob(os.path.join(carpeta, "*.xlsx"))
                  if not os.path.basename(f).startswith("~$"))


def _carpeta_unica(raiz, clave, que):
    cands = [d for d in sorted(os.listdir(raiz))
             if os.path.isdir(os.path.join(raiz, d)) and clave in _norm(d)]
    if len(cands) != 1:
        existentes = [d for d in sorted(os.listdir(raiz)) if os.path.isdir(os.path.join(raiz, d))]
        raise DatosError(f"No se pudo determinar la carpeta de {que} en '{raiz}': buscaba una subcarpeta "
                         f"que contenga '{clave}' y encontré {len(cands)} {cands}. "
                         f"Subcarpetas existentes: {existentes}")
    return os.path.join(raiz, cands[0])


def _archivo_unico(archivos, prefijo, carpeta, que):
    cands = [f for f in archivos if _norm(os.path.basename(f)).startswith(prefijo)]
    if len(cands) != 1:
        raise DatosError(f"En '{carpeta}' se esperaba exactamente 1 archivo de {que} y hay {len(cands)}: "
                         f"{[os.path.basename(c) for c in cands]}")
    return cands[0]


def encontrar_archivos(raiz):
    """Devuelve {asignatura: {trazabilidad, participacion, calificaciones[], matricula}} o falla claro."""
    if not os.path.isdir(raiz):
        raise DatosError(f"La carpeta de datos '{raiz}' no existe.")
    carpeta_mat = _carpeta_unica(raiz, CLAVE_MATRICULADOS, "matriculados")
    archivos_mat = _xlsx(carpeta_mat)
    out = {}
    for asig in ASIGNATURAS:
        clave = CLAVE_ASIGNATURA[asig]
        carpeta = _carpeta_unica(raiz, clave, asig)
        archivos = _xlsx(carpeta)
        traz = _archivo_unico(archivos, "reportetrazabilidad", carpeta, "trazabilidad")
        part = _archivo_unico(archivos, "reporteparticipacion", carpeta, "participación")
        cals = [f for f in archivos if _norm(os.path.basename(f)).startswith("calificacionesalumnos")]
        if not cals:
            raise DatosError(f"En '{carpeta}' no hay archivos 'calificaciones_alumnos*.xlsx'.")
        mats = [f for f in archivos_mat if clave in _norm(os.path.basename(f))]
        if len(mats) != 1:
            raise DatosError(f"En '{carpeta_mat}' se esperaba 1 archivo de matrícula de {asig} "
                             f"(nombre con '{clave}') y hay {len(mats)}: {[os.path.basename(m) for m in mats]}")
        otros = [f for f in archivos if f not in cals + [traz, part]]
        if otros:
            registrar("archivos", asig, "Archivos .xlsx no reconocidos (se ignoran)", len(otros),
                      f"Se ignoran: {[os.path.basename(o) for o in otros]}")
        out[asig] = dict(trazabilidad=traz, participacion=part, calificaciones=cals, matricula=mats[0])
    return out


# =====================================================================================
# 1) MATRÍCULA: estado vigente según el último movimiento
# =====================================================================================
def leer_matricula(archivo, asig):
    df = pd.read_excel(archivo, header=1)
    _exigir_columnas(df, ["Alumno", "Identificación", "Estado Insc.", "Fecha inscripción"], archivo)
    df = df.rename(columns={"Alumno": "nombre_completo", "Identificación": "id_estudiante",
                            "Comisión": "comision", "Estado Insc.": "estado_insc", "Instancia": "instancia",
                            "Fecha inscripción": "fecha_inscripcion", "Nro de Transacción": "nro_transaccion"})
    antes = len(df)
    df["id_estudiante"] = norm_id(df["id_estudiante"])
    sin_id = df["id_estudiante"].isna()
    descartar(df[sin_id], "matricula", asig, "Fila sin ID (pie 'Cantidad de filas' u otra no válida)")
    df = df[~sin_id].copy()
    registrar("matricula", asig, "Filas sin ID (pie 'Cantidad de filas' / vacías)", sin_id.sum(),
              "Descartadas (quedan en descartados.csv)", antes, len(df))
    df["fecha_inscripcion"] = pd.to_datetime(df["fecha_inscripcion"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df["nombre_completo"] = df["nombre_completo"].astype(str).str.strip()
    df["asignatura"] = asig
    nat = df["fecha_inscripcion"].isna().sum()
    if nat:
        registrar("matricula", asig, "Fechas de inscripción inválidas", nat,
                  "Se conservan; en el desempate se ubican primero (movimiento más antiguo)")
    bad = (~df["id_estudiante"].str.match(ID_ALUMNO)).sum()
    if bad:
        registrar("matricula", asig, "IDs con formato distinto a ALU_####", bad, "Se conservan, revisar")
    return df


def resolver_matricula(df, asig="-"):
    """
    Una fila vigente por alumno. El estado vigente es el del movimiento MÁS RECIENTE.
    Orden de desempate explícito: 1) fecha de inscripción, 2) nro. de transacción,
    3) si persiste el empate, prevalece 'Baja' (criterio conservador).
    Devuelve (vigentes, movimientos); movimientos conserva TODAS las filas para auditoría.
    """
    d = df.copy().reset_index(drop=True)
    d["_baja"] = (d["estado_insc"].astype(str).str.strip().str.lower() == "baja").astype(int)
    d["_nro"] = pd.to_numeric(d["nro_transaccion"], errors="coerce") if "nro_transaccion" in d else np.nan
    d = d.sort_values(["id_estudiante", "fecha_inscripcion", "_nro", "_baja"],
                      na_position="first", kind="mergesort").reset_index(drop=True)
    d["n_movimientos"] = d.groupby("id_estudiante")["id_estudiante"].transform("size")
    d["orden_movimiento"] = d.groupby("id_estudiante").cumcount() + 1
    d["es_vigente"] = d["orden_movimiento"] == d["n_movimientos"]

    # Casos ambiguos: fecha y nro. de transacción no coinciden, empate de fecha o fecha inválida
    ambiguos = set()
    for _id, g in d[d["n_movimientos"] > 1].groupby("id_estudiante"):
        f, n = g["fecha_inscripcion"], g["_nro"]
        if f.isna().any():
            ambiguos.add(_id)
            continue
        ult_f = f.max()
        estados_f = set(g.loc[f == ult_f, "estado_insc"])
        if (f == ult_f).sum() > 1:
            ambiguos.add(_id)
        elif n.notna().all() and set(g.loc[n == n.max(), "estado_insc"]) != estados_f:
            ambiguos.add(_id)
    d["caso_ambiguo"] = d["id_estudiante"].isin(ambiguos)

    vig = d[d["es_vigente"]].copy()
    vig["matriculado"] = vig["estado_insc"].astype(str).str.strip().str.lower().eq("aceptada")
    movs = d.drop(columns=["_baja", "_nro"])
    vig = vig.drop(columns=["_baja", "_nro", "es_vigente", "orden_movimiento"])

    multi = d.loc[d["n_movimientos"] > 1, "id_estudiante"].nunique()
    registrar("matricula", asig, "IDs con más de un movimiento (altas/bajas)", multi,
              "Estado vigente = movimiento más reciente (desempate: fecha, nro. transacción, Baja). "
              "Todos los movimientos quedan en matricula_movimientos.csv", len(d), len(vig))
    reinsc = sum(1 for _, g in d[d["n_movimientos"] > 1].groupby("id_estudiante")
                 if g["estado_insc"].iloc[-1] == "Aceptada" and (g["estado_insc"] == "Baja").any())
    registrar("matricula", asig, "  de ellos, bajas seguidas de una nueva inscripción aceptada", reinsc,
              "Quedan matriculados (el último movimiento es Aceptada)")
    registrar("matricula", asig, "  de ellos, casos ambiguos (fecha/nro. transacción no concuerdan o empate)",
              len(ambiguos), "Revisar manualmente: " + (", ".join(sorted(ambiguos)) or "ninguno"))
    registrar("matricula", asig, "Alumnos cuyo estado vigente es 'Baja'", (~vig["matriculado"]).sum(),
              "matriculado=False (no cuentan como inscriptos)")
    homonimos = (df.groupby("nombre_completo")["id_estudiante"].nunique() > 1).sum()
    if homonimos:
        registrar("matricula", asig, "Nombres repetidos con IDs distintos (posibles homónimos)", homonimos,
                  "Se tratan como personas distintas: la clave es el ID, no el nombre")
    return vig, movs


# =====================================================================================
# 2) SEPARACIÓN ALUMNOS / PERSONAL (común a participación y trazabilidad)
# =====================================================================================
def separar_alumnos_personal(df, fuente, asig):
    perfil_ok = df["perfil"].astype(str).str.strip().str.lower().eq("alumnos")
    id_ok = df["id_estudiante"].astype(str).str.match(ID_ALUMNO)
    es_alumno = perfil_ok & id_ok
    inconsistente = perfil_ok ^ id_ok
    motivo = pd.Series(np.where(inconsistente, "Inconsistencia perfil/ID (revisar)",
                                "Personal: perfil distinto de Alumnos e ID no ALU_####"), index=df.index)
    personal = df[~es_alumno].assign(fuente=fuente, motivo_exclusion=motivo[~es_alumno])
    registrar(fuente, asig, "Registros de personal (Tutores/Coordinadores/Invitados, IDs DOC_/STAFF_)",
              (~es_alumno & ~inconsistente).sum(), "Excluidos de los KPIs de alumnos; en personal_excluido.csv",
              len(df), int(es_alumno.sum()))
    if inconsistente.any():
        registrar(fuente, asig, "Inconsistencias perfil/ID (perfil Alumnos sin ID ALU_ o viceversa)",
                  inconsistente.sum(), "Excluidos y marcados para revisión (personal_excluido.csv)")
    return df[es_alumno].copy(), personal


# =====================================================================================
# 3) PARTICIPACIÓN
# =====================================================================================
def _hhmm_a_minutos(s):
    m = re.match(r"^\s*(\d+):(\d{2})(?::(\d{2}))?\s*$", str(s))
    if not m:
        return np.nan
    return int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3) or 0) / 60


def leer_participacion(archivo, asig):
    df = pd.read_excel(archivo, header=5).iloc[1:]   # la 2.ª fila de encabezado (Cantidad/Cargados) se descarta
    cols = {"Usuario": "id_estudiante", "Apellido": "apellido", "Nombre": "nombre", "Perfil": "perfil",
            "Fecha alta": "fecha_alta", "Avance": "avance_pct", "Interacciones": "interacciones",
            "Primera interacción": "primera_interaccion", "Última interacción": "ultima_interaccion",
            "Tiempo estimado de uso": "tiempo_uso_hhmm", "Cantidad de emails enviados": "emails_enviados"}
    _exigir_columnas(df, list(cols), archivo)
    df = df[list(cols)].rename(columns=cols)
    antes = len(df)
    df["id_estudiante"] = norm_id(df["id_estudiante"])
    sin_id = df["id_estudiante"].isna()
    descartar(df[sin_id], "participacion", asig, "ID nulo")
    df = df[~sin_id].copy()
    registrar("participacion", asig, "Filas sin ID", sin_id.sum(), "Descartadas", antes, len(df))
    df["asignatura"] = asig
    for c in ["avance_pct", "interacciones", "emails_enviados"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["fecha_alta"] = pd.to_datetime(df["fecha_alta"], format="%d/%m/%Y", errors="coerce")
    for c in ["primera_interaccion", "ultima_interaccion"]:
        df[c] = pd.to_datetime(df[c], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df["tiempo_uso_min"] = df["tiempo_uso_hhmm"].map(_hhmm_a_minutos).astype(float)
    return df


def procesar_participacion(df, asig):
    alumnos, personal = separar_alumnos_personal(df, "participacion", asig)
    dup = alumnos["id_estudiante"].duplicated(keep=False)
    if dup.any():
        alumnos = alumnos.sort_values("interacciones", ascending=False, kind="mergesort")
        descartar(alumnos[alumnos["id_estudiante"].duplicated()], "participacion", asig, "ID duplicado")
        alumnos = alumnos.drop_duplicates("id_estudiante")
    registrar("participacion", asig, "IDs de alumnos duplicados", dup.sum(),
              "Se conserva la fila con más interacciones; el resto va a descartados.csv")
    alumnos["nunca_ingreso"] = alumnos["primera_interaccion"].isna() | (alumnos["interacciones"].fillna(0) == 0)
    registrar("participacion", asig, "Alumnos que nunca ingresaron (sin primera interacción o 0 interacciones)",
              alumnos["nunca_ingreso"].sum(), "Se dejan los nulos y se marca nunca_ingreso (no se imputan)")
    return alumnos, personal


# =====================================================================================
# 4) TRAZABILIDAD
# =====================================================================================
def marcar_duplicados_trazabilidad(df):
    """
    El LMS no trae ID de evento: dos interacciones reales pueden coincidir en todas las columnas.
    Por eso NO se borran: la 2.ª y siguientes repeticiones se marcan como duplicado_potencial.
    """
    cols = [c for c in ["fecha", "ip", "id_estudiante", "perfil", "seccion", "accion", "descripcion"]
            if c in df.columns]
    d = df.copy()
    d["duplicado_potencial"] = d.duplicated(subset=cols, keep="first")
    return d


def clasificar_tipo_interaccion(accion):
    a = accion.astype(str).str.lower()
    tipo = pd.Series("Otros", index=accion.index)
    tipo[a.str.startswith("acceder") | a.str.startswith("navegar")] = "Acceso/navegación"
    tipo[a.str.contains("ver texto|ver archivo|ver tópico|ver tema|ver noticia|descargar|ver unidad")] = "Lectura de materiales"
    tipo[a.str.contains("evaluaci|realización|realizacion|encuesta")] = "Evaluaciones"
    tipo[a.str.contains("intervencion|mensaje|responder|redactar|enviar")] = "Comunicación/foros"
    tipo[a.str.contains("calificaci|notas")] = "Calificaciones"
    return tipo


def leer_trazabilidad(archivo, asig):
    cols = {"Fecha": "fecha", "IP Usuario": "ip", "Usuario": "id_estudiante", "Perfil": "perfil",
            "Sección": "seccion", "Acción": "accion", "Descripción": "descripcion"}
    raw = pd.read_excel(archivo, header=5)
    _exigir_columnas(raw, list(cols), archivo)
    df = raw[list(cols)].rename(columns=cols)
    n0 = len(df)
    df["id_estudiante"] = norm_id(df["id_estudiante"])
    df["fecha"] = pd.to_datetime(df["fecha"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    m_id, m_fecha = df["id_estudiante"].isna(), df["fecha"].isna()
    descartar(df[m_id], "trazabilidad", asig, "ID de usuario nulo")
    descartar(df[~m_id & m_fecha], "trazabilidad", asig, "Fecha inválida")
    registrar("trazabilidad", asig, "Eventos con ID de usuario nulo", m_id.sum(), "Descartados", n0, n0 - m_id.sum())
    registrar("trazabilidad", asig, "Eventos con fecha inválida", (~m_id & m_fecha).sum(), "Descartados",
              n0 - m_id.sum(), int((~m_id & ~m_fecha).sum()))
    df = df[~m_id & ~m_fecha].copy()
    nulos = df["accion"].isna().sum()
    df["accion"] = df["accion"].fillna("Sin dato")
    registrar("trazabilidad", asig, "Acción nula", nulos, "Se reemplaza por 'Sin dato' (el evento se conserva)")
    df = marcar_duplicados_trazabilidad(df)
    registrar("trazabilidad", asig, "Eventos idénticos repetidos (sin ID de evento para distinguirlos)",
              df["duplicado_potencial"].sum(),
              "NO se eliminan: se marcan duplicado_potencial=True; el KPI decide si los excluye")
    df["asignatura"] = asig
    df["fecha_dia"] = df["fecha"].dt.date
    df["hora"] = df["fecha"].dt.hour
    df["dia_semana"] = df["fecha"].dt.dayofweek  # 0 = lunes
    df["tipo_interaccion"] = clasificar_tipo_interaccion(df["accion"])
    otros = df[df["tipo_interaccion"] == "Otros"]
    registrar("trazabilidad", asig, "Acciones sin categoría reconocida (tipo 'Otros')", len(otros),
              "Se conservan como 'Otros'. Más frecuentes: " +
              ", ".join(f"{k} ({v})" for k, v in otros["accion"].value_counts().head(5).items()))
    return df, n0


# =====================================================================================
# 5) CALIFICACIONES
# =====================================================================================
def limpiar_nombre_instrumento(s):
    s = html.unescape(str(s))
    s = re.sub(r"^\s*Calificación:\s*", "", s)
    s = re.sub(r"[^\w\sº°\-:·.ÁÉÍÓÚáéíóúñÑ]", "", s)  # quita emojis y símbolos
    return re.sub(r"\s+", " ", s).strip()


def _tipo_instrumento(nombre):
    if nombre.lower().startswith("recuperatorio"):
        return "Recuperatorio"
    if re.search(r"parcial", nombre, re.I):
        return "Parcial"
    if re.search(r"autoevaluaci", nombre, re.I):
        return "Autoevaluación"
    return "Actividad/Evaluación"


def leer_calificaciones(archivo, asig):
    cabecera = pd.read_excel(archivo, header=None, nrows=4)
    instrumento = limpiar_nombre_instrumento(cabecera.iloc[2, 0])
    df = pd.read_excel(archivo, header=6)
    _exigir_columnas(df, ["Usuario", "Nota"], archivo)
    df = df.rename(columns={"Usuario": "id_estudiante", "Nota": "nota_texto", "Observaciones": "observacion"})
    df = df[["id_estudiante", "nota_texto", "observacion"]]
    df["id_estudiante"] = norm_id(df["id_estudiante"])
    df = df[df["id_estudiante"].notna()].copy()
    n0 = len(df)
    pts = df["nota_texto"].astype(str).str.extract(r"^\s*([\d.]+)\s*/\s*([\d.]+)\s*$")
    df["puntos"] = pd.to_numeric(pts[0], errors="coerce")
    df["maximo"] = pd.to_numeric(pts[1], errors="coerce")
    df["asignatura"] = asig
    df["instrumento"] = instrumento
    # nota no numérica o fuera de rango
    m_nan = df["puntos"].isna() | df["maximo"].isna()
    m_rango = ~m_nan & ((df["puntos"] < 0) | (df["maximo"] <= 0) | (df["puntos"] > df["maximo"]))
    descartar(df[m_nan], "calificaciones", asig, f"Nota no numérica en '{instrumento}'")
    descartar(df[m_rango], "calificaciones", asig, f"Nota fuera de rango en '{instrumento}'")
    if m_nan.any() or m_rango.any():
        registrar("calificaciones", asig, f"Notas no numéricas / fuera de rango en '{instrumento}'",
                  (m_nan | m_rango).sum(), "Descartadas (equivale a no rendido)", n0, int((~m_nan & ~m_rango).sum()))
    df = df[~m_nan & ~m_rango].copy()
    # alumnos repetidos dentro del mismo instrumento
    dup = df["id_estudiante"].duplicated(keep=False)
    registrar("calificaciones", asig, f"Alumnos con más de una nota en '{instrumento}'", dup.sum(),
              ("Ninguno: se verificó que no hay duplicados" if not dup.any() else
               f"Criterio '{NOTAS_DUPLICADAS_CRITERIO}' (SUPUESTO: no se sabe si son intentos o correcciones); "
               "las filas no usadas van a descartados.csv"))
    if dup.any():
        df = df.sort_values("puntos", ascending=(NOTAS_DUPLICADAS_CRITERIO != "mayor_nota"), kind="mergesort")
        descartar(df[df["id_estudiante"].duplicated()], "calificaciones", asig, f"Nota repetida en '{instrumento}'")
        df = df.drop_duplicates("id_estudiante")
    df["nota_100"] = (df["puntos"] / df["maximo"] * 100).round(2)
    df["nota_10"] = (df["puntos"] / df["maximo"] * 10).round(2)   # instrumento normalizado a 10 (p. ej. 25/25*10)
    df["es_recuperatorio"] = instrumento.lower().startswith("recuperatorio")
    df["tipo_instrumento"] = _tipo_instrumento(instrumento)
    return df


def _aprobada(c):
    """Aprobada según la columna 'observacion' del LMS; si no existe, se usa nota_100 >= 60."""
    if "observacion" in c.columns:
        return c["observacion"].astype(str).str.strip().str.lower().eq("aprobada")
    return c["nota_100"] >= 60


def aplicar_recuperatorios(cal, modo=RECUPERATORIO_MODO):
    """
    Vincula cada recuperatorio con su evaluación original y marca qué fila vale para la nota final
    (usa_en_nota_final). SE ELIGE LA FILA COMPLETA (no se mezclan valores de registros distintos).
      docente    : (CONFIRMADO POR EL DOCENTE) sin nota original -> queda el recuperatorio; original aprobada ->
                   se conserva la original (no debería recuperar); original desaprobada -> la mejor de las dos
      mayor_nota : vale la mayor de las dos
      reemplaza  : el recuperatorio siempre reemplaza a la original
      aparte     : el recuperatorio cuenta como un instrumento más
    Las filas no usadas NO se borran: quedan en calificaciones con usa_en_nota_final=False.
    """
    if modo not in ("docente", "mayor_nota", "reemplaza", "aparte"):
        raise ValueError(f"Modo de recuperatorio inválido: {modo}")
    c = cal.copy().reset_index(drop=True)
    c["aprobada"] = _aprobada(c)
    base = c["instrumento"].str.replace(r"^\s*Recuperatorio\s*:\s*", "", regex=True).str.strip()
    c["instrumento_base"] = np.where(c["es_recuperatorio"] & (modo != "aparte"), base, c["instrumento"])
    claves = ["id_estudiante", "asignatura", "instrumento_base"]
    if modo == "aparte" or not c["es_recuperatorio"].any():
        c["usa_en_nota_final"] = True
        return c

    orig, rec = c[~c["es_recuperatorio"]], c[c["es_recuperatorio"]]
    # el recuperatorio debe vincularse a una evaluación existente en los datos
    originales = set(zip(orig["asignatura"], orig["instrumento"]))
    for (asig, inst, b), _ in rec.groupby(["asignatura", "instrumento", "instrumento_base"]):
        if (asig, b) not in originales:
            registrar("calificaciones", asig, f"Recuperatorio '{inst}' sin evaluación original en los datos", 1,
                      f"No se pudo vincular con '{b}': se trata como instrumento propio")
    m = (rec.reset_index().rename(columns={"index": "idx_r"})[["idx_r"] + claves + ["nota_100"]]
         .merge(orig.reset_index().rename(columns={"index": "idx_o"})[["idx_o"] + claves + ["nota_100", "aprobada"]],
                on=claves, how="left", suffixes=("_r", "_o")))
    sin_orig = m["idx_o"].isna()
    apro = m["aprobada"].fillna(False).astype(bool)
    mejora = m["nota_100_r"] > m["nota_100_o"]
    if modo == "docente":
        usa_r = sin_orig | (~apro & mejora)
    elif modo == "mayor_nota":
        usa_r = sin_orig | mejora
    else:  # reemplaza
        usa_r = pd.Series(True, index=m.index)
    reemplazadas = set(m.loc[usa_r & ~sin_orig, "idx_o"].astype(int))
    usa = (set(orig.index) - reemplazadas) | set(m.loc[usa_r, "idx_r"].astype(int))
    c["usa_en_nota_final"] = c.index.isin(list(usa))
    for asig, g in m.groupby("asignatura"):
        so, ap, me, ur = sin_orig[g.index], apro[g.index], mejora[g.index], usa_r[g.index]
        registrar("calificaciones", asig, "Alumnos que rindieron recuperatorio", len(g),
                  f"Modo '{modo}'. Sin nota original (queda el recuperatorio): {int(so.sum())}; "
                  f"original aprobada: {int((~so & ap).sum())}; original desaprobada: {int((~so & ~ap).sum())} "
                  f"(recuperatorio mejor en {int((~so & ~ap & me).sum())}). Recuperatorios que quedan como nota: {int(ur.sum())}")
    return c


# =====================================================================================
# 6) NOTAS FINALES: lo REAL separado de lo ESTIMADO
# =====================================================================================
def condicion(valor, asig):
    """Condición según los umbrales de la consigna. NaN -> None."""
    if valor is None or pd.isna(valor):
        return None
    r = REGLAS[asig]
    return "Promociona" if valor >= r["promociona"] else ("Regular" if valor >= r["regular"] else "Libre")


def _entero_o_na(valor, n):
    return pd.Series([valor if valor is not None else pd.NA] * n, dtype="Int64")


def calcular_notas_finales(cal, universo, cursada_cerrada=None):
    """
    universo: DataFrame (id_estudiante, asignatura).  cal: con aplicar_recuperatorios() ya aplicado.

    Criterio del docente: si un examen existe (otros alumnos lo rindieron) y el alumno no lo rindió, vale 0.
    Se calcula sobre los instrumentos PRESENTES en los datos.

    nota_a_la_fecha (la que usa el semáforo; es una estimación mientras la cursada siga abierta):
      Álgebra  : puntos acumulados / puntos máximos observados * 120 (= proyeccion_120_observados)
      Prob/Algo: promedio_con_faltantes
    Se conservan además los valores reales y alternativos:
      puntos_acumulados (REAL), proyeccion_120_rendidos (solo sobre lo rendido), promedio_normalizado_10
      (cada instrumento llevado a 10: p. ej. 25/25*10), promedio_observados (solo lo rendido).
    Estado definitivo: solo "Promociona" en Álgebra con >= 85 puntos acumulados reales; el resto queda
    "Pendiente" hasta que la cursada esté cerrada. Sin notas nunca pasa a Libre.
    """
    cursada_cerrada = CURSADA_CERRADA if cursada_cerrada is None else cursada_cerrada
    if "usa_en_nota_final" in cal.columns:
        cal = cal[cal["usa_en_nota_final"]]
    base_col = "instrumento_base" if "instrumento_base" in cal.columns else "instrumento"
    res = []
    for asig, regla in REGLAS.items():
        ids = universo.loc[universo["asignatura"] == asig, ["id_estudiante"]].drop_duplicates().reset_index(drop=True)
        c = cal[cal["asignatura"] == asig]
        g = c.groupby("id_estudiante")
        n = len(ids)
        en_datos = int(c[base_col].nunique())
        esperados = regla["instrumentos_esperados"]
        r = ids.copy()
        r["asignatura"] = asig
        r["instrumentos_rendidos"] = r["id_estudiante"].map(g.size()).fillna(0).astype(int)
        r["instrumentos_en_datos"] = en_datos
        r["instrumentos_esperados"] = _entero_o_na(esperados, n)
        r["completitud_datos"] = round(en_datos / esperados, 3) if esperados else np.nan
        r["completitud_alumno"] = (r["instrumentos_rendidos"] / en_datos).round(3) if en_datos else np.nan
        r["datos_completos"] = bool(esperados and en_datos >= esperados)
        sin = (r["instrumentos_rendidos"] == 0).to_numpy()
        cerrada = np.full(n, bool(cursada_cerrada))

        if regla["tipo"] == "acumulativo":
            acum = r["id_estudiante"].map(g["puntos"].sum()).where(~sin)
            max_obs = float(c.groupby(base_col)["maximo"].max().sum())
            posibles = r["id_estudiante"].map(g["maximo"].sum())
            n10 = (c["puntos"] / c["maximo"] * 10).groupby(c["id_estudiante"]).sum()
            r["puntos_acumulados"] = acum                                                       # REAL
            r["puntos_maximos_observados"] = max_obs
            r["proyeccion_120_rendidos"] = (acum / posibles * regla["maximo"]).round(2)           # ESTIMACIÓN
            r["proyeccion_120_observados"] = (acum / max_obs * regla["maximo"]).round(2) if max_obs else np.nan
            r["promedio_normalizado_10"] = (r["id_estudiante"].map(n10) / en_datos).round(2).where(~sin) if en_datos else np.nan
            r["rendimiento_observado_pct"] = (acum / posibles * 100).round(2)
            valor = r["proyeccion_120_observados"]
            real_promociona = acum.to_numpy(dtype=float) >= regla["promociona"]
        else:
            prom_obs = r["id_estudiante"].map(g["nota_100"].mean()).round(2).where(~sin)
            suma = r["id_estudiante"].map(g["nota_100"].sum())
            prom_falt = (suma / en_datos).round(2).where(~sin) if en_datos else pd.Series(np.nan, index=r.index)
            r["promedio_observados"] = prom_obs
            r["promedio_con_faltantes"] = prom_falt            # lo no rendido = 0 (criterio del docente)
            r["denominador_confirmado"] = True                  # instrumentos presentes en los datos
            r["rendimiento_observado_pct"] = prom_obs
            valor = prom_falt
            real_promociona = np.zeros(n, dtype=bool)
        r["nota_a_la_fecha"] = valor
        r["escala_nota_a_la_fecha"] = regla["maximo"]
        v = valor.to_numpy(dtype=float)
        r["estado_provisorio"] = np.select([sin, v >= regla["promociona"], v >= regla["regular"]],
                                           ["Sin notas", "Promociona", "Regular"], default="Libre")
        r["estado_definitivo"] = np.select(
            [sin, real_promociona, cerrada & (v >= regla["promociona"]), cerrada & (v >= regla["regular"]), cerrada],
            ["Sin notas", "Promociona", "Promociona", "Regular", "Libre"], default="Pendiente")
        res.append(r)
    return pd.concat(res, ignore_index=True)


# =====================================================================================
# 7) SITUACIÓN DEL ESTUDIANTE Y VALIDACIONES
# =====================================================================================
def clasificar_situacion_matricula(matriculado, tiene_actividad):
    m, a = matriculado.astype(bool), tiene_actividad.astype(bool)
    return pd.Series(np.select(
        [m & a, m & ~a, ~m & a], ["Matriculado con actividad", "Matriculado sin participación",
                                  "NO matriculado con actividad"],
        default="No matriculado sin actividad"), index=matriculado.index)


_SEMAFORO = {"Promociona": "Verde", "Regular": "Amarillo", "Libre": "Rojo",
             "Pendiente": "Gris (pendiente)", "Sin notas": "Sin notas"}


def construir_situacion(universo, mat, par, eventos, notas):
    sit = (universo
           .merge(mat[["id_estudiante", "asignatura", "nombre_completo", "estado_insc", "matriculado",
                       "fecha_inscripcion"]], on=["id_estudiante", "asignatura"], how="left", validate="one_to_one")
           .merge(par.drop(columns=["perfil"]), on=["id_estudiante", "asignatura"], how="left", validate="one_to_one")
           .merge(eventos, on=["id_estudiante", "asignatura"], how="left", validate="one_to_one")
           .merge(notas, on=["id_estudiante", "asignatura"], how="left", validate="one_to_one"))
    sit["matriculado"] = sit["matriculado"].eq(True)   # sin registro en el padrón -> False
    sit["en_padron"] = sit["estado_insc"].notna()
    sit["tiene_actividad"] = (sit["interacciones"].fillna(0) > 0) | (sit["eventos_trazabilidad"].fillna(0) > 0)
    sit["tiene_notas"] = sit["instrumentos_rendidos"].fillna(0) > 0
    sit["situacion_matricula"] = clasificar_situacion_matricula(sit["matriculado"], sit["tiene_actividad"])
    sit["semaforo"] = sit["estado_provisorio"].map(_SEMAFORO)
    sit["semaforo_definitivo"] = sit["estado_definitivo"].isin(ESTADOS_DEFINIDOS)
    return sit


def validar_modelo(sit, notas, cal, mat, universo, personal, cursada_cerrada=False):
    """Devuelve DataFrame de chequeos; main() falla si alguno es False."""
    r = []

    def chk(nombre, ok, detalle=""):
        r.append(dict(chequeo=nombre, ok=bool(ok), detalle=detalle))

    chk("situacion_estudiante única por id_estudiante+asignatura", not sit.duplicated(["id_estudiante", "asignatura"]).any(),
        f"{len(sit)} filas")
    chk("los merges no multiplican filas (situación = universo)", len(sit) == len(universo),
        f"universo={len(universo)} situación={len(sit)}")
    chk("notas_finales única por id_estudiante+asignatura", not notas.duplicated(["id_estudiante", "asignatura"]).any())
    chk("matrícula vigente única por id_estudiante+asignatura", not mat.duplicated(["id_estudiante", "asignatura"]).any())
    fuera = ((cal["puntos"] < 0) | (cal["puntos"] > cal["maximo"]) | (cal["nota_100"] < 0) | (cal["nota_100"] > 100)).sum()
    chk("notas dentro del rango válido (0..máximo)", fuera == 0, f"{fuera} fuera de rango")
    sin = sit["instrumentos_rendidos"].fillna(0) == 0
    chk("'Sin notas' no termina como Libre/Regular/Promociona",
        (sit.loc[sin, ["estado_provisorio", "estado_definitivo"]] == "Sin notas").all().all(),
        f"{int(sin.sum())} alumnos sin notas")
    if not cursada_cerrada:
        # la estimación (proyección / promedio con faltantes) nunca define un estado definitivo
        legit = (sit["asignatura"] == "Álgebra") & (sit["puntos_acumulados"] >= REGLAS["Álgebra"]["promociona"])
        mal = ~sit["estado_definitivo"].isin(["Promociona", "Pendiente", "Sin notas"]) | \
              ((sit["estado_definitivo"] == "Promociona") & ~legit)
        chk("con la cursada abierta no hay Regular/Libre definitivos ni Promociona sin puntos reales suficientes",
            not mal.any(), f"{int(mal.sum())} casos")
    ids_personal = set(zip(personal["id_estudiante"], personal["asignatura"])) if len(personal) else set()
    ids_mat = set(zip(mat["id_estudiante"], mat["asignatura"]))
    chk("el personal excluido no incluye alumnos matriculados", not (ids_personal & ids_mat),
        f"{len(ids_personal & ids_mat)} coincidencias")
    # informativos (siempre OK): casos que las alertas del dashboard de matrícula deben cubrir
    n1 = int((sit["situacion_matricula"] == "Matriculado sin participación").sum())
    n2 = int((sit["situacion_matricula"] == "NO matriculado con actividad").sum())
    chk("[informativo] matriculados sin participación", True, f"{n1}")
    chk("[informativo] actividad sin matrícula", True, f"{n2}")
    return pd.DataFrame(r)


# =====================================================================================
# 8) ORQUESTACIÓN
# =====================================================================================
def ejecutar(raiz, salida, recuperatorio=None, cursada_cerrada=None):
    recuperatorio = recuperatorio or RECUPERATORIO_MODO
    reiniciar_registro()
    os.makedirs(salida, exist_ok=True)
    archivos = encontrar_archivos(raiz)
    movs, mats, pars, trazs, cals, personal = [], [], [], [], [], []

    for asig in ASIGNATURAS:
        f = archivos[asig]
        print(f"[{asig}] leyendo...")
        vig, mov = resolver_matricula(leer_matricula(f["matricula"], asig), asig)
        mats.append(vig); movs.append(mov)

        alumnos, pers = procesar_participacion(leer_participacion(f["participacion"], asig), asig)
        pars.append(alumnos); personal.append(pers)

        tr, n_leidas = leer_trazabilidad(f["trazabilidad"], asig)
        tr_alumnos, tr_pers = separar_alumnos_personal(tr, "trazabilidad", asig)
        n_desc = n_leidas - len(tr)
        registrar("trazabilidad", asig, "Balance de filas", 0,
                  f"{n_leidas} leídas = {len(tr_alumnos)} alumnos + {len(tr_pers)} personal + {n_desc} descartadas",
                  n_leidas, len(tr_alumnos))
        assert n_leidas == len(tr_alumnos) + len(tr_pers) + n_desc, "balance de trazabilidad inconsistente"
        trazs.append(tr_alumnos); personal.append(tr_pers)

        for archivo in f["calificaciones"]:
            cals.append(leer_calificaciones(archivo, asig))

    mat = pd.concat(mats, ignore_index=True)
    movimientos = pd.concat(movs, ignore_index=True)
    par = pd.concat(pars, ignore_index=True)
    tra = pd.concat(trazs, ignore_index=True)
    pers = pd.concat(personal, ignore_index=True)
    cal = aplicar_recuperatorios(pd.concat(cals, ignore_index=True), recuperatorio)

    universo = pd.concat([mat[["id_estudiante", "asignatura"]], par[["id_estudiante", "asignatura"]],
                          cal[["id_estudiante", "asignatura"]], tra[["id_estudiante", "asignatura"]]]
                         ).drop_duplicates().reset_index(drop=True)
    notas = calcular_notas_finales(cal, universo, cursada_cerrada)
    eventos = tra.groupby(["id_estudiante", "asignatura"]).agg(
        eventos_trazabilidad=("fecha", "size"),
        eventos_repetidos_potenciales=("duplicado_potencial", "sum"),
        dias_activos=("fecha_dia", "nunique"),
        primer_evento=("fecha", "min"), ultimo_evento=("fecha", "max")).reset_index()
    sit = construir_situacion(universo, mat, par, eventos, notas)

    for (asig, sm), n in sit.groupby(["asignatura", "situacion_matricula"]).size().items():
        registrar("modelo", asig, f"Situación de matrícula: {sm}", n, "Se conservan y se marcan")
    validaciones = validar_modelo(sit, notas, cal, mat, universo, pers,
                                  CURSADA_CERRADA if cursada_cerrada is None else cursada_cerrada)
    for _, v in validaciones.iterrows():
        registrar("validacion", "todas", v["chequeo"], 0 if v["ok"] else 1, ("OK " if v["ok"] else "FALLÓ ") + str(v["detalle"]))

    descartados = pd.concat(DESCARTADOS, ignore_index=True) if DESCARTADOS else pd.DataFrame(columns=["fuente", "asignatura", "motivo"])
    salidas = {"matricula": mat, "matricula_movimientos": movimientos, "participacion": par,
               "trazabilidad": tra, "calificaciones": cal, "notas_finales": notas,
               "situacion_estudiante": sit, "personal_excluido": pers, "descartados": descartados,
               "informe_calidad_datos": pd.DataFrame(LOG).astype({"filas_antes": "Int64", "filas_despues": "Int64"})}
    resumen = []
    for nombre, df in salidas.items():
        df.to_csv(os.path.join(salida, f"{nombre}.csv"), index=False, encoding="utf-8-sig")
        try:
            df.to_parquet(os.path.join(salida, f"{nombre}.parquet"), index=False)
        except Exception:
            pass  # sin pyarrow se generan solo los CSV
        resumen.append((nombre, len(df)))
        print(f"   {nombre}: {len(df):,} filas")
    validaciones.to_csv(os.path.join(salida, "validaciones.csv"), index=False, encoding="utf-8-sig")

    print("\nValidaciones:")
    for _, v in validaciones.iterrows():
        print(f"   [{'OK' if v['ok'] else 'FALLÓ'}] {v['chequeo']} {('- ' + str(v['detalle'])) if v['detalle'] else ''}")
    if not validaciones["ok"].all():
        raise SystemExit("Hay validaciones que fallaron: revisar validaciones.csv antes de seguir.")
    print(f"\nListo. Archivos en: {os.path.abspath(salida)}")
    return salidas


def main(argv=None):
    ap = argparse.ArgumentParser(description="ETL 6.1 del TFI (LMS)")
    ap.add_argument("raw", help="carpeta con los Excel originales (p. ej. data/raw)")
    ap.add_argument("processed", help="carpeta de salida (p. ej. data/processed)")
    ap.add_argument("--recuperatorio", choices=["docente", "mayor_nota", "reemplaza", "aparte"],
                    default=RECUPERATORIO_MODO, help="cómo se trata el recuperatorio (por defecto, la regla del docente)")
    ap.add_argument("--cursada-cerrada", action="store_true",
                    help="habilita estados definitivos Regular/Libre (solo si la cursada terminó)")
    a = ap.parse_args(argv)
    try:
        ejecutar(a.raw, a.processed, a.recuperatorio, a.cursada_cerrada or None)
    except DatosError as e:
        sys.exit(f"ERROR en los datos de entrada: {e}")


if __name__ == "__main__":
    main()
