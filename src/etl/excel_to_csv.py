"""Extrae las hojas de Excel originales a CSV sin alterar el contenido de origen.

Uso desde la raíz:
    python -m src.etl.excel_to_csv
    python -m src.etl.excel_to_csv --raw-dir data/raw --output-dir data/interim/csv

No aplica reglas de negocio ni limpieza. Los encabezados y tipos deben auditarse.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import unicodedata
import pandas as pd


def slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_") or "hoja"


def convert(raw_dir: Path, output_dir: Path) -> int:
    if not raw_dir.exists():
        raise FileNotFoundError(
            f"No existe {raw_dir}. Descargar primero los Excel originales desde Drive."
        )
    sources = sorted(
        f for f in raw_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in {".xlsx", ".xlsm"}
        and not f.name.startswith("~$")
    )
    if not sources:
        raise FileNotFoundError(
            f"No se encontraron archivos .xlsx/.xlsm en {raw_dir}."
        )

    count = 0
    for source in sources:
        relative = source.relative_to(raw_dir)
        target_dir = output_dir / relative.parent / relative.stem
        workbook = pd.ExcelFile(source, engine="openpyxl")
        for position, sheet in enumerate(workbook.sheet_names, start=1):
            df = pd.read_excel(workbook, sheet_name=sheet, dtype=object)
            target_dir.mkdir(parents=True, exist_ok=True)
            csv_path = target_dir / f"{position:02d}_{slug(sheet)}.csv"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            count += 1
            print(f"{source} [{sheet}] -> {csv_path} ({len(df)} filas)")
    print(f"Conversión finalizada: {len(sources)} Excel, {count} hojas CSV.")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convierte Excel del LMS a CSV.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/interim/csv"))
    args = parser.parse_args()
    convert(args.raw_dir, args.output_dir)
