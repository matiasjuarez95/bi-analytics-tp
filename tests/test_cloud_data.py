"""Pruebas de conexión de archivos: estructura real y validaciones de seguridad del ZIP."""
import io
import zipfile
from pathlib import Path

import pytest

from src.cloud_data import _extraer_seguro, _raiz_excel, fuentes_disponibles


def _zip(path, items):
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in items.items():
            zf.writestr(name, content)


def test_extraer_y_encontrar_carpetas_esperadas(tmp_path):
    archivo = tmp_path / "fuentes.zip"
    _zip(archivo, {
        "Datos_LMS_Anonimizados/Matriculados/Algebra.xlsx": "excel",
        "Datos_LMS_Anonimizados/Álgebra/reporte_trazabilidad.xlsx": "excel",
        "Datos_LMS_Anonimizados/Probabilidad y Estadística/reporte_participacion.xlsx": "excel",
        "Datos_LMS_Anonimizados/Algoritmos y Estructuras de Datos/reporte_participacion.xlsx": "excel",
    })
    destino = tmp_path / "extraido"
    destino.mkdir()
    _extraer_seguro(archivo, destino)
    raiz = _raiz_excel(destino)
    assert raiz.name == "Datos_LMS_Anonimizados"
    assert (raiz / "Matriculados" / "Algebra.xlsx").is_file()


def test_zip_no_admite_escape_de_directorio(tmp_path):
    archivo = tmp_path / "fuentes.zip"
    _zip(archivo, {"../archivo.xlsx": "fuera"})
    destino = tmp_path / "extraido"
    destino.mkdir()
    with pytest.raises(ValueError, match="Ruta"):
        _extraer_seguro(archivo, destino)
    assert not (tmp_path / "archivo.xlsx").exists()


def test_sin_secrets_no_intenta_acceder_drive():
    class SinSecrets:
        def __contains__(self, key):
            raise FileNotFoundError("No hay secrets.toml")
    assert fuentes_disponibles(SinSecrets()) is False


def test_secretos_completos():
    assert fuentes_disponibles({"gcp_service_account": {"type": "service_account"},
                                "drive_zip_file_id": "ID"}) is True
