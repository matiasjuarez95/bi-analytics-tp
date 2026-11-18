"""Validación de la fecha de corte en dashboards/app_TFI.py.

Usa el AppTest de Streamlit para ejecutar la app sin navegador.
Requiere los datos procesados en data/processed/ (si no están, se saltea).

    python -m pytest tests/test_app_fecha_corte.py -q
"""
import datetime as dt
import json
import shutil
from pathlib import Path

import base64

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[1]
APP = RAIZ / "dashboards" / "app_TFI.py"
PROC = RAIZ / "data" / "processed"

pytestmark = pytest.mark.skipif(
    not (PROC / "trazabilidad.csv").is_file() or not (PROC / "kpi").is_dir(),
    reason="Faltan los datos procesados (correr el ETL y los KPI primero).")

st_testing = pytest.importorskip("streamlit.testing.v1")


def correr(app=APP, fecha=None, materias=None):
    at = st_testing.AppTest.from_file(str(app), default_timeout=180).run()
    if materias is not None:
        at.multiselect[0].set_value(materias).run()
    if fecha is not None:
        at.date_input[0].set_value(fecha).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def grafico(at, titulo):
    """Devuelve los datos de un gráfico Plotly de la app buscándolo por su título."""
    for el in at.get("plotly_chart"):
        fig = json.loads(el.proto.spec)
        if titulo in fig["layout"].get("title", {}).get("text", ""):
            return fig
    raise AssertionError(f"No se encontró el gráfico «{titulo}»")


def valores(eje):
    """Lista de valores de un eje Plotly (Plotly 6 puede guardarlos en binario)."""
    if isinstance(eje, dict) and "bdata" in eje:
        return np.frombuffer(base64.b64decode(eje["bdata"]), dtype=eje["dtype"]).tolist()
    return list(eje)


def eventos_esperados(desde, hasta):
    """Eventos de matriculados entre dos fechas (inclusive), calculados aparte de la app."""
    t = pd.read_csv(PROC / "trazabilidad.csv", usecols=["fecha", "id_estudiante", "asignatura"],
                    low_memory=False)
    t["fecha"] = pd.to_datetime(t["fecha"], errors="coerce")
    mat = pd.read_csv(PROC / "kpi" / "kpi_relacion_estudiante.csv")[["id_estudiante", "asignatura"]]
    t = t.merge(mat.drop_duplicates(), on=["id_estudiante", "asignatura"])
    dia = t["fecha"].dt.date
    return t[(dia >= desde) & (dia <= hasta)].groupby("asignatura").size().to_dict()


def test_corte_en_ultimo_dia_coincide_con_kpi():
    """Con el corte en el último día, la serie semanal es igual a kpi_actividad_semanal."""
    at = correr()
    fig = grafico(at, "Actividad semanal")
    total_app = sum(sum(valores(tr["y"])) for tr in fig["data"])
    kpi = pd.read_csv(PROC / "kpi" / "kpi_actividad_semanal.csv")
    assert total_app == kpi["eventos"].sum()


def test_corte_a_mitad_de_semana_no_incluye_dias_posteriores():
    """Corte un miércoles: la última semana solo suma lunes a miércoles."""
    miercoles = dt.date(2025, 9, 17)
    lunes = miercoles - dt.timedelta(days=2)
    at = correr(fecha=miercoles)
    fig = grafico(at, "Actividad semanal")
    esperado = eventos_esperados(lunes, miercoles)
    for tr in fig["data"]:
        ultima_semana = valores(tr["y"])[-1]
        assert ultima_semana == esperado[tr["name"]], tr["name"]
    # La semana completa (de kpi_actividad_semanal) tiene más eventos que lo graficado.
    semana_completa = eventos_esperados(lunes, lunes + dt.timedelta(days=6))
    assert all(semana_completa[a] > esperado[a] for a in esperado)


def test_corte_en_primer_dia_no_rompe_el_rango():
    """Con un solo día de datos no se dibuja el slider (evita min == max)."""
    at = correr(fecha=dt.date(2025, 8, 5))
    assert len(at.slider) == 0
    assert any("un solo día" in c.value for c in at.caption)


def test_materia_sin_actividad_hasta_el_corte(tmp_path):
    """Si la materia elegida empieza después del corte, se muestra un aviso y no falla.

    Con los datos reales todas las materias arrancan el 05/08, así que se arma una copia
    donde la actividad de Álgebra empieza 30 días más tarde.
    """
    copia = tmp_path / "repo"
    shutil.copytree(RAIZ / "dashboards", copia / "dashboards")
    shutil.copytree(PROC, copia / "data" / "processed")
    desplazar = pd.Timedelta(days=30)
    traz = pd.read_csv(copia / "data/processed/trazabilidad.csv", low_memory=False)
    traz["fecha"] = pd.to_datetime(traz["fecha"], errors="coerce")
    traz.loc[traz["asignatura"] == "Álgebra", "fecha"] += desplazar
    traz.to_csv(copia / "data/processed/trazabilidad.csv", index=False)
    diaria = pd.read_csv(copia / "data/processed/kpi/kpi_actividad_diaria.csv")
    diaria["dia"] = pd.to_datetime(diaria["dia"])
    diaria.loc[diaria["asignatura"] == "Álgebra", "dia"] += desplazar
    diaria.to_csv(copia / "data/processed/kpi/kpi_actividad_diaria.csv", index=False)

    at = correr(app=copia / "dashboards" / "app_TFI.py",
                materias=["Álgebra"], fecha=dt.date(2025, 8, 20))
    avisos = [i.value for i in at.info]
    assert any("No hay actividad en el período" in a for a in avisos)
    assert any("No hay actividad registrada hasta la fecha de corte" in a for a in avisos)
