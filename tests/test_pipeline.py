"""Pruebas del orquestador sin depender de los 26 Excel reales."""
from pathlib import Path

import pandas as pd
import pytest

from src import pipeline


def _etl_falso(raw, output):
    output = Path(output)
    salida = {}
    for nombre in pipeline.TABLAS_ETL:
        if nombre == "situacion_estudiante":
            tabla = pd.DataFrame({"id_estudiante": ["S1"], "asignatura": ["Álgebra"],
                                  "matriculado": [True]})
        else:
            tabla = pd.DataFrame({"valor": [1]})
        salida[nombre] = tabla
        tabla.to_csv(output / f"{nombre}.csv", index=False)
    pd.DataFrame({"chequeo": ["clave única"], "ok": [True]}).to_csv(
        output / "validaciones.csv", index=False
    )
    return salida


def _kpi_falso(entrada, salida):
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    tablas = {}
    for nombre in pipeline.TABLAS_KPI:
        if nombre == "kpi_relacion_estudiante":
            tabla = pd.DataFrame({"id_estudiante": ["S1"], "asignatura": ["Álgebra"]})
        elif nombre == "kpi_resumen_asignatura":
            tabla = pd.DataFrame({"asignatura": ["Álgebra"], "matriculados": [1]})
        elif nombre == "kpi_estados_a_la_fecha":
            tabla = pd.DataFrame({"asignatura": ["Álgebra"], "cantidad": [1]})
        else:
            tabla = pd.DataFrame({"valor": [1]})
        tablas[nombre] = tabla
        tabla.to_csv(salida / f"{nombre}.csv", index=False)
    return tablas


def _preparar(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "fuente.xlsx").write_bytes(b"simulada")
    procesados = tmp_path / "processed"
    procesados.mkdir()
    (procesados / "README.md").write_text("archivo versionado", encoding="utf-8")
    (procesados / "indicadores_anteriores.csv").write_text("viejo", encoding="utf-8")
    monkeypatch.setattr(pipeline.procesar_datos, "ejecutar", _etl_falso)
    monkeypatch.setattr(pipeline.kpi, "ejecutar", _kpi_falso)
    return raw, procesados


def test_publica_ambas_etapas_y_registra_ultima_carga(tmp_path, monkeypatch):
    raw, procesados = _preparar(tmp_path, monkeypatch)
    resultado = pipeline.actualizar(raw, procesados)
    assert resultado["estado"] == "correcto"
    assert resultado["fuentes_excel"] == 1
    assert len(resultado["tablas_etl"]) == 10
    assert len(resultado["tablas_kpi"]) == 11
    assert (procesados / "situacion_estudiante.csv").exists()
    assert (procesados / "kpi" / "kpi_relacion_estudiante.csv").exists()
    assert (procesados / "README.md").read_text(encoding="utf-8") == "archivo versionado"
    assert not (procesados / "indicadores_anteriores.csv").exists()
    assert pipeline.leer_estado(procesados) == resultado
    assert not (tmp_path / ".pipeline.lock").exists()


def test_error_kpi_mantiene_publicacion_anterior(tmp_path, monkeypatch):
    raw, procesados = _preparar(tmp_path, monkeypatch)
    def falla(*args):
        raise RuntimeError("Error de KPI simulado")
    monkeypatch.setattr(pipeline.kpi, "ejecutar", falla)
    with pytest.raises(RuntimeError, match="simulado"):
        pipeline.actualizar(raw, procesados)
    assert (procesados / "indicadores_anteriores.csv").read_text() == "viejo"
    assert (procesados / "README.md").exists()
    assert pipeline.leer_estado(procesados) is None
    assert not (tmp_path / ".pipeline.lock").exists()
    assert not list(tmp_path.glob(".pipeline-stage-*"))


def test_validacion_etl_fallida_no_publica(tmp_path, monkeypatch):
    raw, procesados = _preparar(tmp_path, monkeypatch)
    def etl_con_error(r, out):
        tablas = _etl_falso(r, out)
        pd.DataFrame({"chequeo": ["integridad"], "ok": [False]}).to_csv(
            Path(out) / "validaciones.csv", index=False
        )
        return tablas
    monkeypatch.setattr(pipeline.procesar_datos, "ejecutar", etl_con_error)
    with pytest.raises(ValueError, match="validaciones"):
        pipeline.actualizar(raw, procesados)
    assert (procesados / "indicadores_anteriores.csv").exists()
    assert not (tmp_path / ".pipeline.lock").exists()


def test_bloqueo_impide_actualizaciones_concurrentes(tmp_path, monkeypatch):
    raw, procesados = _preparar(tmp_path, monkeypatch)
    (tmp_path / ".pipeline.lock").write_text("en ejecución")
    with pytest.raises(RuntimeError, match="actualización en ejecución"):
        pipeline.actualizar(raw, procesados)
    assert (procesados / "indicadores_anteriores.csv").exists()


def test_faltan_fuentes(tmp_path):
    with pytest.raises(FileNotFoundError, match="fuentes"):
        pipeline.actualizar(tmp_path / "no-existe", tmp_path / "processed")
