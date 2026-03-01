#!/usr/bin/env python3
"""
Enrich the municipalities database with additional IBGE data.

Fetches from IBGE APIs:
- Population (Censo 2022)
- Population estimate (Estimativa 2025)
- Area (km²)
- Regiões imediatas e intermediárias

Updates: data/municipios.json with new fields:
  populacao_2022, populacao_estimada_2025, area_km2, densidade_demo,
  regiao_imediata, regiao_intermediaria
"""

import gzip
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MUNICIPIOS_JSON = DATA_DIR / "municipios.json"

IBGE_BASE = "https://servicodados.ibge.gov.br"

# Censo 2022 - Population by municipality
POPULATION_URL = (
    f"{IBGE_BASE}/api/v3/agregados/4714/periodos/2022"
    "/variaveis/93?localidades=N6[all]"
)

# Estimativa 2025 - Population estimate by municipality
ESTIMATE_2025_URL = (
    f"{IBGE_BASE}/api/v3/agregados/6579/periodos/2025"
    "/variaveis/9324?localidades=N6[all]"
)

# Area territorial (km²)
AREA_URL = (
    f"{IBGE_BASE}/api/v3/agregados/1301/periodos/-6"
    "/variaveis/615?localidades=N6[all]"
)

# Flat view with regiões imediatas e intermediárias
LOCALIDADES_URL = (
    f"{IBGE_BASE}/api/v1/localidades/municipios?view=nivelado"
)


def fetch_json(url, label):
    """Fetch JSON from a URL with retry logic."""
    for attempt in range(3):
        try:
            print(f"  Fetching {label}...")
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                if raw[:2] == b'\x1f\x8b':
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8"))
            print(f"  OK ({label})")
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"  Attempt {attempt + 1}/3 failed for {label}: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {label} after 3 attempts")


def parse_population(raw):
    """Parse population API response into {ibge_code: population} dict."""
    pop = {}
    # Response is a list with one variable entry
    resultados = raw[0]["resultados"][0]["series"]
    for serie in resultados:
        code = int(serie["localidade"]["id"])
        value = serie["serie"].get("2022", "")
        if value and value not in ("-", "...", "X"):
            pop[code] = int(value)
    print(f"  Parsed population for {len(pop)} municipalities")
    return pop


def parse_estimate_2025(raw):
    """Parse 2025 population estimate into {ibge_code: population} dict."""
    est = {}
    resultados = raw[0]["resultados"][0]["series"]
    for serie in resultados:
        code = int(serie["localidade"]["id"])
        value = serie["serie"].get("2025", "")
        if value and value not in ("-", "...", "X"):
            est[code] = int(value)
    print(f"  Parsed 2025 estimates for {len(est)} municipalities")
    return est


def parse_area(raw):
    """Parse area API response into {ibge_code: area_km2} dict."""
    areas = {}
    resultados = raw[0]["resultados"][0]["series"]
    for serie in resultados:
        code = int(serie["localidade"]["id"])
        # Get the most recent period value
        values = serie["serie"]
        value = None
        for v in values.values():
            if v and v not in ("-", "...", "X"):
                value = v
        if value:
            areas[code] = float(value)
    print(f"  Parsed area for {len(areas)} municipalities")
    return areas


def parse_regioes(raw):
    """Parse flat localidades into {ibge_code: {imediata, intermediaria}}."""
    regioes = {}
    for mun in raw:
        code = int(mun["municipio-id"])
        regioes[code] = {
            "regiao_imediata": mun.get("regiao-imediata-nome", ""),
            "regiao_intermediaria": mun.get("regiao-intermediaria-nome", ""),
        }
    print(f"  Parsed regiões for {len(regioes)} municipalities")
    return regioes


def run(*, dry_run=False, **kwargs):
    print(f"Loading {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
        municipios = json.load(f)
    print(f"Loaded {len(municipios)} municipalities")

    if dry_run:
        print("\n[DRY RUN] Would fetch from IBGE APIs:")
        print(f"  Population (Censo 2022): {POPULATION_URL}")
        print(f"  Estimate (2025):         {ESTIMATE_2025_URL}")
        print(f"  Area:                    {AREA_URL}")
        print(f"  Regiões:                 {LOCALIDADES_URL}")
        print("[DRY RUN] No data fetched or written.")
        return

    print("\nFetching IBGE data...")
    pop_raw = fetch_json(POPULATION_URL, "population (Censo 2022)")
    time.sleep(2)
    est_raw = fetch_json(ESTIMATE_2025_URL, "population estimate (2025)")
    time.sleep(2)
    area_raw = fetch_json(AREA_URL, "area (km²)")
    time.sleep(2)
    regioes_raw = fetch_json(LOCALIDADES_URL, "regiões imediatas/intermediárias")

    print("\nParsing responses...")
    population = parse_population(pop_raw)
    estimates_2025 = parse_estimate_2025(est_raw)
    areas = parse_area(area_raw)
    regioes = parse_regioes(regioes_raw)

    print("\nEnriching municipalities...")
    enriched = 0
    missing_pop = 0
    missing_est = 0
    missing_area = 0

    for mun in municipios:
        code = mun["ibge_code"]

        # Population (Censo 2022)
        pop = population.get(code)
        if pop is not None:
            mun["populacao_2022"] = pop
        else:
            missing_pop += 1

        # Population estimate (2025)
        est = estimates_2025.get(code)
        if est is not None:
            mun["populacao_estimada_2025"] = est
        else:
            missing_est += 1

        # Area
        area = areas.get(code)
        if area is not None:
            mun["area_km2"] = area
        else:
            missing_area += 1

        # Demographic density (use 2025 estimate if available, else 2022 census)
        pop_for_density = est if est is not None else pop
        if pop_for_density is not None and area is not None and area > 0:
            mun["densidade_demo"] = round(pop_for_density / area, 2)

        # Regiões
        reg = regioes.get(code, {})
        if reg.get("regiao_imediata"):
            mun["regiao_imediata"] = reg["regiao_imediata"]
        if reg.get("regiao_intermediaria"):
            mun["regiao_intermediaria"] = reg["regiao_intermediaria"]

        enriched += 1

    print(f"  Enriched: {enriched}")
    if missing_pop:
        print(f"  Missing population (2022): {missing_pop}")
    if missing_est:
        print(f"  Missing estimate (2025): {missing_est}")
    if missing_area:
        print(f"  Missing area: {missing_area}")

    # Spot check: São Paulo
    sp = next((m for m in municipios if m["ibge_code"] == 3550308), None)
    if sp:
        print(f"\n  Spot check - São Paulo (3550308):")
        print(f"    Population (2022): {sp.get('populacao_2022', 'N/A'):,}")
        print(f"    Estimate (2025):   {sp.get('populacao_estimada_2025', 'N/A'):,}")
        print(f"    Area: {sp.get('area_km2', 'N/A')} km²")
        print(f"    Density: {sp.get('densidade_demo', 'N/A')} hab/km²")
        print(f"    Região imediata: {sp.get('regiao_imediata', 'N/A')}")
        print(f"    Região intermediária: {sp.get('regiao_intermediaria', 'N/A')}")

    print(f"\nSaving to {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)
    print("Done!")


if __name__ == "__main__":
    run()
