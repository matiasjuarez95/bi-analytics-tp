"""Obtención privada de las fuentes reales y ejecución del pipeline en la nube.

La fuente es el ZIP del trabajo práctico alojado en Google Drive.
Las credenciales se cargan en Streamlit Secrets y nunca se guardan en Git.
"""
from __future__ import annotations

import shutil
import stat
import tempfile
import unicodedata
import zipfile
from pathlib import Path

from src.pipeline import actualizar

MAX_FILES = 200
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024


def _normalizar(nombre: str) -> str:
    s = unicodedata.normalize("NFKD", nombre).casefold()
    return "".join(c for c in s if not unicodedata.combining(c))


def _extraer_seguro(archivo: Path, destino: Path) -> None:
    """Extrae solo archivos y directorios normales dentro del destino."""
    destino = destino.resolve()
    with zipfile.ZipFile(archivo) as zf:
        entradas = zf.infolist()
        if len(entradas) > MAX_FILES:
            raise ValueError("ZIP con demasiados archivos")
        if sum(x.file_size for x in entradas) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("ZIP supera el límite permitido de datos descomprimidos")
        for info in entradas:
            modo = info.external_attr >> 16
            if stat.S_ISLNK(modo):
                raise ValueError("El ZIP contiene un enlace simbólico")
            nombre = info.filename.replace("\\", "/")
            if not nombre or nombre.startswith("/") or ".." in Path(nombre).parts:
                raise ValueError("Ruta no permitida en el ZIP")
            salida = (destino / nombre).resolve()
            if not salida.is_relative_to(destino):
                raise ValueError("Ruta fuera de la carpeta de destino")
            if info.is_dir():
                salida.mkdir(parents=True, exist_ok=True)
            elif salida.suffix.lower() in {".xlsx", ".xls", ".xlsm"}:
                salida.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as origen, salida.open("wb") as objetivo:
                    shutil.copyfileobj(origen, objetivo)


def _raiz_excel(extraidos: Path) -> Path:
    """Busca la carpeta que contiene Matriculados y las tres asignaturas."""
    candidatos = [extraidos, *(x for x in extraidos.rglob("*") if x.is_dir())]
    for candidato in candidatos:
        subcarpetas = {_normalizar(x.name) for x in candidato.iterdir() if x.is_dir()}
        if (any("matriculad" in x for x in subcarpetas)
            and any("algebra" in x for x in subcarpetas)
            and any("probabilidad" in x for x in subcarpetas)
            and any("algoritmo" in x for x in subcarpetas)):
            return candidato
    raise ValueError("El ZIP no contiene la estructura de materias esperada por el ETL")


def descargar_zip_drive(archivo: Path, credenciales: dict, file_id: str) -> None:
    """Descarga el ZIP real de Drive mediante una cuenta de servicio autorizada."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    info = dict(credenciales)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    request = service.files().get_media(fileId=file_id)
    with archivo.open("wb") as f:
        downloader = MediaIoBaseDownload(f, request, chunksize=1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def actualizar_desde_drive(
    processed: str | Path, credenciales: dict, file_id: str
) -> dict:
    """Descarga fuentes reales en un directorio temporal y ejecuta ETL + KPI."""
    if not file_id:
        raise ValueError("Falta la identificación del ZIP de Google Drive")
    with tempfile.TemporaryDirectory(prefix="tfi-lms-drive-") as temporal:
        raiz = Path(temporal)
        zip_path = raiz / "fuentes.zip"
        descargar_zip_drive(zip_path, credenciales, file_id)
        extraidos = raiz / "excel"
        extraidos.mkdir()
        _extraer_seguro(zip_path, extraidos)
        carpeta_raw = _raiz_excel(extraidos)
        return actualizar(carpeta_raw, processed)


def fuentes_disponibles(secrets) -> bool:
    """Detecta si Streamlit Secrets contiene credenciales reales de Drive."""
    try:
        return "gcp_service_account" in secrets and "drive_zip_file_id" in secrets
    except FileNotFoundError:
        return False
