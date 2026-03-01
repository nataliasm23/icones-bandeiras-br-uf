#!/usr/bin/env python3
"""
Enrich municipios.json with fiscal transfer data (FUNDEB + FPM).

Downloads CSV data from Tesouro Transparente and aggregates annual totals.
Adds: fundeb_2024, fpm_2024 (annual total in R$).

Source: Tesouro Nacional - Transferências Obrigatórias da União por Município
  https://www.tesourotransparente.gov.br/ckan/dataset/transferencias-obrigatorias-da-uniao-por-municipio

Usage:
  python3 scripts/municipios/enrich_fiscal.py [--dry-run]
"""

import csv
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
MUNICIPIOS_JSON = ROOT / "data" / "municipios.json"

FUNDEB_URL = "https://www.tesourotransparente.gov.br/ckan/dataset/3b5a779d-78f5-4602-a6b7-23ece6d60f27/resource/18d5b0ae-8037-461e-8685-3f0d7752a287/download/fundeb-por-municipio.csv"
FPM_URL = "https://www.tesourotransparente.gov.br/ckan/dataset/3b5a779d-78f5-4602-a6b7-23ece6d60f27/resource/d69ff32a-6681-4114-81f0-233bb6b17f58/download/fpm-por-municipio.csv"

FUNDEB_CACHE = Path("/tmp/fundeb-por-municipio.csv")
FPM_CACHE = Path("/tmp/fpm-por-municipio.csv")

YEAR = "2024"  # Latest complete year


def download_if_needed(url, path):
    """Download file if not cached."""
    if path.exists():
        print(f"  Using cached {path.name}")
        return
    print(f"  Downloading {path.name}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=60)
    data = resp.read()
    with open(path, "wb") as f:
        f.write(data)
    print(f"  Downloaded {len(data) / 1024 / 1024:.1f} MB")


def parse_value(s):
    """Parse Brazilian currency format '1.234.567,89' to float."""
    s = s.strip()
    if not s or s == "-":
        return 0.0
    # Remove thousand separators (.), replace decimal comma
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def aggregate_annual(csv_path, year):
    """Read monthly CSV and aggregate annual totals per SIAFI code."""
    totals = {}  # siafi_code -> annual total

    with open(csv_path, "r", encoding="latin-1") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)

        # Find the year column index
        year_col = None
        for i, h in enumerate(header):
            if h.strip() == year:
                year_col = i
                break

        if year_col is None:
            print(f"  WARNING: Year {year} not found in {csv_path.name}")
            return {}

        for row in reader:
            cod = row[0].strip()
            if not cod.isdigit() or int(cod) >= 9000:
                continue  # skip summary rows

            val = parse_value(row[year_col]) if year_col < len(row) else 0.0
            if cod not in totals:
                totals[cod] = 0.0
            totals[cod] += val

    return totals


def run(*, dry_run=False):
    """Enrich municipios.json with FUNDEB and FPM transfer data."""
    print("=== Fiscal Transfer Enrichment (FUNDEB + FPM) ===\n")

    # Download data
    download_if_needed(FUNDEB_URL, FUNDEB_CACHE)
    download_if_needed(FPM_URL, FPM_CACHE)

    # Aggregate annual totals
    print(f"\nAggregating {YEAR} annual totals...")
    fundeb = aggregate_annual(FUNDEB_CACHE, YEAR)
    fpm = aggregate_annual(FPM_CACHE, YEAR)
    print(f"  FUNDEB: {len(fundeb)} municipalities")
    print(f"  FPM: {len(fpm)} municipalities")

    # Load municipios
    print(f"\nLoading {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
        municipios = json.load(f)
    print(f"  {len(municipios)} municipalities loaded")

    # Build SIAFI → index map
    siafi_to_idx = {}
    for i, m in enumerate(municipios):
        siafi = m.get("codigo_siafi")
        if siafi:
            siafi_to_idx[siafi] = i

    if dry_run:
        matched_f = sum(1 for s in fundeb if s in siafi_to_idx or s.zfill(4) in siafi_to_idx)
        matched_p = sum(1 for s in fpm if s in siafi_to_idx or s.zfill(4) in siafi_to_idx)
        print(f"\n[DRY RUN] Would enrich:")
        print(f"  FUNDEB {YEAR}: {matched_f} municipalities")
        print(f"  FPM {YEAR}: {matched_p} municipalities")
        # Show top 5 FUNDEB
        top = sorted(fundeb.items(), key=lambda x: x[1], reverse=True)[:5]
        for siafi, val in top:
            idx = siafi_to_idx.get(siafi) or siafi_to_idx.get(siafi.zfill(4))
            name = municipios[idx]["name"] if idx is not None else "?"
            print(f"    {name}: R$ {val:,.2f}")
        return

    # Enrich
    count_f = 0
    count_p = 0

    for siafi_code, val in fundeb.items():
        idx = siafi_to_idx.get(siafi_code) or siafi_to_idx.get(siafi_code.zfill(4))
        if idx is not None and val > 0:
            municipios[idx]["fundeb_2024"] = round(val, 2)
            count_f += 1

    for siafi_code, val in fpm.items():
        idx = siafi_to_idx.get(siafi_code) or siafi_to_idx.get(siafi_code.zfill(4))
        if idx is not None and val > 0:
            municipios[idx]["fpm_2024"] = round(val, 2)
            count_p += 1

    print(f"\n  FUNDEB enriched: {count_f}")
    print(f"  FPM enriched: {count_p}")

    # Save
    print(f"\nSaving {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)
    print("  Done!")

    # Summary
    print(f"\n=== Summary ===")
    total_fundeb = sum(m.get("fundeb_2024", 0) for m in municipios)
    total_fpm = sum(m.get("fpm_2024", 0) for m in municipios)
    print(f"  Total FUNDEB {YEAR}: R$ {total_fundeb:,.2f}")
    print(f"  Total FPM {YEAR}: R$ {total_fpm:,.2f}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
