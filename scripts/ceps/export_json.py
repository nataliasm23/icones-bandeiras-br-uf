#!/usr/bin/env python3
"""
export_json.py  (was 05-export-json-by-uf.py)
──────────────────────────────────────────────
Exporta CEPs particionados por UF em 27 arquivos JSON (intermediarios).

Le data/merged/ceps-validated.csv e cria:
  - data/ceps/by-uf/{UF}.json para cada uma das 27 UFs
"""

import csv
import json
import logging
import time
from collections import defaultdict
from pathlib import Path

from config import ALL_UFS, DATA_DIR, MERGED_DIR

log = logging.getLogger(__name__)

# === Paths ===
INPUT_CSV = MERGED_DIR / "ceps-validated.csv"
BY_UF_OUTPUT_DIR = DATA_DIR / "by-uf"

JSON_COLUMNS = ["cep", "logradouro", "complemento", "bairro", "localidade", "uf", "ibge", "ddd"]


def read_and_partition(csv_path: Path) -> dict[str, list[dict]]:
    by_uf: dict[str, list[dict]] = defaultdict(list)

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            uf = row.get("uf", "").strip().upper()
            if not uf:
                continue
            record = {col: row.get(col, "") or "" for col in JSON_COLUMNS}
            by_uf[uf].append(record)

    for uf in by_uf:
        by_uf[uf].sort(key=lambda r: r["cep"])

    return dict(by_uf)


def export_uf_jsons(by_uf: dict[str, list[dict]]) -> dict[str, dict]:
    BY_UF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_info: dict[str, dict] = {}

    for uf in sorted(by_uf.keys()):
        records = by_uf[uf]
        output_path = BY_UF_OUTPUT_DIR / f"{uf}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, separators=(",", ":"))

        size_kb = output_path.stat().st_size / 1024
        file_info[uf] = {"count": len(records), "file_size_kb": round(size_kb, 1)}

    return file_info


def print_summary(file_info: dict[str, dict]) -> None:
    total_ceps = sum(info["count"] for info in file_info.values())
    total_size = sum(info["file_size_kb"] for info in file_info.values())

    log.info("=" * 45)
    log.info("  Arquivos JSON por UF: %s", BY_UF_OUTPUT_DIR)
    log.info("  Total UFs: %d", len(file_info))
    log.info("  Total CEPs: %d", total_ceps)
    log.info("  Tamanho total: %.1f KB", total_size)
    log.info("=" * 45)

    for uf in sorted(file_info.keys()):
        info = file_info[uf]
        log.info("  %s: %10d CEPs  %10.1f KB", uf, info["count"], info["file_size_kb"])

    missing = set(ALL_UFS) - set(file_info.keys())
    if missing:
        log.warning("  UFs sem CEPs: %s", ", ".join(sorted(missing)))


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run(*, dry_run: bool = False) -> None:
    if not INPUT_CSV.exists():
        log.error("Arquivo nao encontrado: %s", INPUT_CSV)
        log.error("Execute os scripts anteriores primeiro.")
        return

    log.info("Lendo %s...", INPUT_CSV)
    start = time.time()

    by_uf = read_and_partition(INPUT_CSV)
    total = sum(len(v) for v in by_uf.values())
    log.info("  %d registros lidos, %d UFs encontradas.", total, len(by_uf))

    if dry_run:
        log.info("[DRY-RUN] Would export %d UF JSON files to %s", len(by_uf), BY_UF_OUTPUT_DIR)
        for uf in sorted(by_uf.keys()):
            log.info("  %s: %d CEPs -> %s/%s.json", uf, len(by_uf[uf]), BY_UF_OUTPUT_DIR, uf)
        return

    log.info("Exportando JSONs por UF...")
    file_info = export_uf_jsons(by_uf)

    elapsed = time.time() - start
    print_summary(file_info)
    log.info("Tempo total: %.1fs", elapsed)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    run()
