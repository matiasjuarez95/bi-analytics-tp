# -*- coding: utf-8 -*-
"""Orquestador local del TFI: ETL 6.1 -> validaciones -> KPI 6.2.

Todos los resultados se producen en una carpeta temporal. La versión publicada en
data/processed solo se reemplaza si ambos pasos terminaron correctamente.
No ejecuta el pipeline al abrir un dashboard; la actualización es explícita.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.etl import procesar_datos
from src import kpi

TABLAS_ETL = (
    "matricula", "matricula_movimientos", "participacion", "trazabilidad",
    "calificaciones", "notas_finales", "situacion_estudiante",
    "personal_excluido", "descartados", "informe_calidad_datos",
)
TABLAS_KPI = (
    "kpi_resumen_asignatura", "kpi_estados_a_la_fecha", "kpi_alertas_matricula",
    "kpi_histograma_notas", "kpi_relacion_estudiante", "kpi_interacciones_tipo",
    "kpi_actividad_diaria", "kpi_actividad_semanal", "kpi_actividad_mensual",
    "kpi_mapa_calor", "kpi_notas_instrumento",
)
METADATA = "ultima_actualizacion.json"


@contextmanager
def _bloquear(ruta: Path):
    """Evita dos actualizaciones simultáneas en una misma carpeta de datos."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(ruta), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(
            "Ya hay una actualización en ejecución. "
            f"Si no es así, revisá el archivo de bloqueo: {ruta}"
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"pid={os.getpid()}\\n")
        yield
    finally:
        ruta.unlink(missing_ok=True)


def _validar_etl(tablas: dict, carpeta: Path) -> None:
    faltan = [x for x in TABLAS_ETL if x not in tablas or not (carpeta / f"{x}.csv").is_file()]
    if faltan:
        raise ValueError(f"ETL incompleto: {faltan}")
    ruta = carpeta / "validaciones.csv"
    if not ruta.is_file():
        raise ValueError("ETL no generó validaciones.csv")
    v = pd.read_csv(ruta)
    if "ok" not in v.columns or v.empty or not v["ok"].astype(str).str.lower().eq("true").all():
        raise ValueError("Fallaron las validaciones del ETL; no se publicarán los nuevos datos")


def _validar_kpi(tablas: dict, carpeta: Path, etl: dict) -> None:
    faltan = [x for x in TABLAS_KPI if x not in tablas or not (carpeta / "kpi" / f"{x}.csv").is_file()]
    if faltan:
        raise ValueError(f"KPI incompletos: {faltan}")
    base = etl["situacion_estudiante"]
    total_matriculados = int(base["matriculado"].eq(True).sum())
    relacion = tablas["kpi_relacion_estudiante"]
    resumen = tablas["kpi_resumen_asignatura"]
    estados = tablas["kpi_estados_a_la_fecha"]
    if (len(relacion) != total_matriculados
            or relacion.duplicated(["id_estudiante", "asignatura"]).any()
            or int(resumen["matriculados"].sum()) != total_matriculados
            or int(estados["cantidad"].sum()) != total_matriculados):
        raise ValueError("KPI inconsistentes con el universo de matrícula vigente")


def leer_estado(procesados: str | Path) -> dict | None:
    """Lee la última publicación exitosa; nunca contiene nombres de estudiantes."""
    archivo = Path(procesados) / METADATA
    if not archivo.is_file():
        return None
    try:
        with archivo.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def actualizar(raw: str | Path = "data/raw",
               processed: str | Path = "data/processed") -> dict:
    """Procesa fuentes y publica los resultados únicamente si todo sale bien.

    Usa un staging en el mismo volumen para sustituir la carpeta completa.
    Ante error de ETL/KPI, conserva la versión anterior sin alteraciones.
    Diseñado para una instalación local con un único administrador.
    """
    raw, destino = Path(raw).resolve(), Path(processed).resolve()
    if not raw.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de fuentes: {raw}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    lock = destino.parent / ".pipeline.lock"
    with _bloquear(lock):
        stage = Path(tempfile.mkdtemp(prefix=".pipeline-stage-", dir=destino.parent))
        backup = destino.parent / f".pipeline-backup-{uuid.uuid4().hex}"
        respaldo_creado = False
        try:
            tablas_etl = procesar_datos.ejecutar(str(raw), str(stage))
            _validar_etl(tablas_etl, stage)
            tablas_kpi = kpi.ejecutar(stage, stage / "kpi")
            _validar_kpi(tablas_kpi, stage, tablas_etl)
            datos = {
                "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "estado": "correcto",
                "tablas_etl": {k: len(v) for k, v in tablas_etl.items()},
                "tablas_kpi": {k: len(v) for k, v in tablas_kpi.items()},
                "validaciones_etl": "aprobadas",
                "fuentes_excel": len([p for p in raw.rglob("*") if p.suffix.lower() in {".xlsx", ".xls", ".xlsm"}]),
            }
            (stage / METADATA).write_text(
                json.dumps(datos, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8"
            )
            # El README está versionado en Git y no debe desaparecer durante el cambio.
            readme = destino / "README.md"
            if readme.is_file():
                shutil.copy2(readme, stage / "README.md")
            if destino.exists():
                os.replace(destino, backup)
                respaldo_creado = True
            try:
                os.replace(stage, destino)
            except BaseException:
                if respaldo_creado:
                    os.replace(backup, destino)
                    respaldo_creado = False
                raise
            if respaldo_creado:
                shutil.rmtree(backup)
            return datos
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline integrado del TFI BI&A")
    parser.add_argument("--raw", default="data/raw", help="Carpeta de Excel originales")
    parser.add_argument("--processed", default="data/processed", help="Salida de ETL y KPI")
    args = parser.parse_args()
    print(json.dumps(actualizar(args.raw, args.processed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
