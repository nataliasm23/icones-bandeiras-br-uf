#!/usr/bin/env python3
"""
Enrich municipalities with additional IBGE data (wave 2).

Fetches from IBGE Pesquisas API (bulk N6 level):
  - IDHM — Índice de Desenvolvimento Humano Municipal (pesquisa 10111, indicator 329756)
  - Frota de veículos (pesquisa 22, indicator 28120)

Updates: data/municipios.json
"""

import gzip
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
MUNICIPIOS_JSON = DATA_DIR / "municipios.json"

IBGE_PESQUISAS_BASE = "https://servicodados.ibge.gov.br/api/v1/pesquisas"

IBGE_INDICATORS = [
    ("idhm",      "10111", "329756", "float"),
    ("veiculos",   "22",   "28120",  "int"),
]


def fetch_json(url, label):
    """Fetch JSON from a URL with retry logic."""
    for attempt in range(3):
        try:
            print(f"  Fetching {label}...")
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                if raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8"))
            print(f"  OK ({label})")
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"  Attempt {attempt + 1}/3 failed for {label}: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {label} after 3 attempts")


def get_latest_value(res_dict):
    """Get the most recent non-null value from a year→value dict."""
    for year in sorted(res_dict.keys(), reverse=True):
        val = res_dict[year]
        if val is not None and val != "" and val != "-" and val != "...":
            return val, year
    return None, None


def parse_ibge_indicator(raw_data, value_type):
    """Parse IBGE Pesquisas API response into {6-digit-code: (value, year)} dict."""
    if not raw_data or not raw_data[0].get("res"):
        return {}

    result = {}
    for entry in raw_data[0]["res"]:
        loc = entry["localidade"]
        val, year = get_latest_value(entry["res"])
        if val is None:
            continue

        if value_type == "float":
            try:
                val = round(float(val), 3)
            except (ValueError, TypeError):
                continue
        elif value_type == "int":
            try:
                val = int(float(val))
            except (ValueError, TypeError):
                continue

        result[loc] = (val, year)

    return result


def ibge7_to_6(ibge_code):
    """Convert 7-digit IBGE code to 6-digit (drop check digit)."""
    return str(ibge_code)[:6]


def run(*, dry_run=False, **kwargs):
    print(f"Loading {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
        municipios = json.load(f)
    print(f"Loaded {len(municipios)} municipalities")

    if dry_run:
        print("\n[DRY RUN] Would fetch:")
        for field, pesq, ind, _ in IBGE_INDICATORS:
            url = f"{IBGE_PESQUISAS_BASE}/{pesq}/indicadores/{ind}/resultados/N6"
            print(f"  {field}: {url}")
        print("[DRY RUN] No data fetched or written.")
        return

    # Fetch all indicators
    print("\nFetching IBGE Pesquisas data...")
    indicators_data = {}
    for field, pesq, ind, vtype in IBGE_INDICATORS:
        url = f"{IBGE_PESQUISAS_BASE}/{pesq}/indicadores/{ind}/resultados/N6"
        raw = fetch_json(url, field)
        parsed = parse_ibge_indicator(raw, vtype)
        indicators_data[field] = parsed
        print(f"    → {field}: {len(parsed)} values")
        time.sleep(1)

    # Enrich
    print("\nEnriching municipalities...")
    counts = {field: 0 for field in indicators_data.keys()}

    for mun in municipios:
        code6 = ibge7_to_6(mun["ibge_code"])

        for field, data in indicators_data.items():
            entry = data.get(code6)
            if entry is not None:
                val, year = entry
                mun[field] = val
                # Store the reference year for time-sensitive data
                if field == "veiculos":
                    mun["veiculos_ano"] = year
                counts[field] += 1

    print("\n  Enrichment results:")
    for field, count in counts.items():
        pct = count / len(municipios) * 100
        print(f"    {field:>12}: {count:>5} ({pct:.1f}%)")

    # Spot check
    sp = next((m for m in municipios if m["ibge_code"] == 3550308), None)
    if sp:
        print(f"\n  Spot check — São Paulo (3550308):")
        print(f"    idhm: {sp.get('idhm', 'N/A')}")
        print(f"    veiculos: {sp.get('veiculos', 'N/A'):,} ({sp.get('veiculos_ano', '?')})")

    print(f"\nSaving to {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)
    print("Done!")


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
