#!/usr/bin/env python3
"""
Enrich municipalities with IBGE socioeconomic data.

Fetches from IBGE Pesquisas API (bulk N6 level):
  - Gentílico (pesquisa 33, indicator 60409)
  - Bioma predominante (pesquisa 33, indicator 77861)
  - Sistema costeiro-marinho (pesquisa 33, indicator 82270)
  - Prefeito atual (pesquisa 33, indicator 29170)
  - PIB per capita (pesquisa 38, indicator 47001)
  - PIB total (pesquisa 38, indicator 46997)
  - Taxa mortalidade infantil (pesquisa 39, indicator 30279)
  - Índice de Gini (pesquisa 36, indicator 30252)
  - Estabelecimentos de saúde (pesquisa 32, indicator 28163)

Fetches from kelvins/municipios-brasileiros CSV:
  - Código SIAFI
  - Fuso horário

Derives:
  - capital (from UF_CAPITALS)

Updates: data/municipios.json
"""

import csv
import gzip
import io
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
MUNICIPIOS_JSON = DATA_DIR / "municipios.json"

IBGE_PESQUISAS_BASE = "https://servicodados.ibge.gov.br/api/v1/pesquisas"

# Each entry: (field_name, pesquisa_id, indicator_id, value_type, preferred_year_or_latest)
IBGE_INDICATORS = [
    ("gentilico",                "33", "60409", "str",   None),
    ("bioma",                    "33", "77861", "str",   None),
    ("sistema_costeiro",         "33", "82270", "str",   None),
    ("prefeito",                 "33", "29170", "str",   None),
    ("pib_per_capita",           "38", "47001", "float", None),
    ("pib",                      "38", "46997", "float", None),
    ("taxa_mortalidade_infantil","39", "30279", "float", None),
    ("indice_gini",              "36", "30252", "float", None),
    ("estabelecimentos_saude",   "32", "28163", "int",   None),
]

KELVINS_CSV_URL = (
    "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
)

# State capitals by IBGE code
CAPITALS = {
    1200401, 2704302, 1302603, 1600303, 2927408, 2304400, 5300108,
    3205309, 5208707, 2111300, 3106200, 5002704, 5103403, 1501402,
    2507507, 2611606, 2211001, 4106902, 3304557, 2408102, 1100205,
    1400100, 4314902, 4205407, 2800308, 3550308, 1721000,
}


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


def fetch_csv(url, label):
    """Fetch CSV from a URL."""
    print(f"  Fetching {label}...")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    print(f"  OK ({label})")
    return raw


def get_latest_value(res_dict):
    """Get the most recent non-null value from a year→value dict."""
    for year in sorted(res_dict.keys(), reverse=True):
        val = res_dict[year]
        if val is not None and val != "" and val != "-" and val != "...":
            return val, year
    return None, None


def parse_ibge_indicator(raw_data, value_type):
    """Parse IBGE Pesquisas API response into {6-digit-code: value} dict."""
    if not raw_data or not raw_data[0].get("res"):
        return {}

    result = {}
    for entry in raw_data[0]["res"]:
        loc = entry["localidade"]  # 6-digit IBGE code (without check digit)
        val, year = get_latest_value(entry["res"])
        if val is None:
            continue

        if value_type == "float":
            try:
                val = round(float(val), 2)
            except (ValueError, TypeError):
                continue
        elif value_type == "int":
            try:
                val = int(float(val))
            except (ValueError, TypeError):
                continue
        # str stays as-is

        result[loc] = val

    return result


def parse_kelvins_csv(csv_text):
    """Parse kelvins/municipios-brasileiros CSV into {ibge_code: {siafi, fuso_horario}}."""
    reader = csv.DictReader(io.StringIO(csv_text))
    result = {}
    for row in reader:
        code = int(row["codigo_ibge"])
        result[code] = {
            "codigo_siafi": row.get("siafi_id", ""),
            "fuso_horario": row.get("fuso_horario", ""),
        }
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
        for field, pesq, ind, vtype, _ in IBGE_INDICATORS:
            url = f"{IBGE_PESQUISAS_BASE}/{pesq}/indicadores/{ind}/resultados/N6"
            print(f"  {field}: {url}")
        print(f"  kelvins CSV: {KELVINS_CSV_URL}")
        print(f"  + capital flag for {len(CAPITALS)} capitals")
        print("[DRY RUN] No data fetched or written.")
        return

    # Fetch all IBGE indicators
    print("\nFetching IBGE Pesquisas data...")
    indicators_data = {}
    for field, pesq, ind, vtype, _ in IBGE_INDICATORS:
        url = f"{IBGE_PESQUISAS_BASE}/{pesq}/indicadores/{ind}/resultados/N6"
        raw = fetch_json(url, field)
        parsed = parse_ibge_indicator(raw, vtype)
        indicators_data[field] = parsed
        print(f"    → {field}: {len(parsed)} values")
        time.sleep(1)

    # Fetch kelvins CSV
    print("\nFetching kelvins/municipios-brasileiros CSV...")
    csv_text = fetch_csv(KELVINS_CSV_URL, "kelvins CSV")
    kelvins_data = parse_kelvins_csv(csv_text)
    print(f"    → {len(kelvins_data)} municipalities from CSV")

    # Enrich
    print("\nEnriching municipalities...")
    counts = {field: 0 for field in list(indicators_data.keys()) + ["codigo_siafi", "fuso_horario", "capital"]}

    for mun in municipios:
        code7 = mun["ibge_code"]
        code6 = ibge7_to_6(code7)

        # IBGE Pesquisas indicators
        for field, data in indicators_data.items():
            val = data.get(code6)
            if val is not None:
                # Normalize sistema_costeiro to boolean-like
                if field == "sistema_costeiro":
                    val = val.strip().lower() == "pertence"
                mun[field] = val
                counts[field] += 1

        # Kelvins CSV data
        kelvins = kelvins_data.get(code7)
        if kelvins:
            if kelvins["codigo_siafi"]:
                mun["codigo_siafi"] = kelvins["codigo_siafi"]
                counts["codigo_siafi"] += 1
            if kelvins["fuso_horario"]:
                mun["fuso_horario"] = kelvins["fuso_horario"]
                counts["fuso_horario"] += 1

        # Capital flag
        mun["capital"] = code7 in CAPITALS
        if mun["capital"]:
            counts["capital"] += 1

    print("\n  Enrichment results:")
    for field, count in counts.items():
        pct = count / len(municipios) * 100
        print(f"    {field:>30}: {count:>5} ({pct:.1f}%)")

    # Spot check: São Paulo
    sp = next((m for m in municipios if m["ibge_code"] == 3550308), None)
    if sp:
        print(f"\n  Spot check — São Paulo (3550308):")
        for field in ["gentilico", "bioma", "sistema_costeiro", "prefeito",
                       "pib_per_capita", "pib", "taxa_mortalidade_infantil",
                       "indice_gini", "estabelecimentos_saude",
                       "codigo_siafi", "fuso_horario", "capital"]:
            print(f"    {field}: {sp.get(field, 'N/A')}")

    print(f"\nSaving to {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)
    print("Done!")


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
