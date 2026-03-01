#!/usr/bin/env python3
"""
Enrich municipality database with geolocation, DDD, and CEP sede.

Sources:
  - Geolocation (lat/lng) and DDD: kelvins_municipios.csv
  - CEP sede: smallest CEP per IBGE code from unified SQLite database
"""

import csv
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
DATABASE_DIR = ROOT / "database"
KELVINS_CSV = DATA_DIR / "ceps" / "raw" / "kelvins_municipios.csv"
UNIFIED_SQLITE = DATABASE_DIR / "municipios-br.sqlite"
MUNICIPIOS_JSON = DATA_DIR / "municipios.json"


def load_kelvins():
    """Load geolocation and DDD from kelvins CSV."""
    geo = {}
    with open(KELVINS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ibge = int(row["codigo_ibge"])
            geo[ibge] = {
                "latitude": float(row["latitude"]) if row["latitude"] else None,
                "longitude": float(row["longitude"]) if row["longitude"] else None,
                "ddd": row["ddd"].strip() if row["ddd"] else None,
            }
    print(f"  Kelvins: {len(geo)} municipalities with geo/DDD data")
    return geo


def load_cep_sede():
    """Find smallest CEP per IBGE code from unified SQLite database."""
    cep_sede = {}

    if not UNIFIED_SQLITE.exists():
        print("  Warning: unified SQLite not found, skipping cep_sede")
        return cep_sede

    conn = sqlite3.connect(str(UNIFIED_SQLITE))
    rows = conn.execute(
        "SELECT ibge, MIN(cep) as min_cep FROM ceps WHERE ibge != '' GROUP BY ibge"
    ).fetchall()
    conn.close()

    for ibge, min_cep in rows:
        cep_sede[ibge] = min_cep

    print(f"  CEP sede: {len(cep_sede)} municipalities from SQLite")
    return cep_sede


def run(*, dry_run=False, **kwargs):
    """Enrich municipios.json with geo, DDD, and CEP sede."""
    if dry_run:
        print("[DRY RUN] Source files:")
        print(f"  Kelvins CSV:    {KELVINS_CSV}")
        print(f"    exists: {KELVINS_CSV.exists()}")
        print(f"  Unified SQLite: {UNIFIED_SQLITE}")
        print(f"    exists: {UNIFIED_SQLITE.exists()}")
        print(f"  Municipios JSON: {MUNICIPIOS_JSON}")
        print(f"    exists: {MUNICIPIOS_JSON.exists()}")
        print("[DRY RUN] No data loaded or written.")
        return

    print("Loading enrichment sources...")
    geo = load_kelvins()
    cep_sede = load_cep_sede()

    print(f"\nLoading {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
        municipios = json.load(f)

    enriched = 0
    geo_count = 0
    ddd_count = 0
    cep_count = 0

    for mun in municipios:
        ibge_code = mun["ibge_code"]
        ibge_str = str(ibge_code)
        changed = False

        # Geo + DDD from kelvins
        if ibge_code in geo:
            info = geo[ibge_code]
            if info["latitude"] is not None:
                mun["latitude"] = round(info["latitude"], 4)
                mun["longitude"] = round(info["longitude"], 4)
                geo_count += 1
                changed = True
            if info["ddd"]:
                mun["ddd"] = info["ddd"]
                ddd_count += 1
                changed = True

        # CEP sede
        if ibge_str in cep_sede:
            cep = cep_sede[ibge_str]
            mun["cep_sede"] = f"{cep[:5]}-{cep[5:]}"
            cep_count += 1
            changed = True

        if changed:
            enriched += 1

    # Write back
    with open(MUNICIPIOS_JSON, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)

    print(f"\nEnriched {enriched}/{len(municipios)} municipalities:")
    print(f"  Geolocation: {geo_count}")
    print(f"  DDD:         {ddd_count}")
    print(f"  CEP sede:    {cep_count}")
    print(f"\nSaved to {MUNICIPIOS_JSON}")


if __name__ == "__main__":
    run()
