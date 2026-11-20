"""Datos ficticios reproducibles para presentar los dashboards sin fuentes externas.

No reproduce las cifras de los Excel académicos: genera una cohorte ilustrativa
y calcula las tablas con el mismo módulo KPI utilizado en el proyecto.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.kpi import calcular_kpis

MARCADOR = "datos_demostracion.json"
ASIGNATURAS = ("Álgebra", "Algoritmos", "Probabilidad")
TIPOS = (
    "Acceso/navegación", "Lectura de materiales", "Evaluaciones",
    "Comunicación/foros", "Calificaciones", "Otros",
)


def es_demo(carpeta: str | Path) -> bool:
    return (Path(carpeta) / MARCADOR).is_file()


def generar_demo(carpeta: str | Path, *, alumnos_por_materia: int = 80) -> dict[str, int]:
    """Crea la foto de datos y tablas KPI con IDs ficticios; resultado determinista."""
    if alumnos_por_materia < 4:
        raise ValueError("Se necesitan al menos cuatro alumnos por materia")
    destino = Path(carpeta)
    destino.mkdir(parents=True, exist_ok=True)
    kpi_dir = destino / "kpi"
    kpi_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20251120)

    situaciones, eventos, notas = [], [], []
    inicio = pd.Timestamp("2025-08-05")
    # Fecha final consistente con los textos de la app académica.
    for j, materia in enumerate(ASIGNATURAS):
        for i in range(alumnos_por_materia):
            estudiante = f"DEMO-{j+1:02d}-{i+1:04d}"
            # Mezcla reproducible de actividad reciente, antigua y ausencia.
            grupo_actividad = i % 10
            if grupo_actividad == 0:
                fechas = []
            else:
                cantidad = int(rng.integers(8, 46))
                max_dia = 81 if grupo_actividad >= 4 else 40
                desplazamientos = rng.integers(0, max_dia, size=cantidad)
                fechas = [inicio + pd.Timedelta(days=int(d), hours=int(rng.integers(8, 23)),
                                             minutes=int(rng.integers(0, 60)))
                          for d in desplazamientos]

            interacciones = int(len(fechas) * rng.uniform(1.2, 2.6))
            minutos = round(float(len(fechas) * rng.uniform(3, 14)), 1)
            tiene_actividad = bool(fechas)
            # Variación realista entre participación y desempeño.
            rend = float(np.clip(28 + i % 5 * 9 + rng.normal(0, 15) + min(len(fechas), 40) * 0.5, 5, 98))
            tiene_nota = i % 11 != 0
            nota = round(rend, 2) if tiene_nota else np.nan
            estado = ("Sin notas" if not tiene_nota else
                      "Promociona" if nota >= 80 else "Regular" if nota >= 60 else "Libre")
            situaciones.append({
                "id_estudiante": estudiante, "asignatura": materia,
                "matriculado": True, "tiene_actividad": tiene_actividad,
                "estado_provisorio": estado, "nota_a_la_fecha": nota,
                "escala_nota_a_la_fecha": 100, "tiempo_uso_min": minutos,
                "interacciones": interacciones, "eventos_trazabilidad": len(fechas),
                "situacion_matricula": ("Matriculado con actividad" if tiene_actividad
                                       else "Matriculado sin participación"),
            })
            for fecha in fechas:
                tipo = str(rng.choice(TIPOS, p=[0.40, 0.24, 0.13, 0.10, 0.09, 0.04]))
                eventos.append({
                    "id_estudiante": estudiante, "asignatura": materia,
                    "fecha": fecha, "tipo_interaccion": tipo,
                })
            if tiene_nota:
                for instrumento in ("Parcial 1", "Trabajo práctico", "Parcial 2"):
                    notas.append({
                        "id_estudiante": estudiante, "asignatura": materia,
                        "instrumento": instrumento,
                        "nota_100": round(float(np.clip(rend + rng.normal(0, 8), 0, 100)), 2),
                        "usa_en_nota_final": True,
                    })

    situacion = pd.DataFrame(situaciones)
    trazabilidad = pd.DataFrame(eventos)
    calificaciones = pd.DataFrame(notas)
    for nombre, tabla in {
        "situacion_estudiante": situacion, "trazabilidad": trazabilidad,
        "calificaciones": calificaciones,
    }.items():
        tabla.to_csv(destino / f"{nombre}.csv", index=False, encoding="utf-8-sig")

    indicadores = calcular_kpis(situacion, trazabilidad, calificaciones)
    for nombre, tabla in indicadores.items():
        tabla.to_csv(kpi_dir / f"{nombre}.csv", index=False, encoding="utf-8-sig")
    resumen = {
        "alumnos_ficticios": len(situacion),
        "eventos_ficticios": len(trazabilidad),
        "calificaciones_ficticias": len(calificaciones),
        "tablas_kpi": len(indicadores),
    }
    (destino / MARCADOR).write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return resumen


def preparar_si_faltan_datos(carpeta: str | Path, raw: str | Path) -> bool:
    """Prepara datos de muestra únicamente en una instalación sin datos reales.

    Si existe una salida ETL parcial, o hay fuentes Excel locales, no la toca.
    """
    carpeta, raw = Path(carpeta), Path(raw)
    if (carpeta / "kpi" / "kpi_resumen_asignatura.csv").is_file():
        return es_demo(carpeta)
    if any(carpeta.glob("*.csv")):
        return False
    if raw.exists() and any(
        p.suffix.lower() in {".xlsx", ".xls", ".xlsm"} for p in raw.rglob("*")
    ):
        return False
    generar_demo(carpeta)
    return True
