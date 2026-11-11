# -*- coding: utf-8 -*-
"""KPI 6.2 del TFI BI&A. Consume salidas del ETL 6.1; no relee los Excel.

Unidad de análisis: (id_estudiante, asignatura). Rendimiento y participación:
solo matrícula vigente, salvo alertas de actividad sin matrícula.
Los estados académicos se interpretan A LA FECHA (cursada abierta).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

CLAVE = ["id_estudiante", "asignatura"]
ESTADOS = ["Promociona", "Regular", "Libre", "Sin notas"]
TIPOS = ["Acceso/navegación", "Lectura de materiales", "Evaluaciones",
         "Comunicación/foros", "Calificaciones", "Otros"]


def _requerir(df: pd.DataFrame, cols: list[str], nombre: str) -> None:
    faltan = sorted(set(cols) - set(df.columns))
    if faltan:
        raise ValueError(f"{nombre}: faltan columnas {faltan}")


def _tasa(num: int, den: int) -> float:
    return round(100 * num / den, 2) if den else float("nan")


def _correlacion(x: pd.Series, y: pd.Series) -> float:
    par = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"),
                        "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if len(par) < 3 or par["x"].nunique() < 2 or par["y"].nunique() < 2:
        return float("nan")
    return round(float(par["x"].corr(par["y"])), 4)


def calcular_kpis(situacion: pd.DataFrame, trazabilidad: pd.DataFrame,
                  calificaciones: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Devuelve tablas para dashboards, sin exportar información nominal."""
    _requerir(situacion, CLAVE + ["matriculado", "tiene_actividad", "estado_provisorio",
             "nota_a_la_fecha", "escala_nota_a_la_fecha", "tiempo_uso_min",
             "interacciones", "situacion_matricula", "eventos_trazabilidad"], "situacion")
    _requerir(trazabilidad, CLAVE + ["fecha", "tipo_interaccion"], "trazabilidad")
    _requerir(calificaciones, CLAVE + ["instrumento", "nota_100"], "calificaciones")
    if situacion.duplicated(CLAVE).any():
        raise ValueError("situacion: duplicados en la clave estudiante+asignatura")

    s = situacion.copy()
    s["matriculado"] = s["matriculado"].eq(True)
    s["tiene_actividad"] = s["tiene_actividad"].eq(True)
    for col in ("nota_a_la_fecha", "escala_nota_a_la_fecha", "tiempo_uso_min",
                "interacciones", "eventos_trazabilidad"):
        s[col] = pd.to_numeric(s[col], errors="coerce")
    s["nota_pct"] = 100 * s["nota_a_la_fecha"] / s["escala_nota_a_la_fecha"]
    s.loc[(s["escala_nota_a_la_fecha"] <= 0), "nota_pct"] = np.nan
    mat = s.loc[s["matriculado"]].copy()
    grupos = sorted(s["asignatura"].dropna().unique())

    resumen, estados, alertas, hist, cruce = [], [], [], [], []
    for asig in grupos:
        universo = s[s["asignatura"] == asig]
        m = mat[mat["asignatura"] == asig]
        n = len(m)
        activos = int(m["tiene_actividad"].sum())
        con_notas = m["nota_pct"].notna()
        notas_validas = m.loc[con_notas, "nota_pct"]
        eventos = pd.to_numeric(m["eventos_trazabilidad"], errors="coerce")
        resumen.append({
            "asignatura": asig, "matriculados": n,
            "activos": activos, "inactivos": n - activos,
            "activos_pct": _tasa(activos, n), "inactivos_pct": _tasa(n - activos, n),
            "cobertura_participacion_pct": _tasa(activos, n),
            "interacciones_lms_promedio_por_matriculado": m["interacciones"].fillna(0).mean() if n else np.nan,
            "tiempo_uso_promedio_min_por_matriculado": m["tiempo_uso_min"].fillna(0).mean() if n else np.nan,
            "eventos_trazabilidad_promedio_por_matriculado": eventos.fillna(0).mean() if n else np.nan,
            "con_notas": int(con_notas.sum()),
            "promedio_nota_pct_solo_con_notas": notas_validas.mean(),
            "correlacion_tiempo_nota": _correlacion(m["tiempo_uso_min"], m["nota_pct"]),
            "correlacion_interacciones_nota": _correlacion(m["interacciones"], m["nota_pct"]),
            "correlacion_eventos_nota": _correlacion(m["eventos_trazabilidad"], m["nota_pct"]),
        })
        for estado in ESTADOS:
            cantidad = int(m["estado_provisorio"].eq(estado).sum())
            estados.append({"asignatura": asig, "estado_a_la_fecha": estado,
                            "cantidad": cantidad, "porcentaje_sobre_matriculados": _tasa(cantidad, n)})
        sin_act = universo["situacion_matricula"].eq("Matriculado sin participación")
        act_no_mat = universo["situacion_matricula"].eq("NO matriculado con actividad")
        alertas.extend([
            {"asignatura": asig, "alerta": "Matriculado sin participación", "cantidad": int(sin_act.sum())},
            {"asignatura": asig, "alerta": "No matriculado con actividad", "cantidad": int(act_no_mat.sum())},
        ])
        # Histograma de porcentaje de nota; 'Sin notas' se visualiza separadamente en estados.
        bins = pd.cut(notas_validas.clip(lower=0, upper=100), bins=[0,20,40,60,80,100],
                      labels=["0-20", "20-40", "40-60", "60-80", "80-100"],
                      include_lowest=True)
        for banda in bins.cat.categories:
            hist.append({"asignatura": asig, "rango_nota_pct": str(banda),
                         "cantidad": int(bins.eq(banda).sum())})
        # Este dataset se usa para scatter, sin nombres. IDs internos permiten selección individual.
        cruce.append(m[CLAVE + ["nota_pct", "estado_provisorio", "tiempo_uso_min",
                                "interacciones", "eventos_trazabilidad", "tiene_actividad"]]
                     .rename(columns={"estado_provisorio": "estado_a_la_fecha"}))

    tr = trazabilidad.copy()
    tr["fecha"] = pd.to_datetime(tr["fecha"], errors="coerce")
    if tr["fecha"].isna().any():
        raise ValueError("trazabilidad: fechas inválidas")
    # Únicamente eventos de matriculados vigentes (match de ambas claves).
    tr = tr.merge(mat[CLAVE], on=CLAVE, how="inner", validate="many_to_one")
    tr["dia"] = tr["fecha"].dt.normalize()
    tr["semana_inicio"] = tr["dia"] - pd.to_timedelta(tr["dia"].dt.dayofweek, unit="D")
    tr["mes"] = tr["fecha"].dt.to_period("M").astype(str)
    tr["hora"] = tr["fecha"].dt.hour
    tr["dia_semana"] = tr["fecha"].dt.dayofweek
    por_tipo = tr.groupby(["asignatura", "tipo_interaccion"]).size().rename("eventos").reset_index()
    diario = tr.groupby(["asignatura", "dia"]).agg(eventos=("id_estudiante", "size"),
                  estudiantes_activos=("id_estudiante", "nunique")).reset_index()
    semanal = tr.groupby(["asignatura", "semana_inicio"]).agg(eventos=("id_estudiante", "size"),
                  estudiantes_activos=("id_estudiante", "nunique")).reset_index()
    mensual = tr.groupby(["asignatura", "mes"]).agg(eventos=("id_estudiante", "size"),
                  estudiantes_activos=("id_estudiante", "nunique")).reset_index()
    mapa = tr.groupby(["asignatura", "dia_semana", "hora"]).size().rename("eventos").reset_index()

    # Instrumentos: solo calificaciones efectivamente utilizadas en la nota y matriculados.
    cal = calificaciones.merge(mat[CLAVE], on=CLAVE, how="inner", validate="many_to_one")
    if "usa_en_nota_final" in cal.columns:
        cal = cal[cal["usa_en_nota_final"].eq(True)]
    instrumentos = cal.groupby(["asignatura", "instrumento"]).agg(
        cantidad_notas=("nota_100", "count"), promedio_nota_100=("nota_100", "mean")
    ).reset_index()

    salidas = {
        "kpi_resumen_asignatura": pd.DataFrame(resumen).round(3),
        "kpi_estados_a_la_fecha": pd.DataFrame(estados),
        "kpi_alertas_matricula": pd.DataFrame(alertas),
        "kpi_histograma_notas": pd.DataFrame(hist),
        "kpi_relacion_estudiante": pd.concat(cruce, ignore_index=True),
        "kpi_interacciones_tipo": por_tipo,
        "kpi_actividad_diaria": diario,
        "kpi_actividad_semanal": semanal,
        "kpi_actividad_mensual": mensual,
        "kpi_mapa_calor": mapa,
        "kpi_notas_instrumento": instrumentos,
    }
    for nombre, tabla in salidas.items():
        if len(tabla) and tabla.isna().all(axis=1).any():
            raise ValueError(f"{nombre}: fila completamente vacía")
    return salidas


def ejecutar(entrada: str | Path, salida: str | Path) -> dict[str, pd.DataFrame]:
    entrada, salida = Path(entrada), Path(salida)
    datos = {}
    for nombre in ("situacion_estudiante", "trazabilidad", "calificaciones"):
        archivo = entrada / f"{nombre}.csv"
        if not archivo.is_file():
            raise FileNotFoundError(f"Falta {archivo}; ejecutar ETL 6.1 primero")
        datos[nombre] = pd.read_csv(archivo, low_memory=False)
    tablas = calcular_kpis(datos["situacion_estudiante"], datos["trazabilidad"], datos["calificaciones"])
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, tabla in tablas.items():
        tabla.to_csv(salida / f"{nombre}.csv", index=False, encoding="utf-8-sig")
        print(f"{nombre}: {len(tabla)} filas")
    return tablas


def main() -> None:
    parser = argparse.ArgumentParser(description="Paso 6.2: KPI del LMS")
    parser.add_argument("entrada", help="Directorio de salidas CSV del ETL 6.1")
    parser.add_argument("salida", help="Directorio donde escribir tablas de KPI")
    args = parser.parse_args()
    ejecutar(args.entrada, args.salida)


if __name__ == "__main__":
    main()
