#!/usr/bin/env python3
"""
Search Wikidata for missing municipality flags by name.

Instead of bulk SPARQL, this queries each municipality individually
using the wbsearchentities API, then fetches P41 (flag image).

This catches municipalities that weren't found by IBGE code matching.
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
MAX_WORKERS = 4
REQUEST_DELAY = 0.3
REQUEST_TIMEOUT = 20

UF_NAMES = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima",
    "PA": "Pará", "AP": "Amapá", "TO": "Tocantins", "MA": "Maranhão",
    "PI": "Piauí", "CE": "Ceará", "RN": "Rio Grande do Norte",
    "PB": "Paraíba", "PE": "Pernambuco", "AL": "Alagoas", "SE": "Sergipe",
    "BA": "Bahia", "MG": "Minas Gerais", "ES": "Espírito Santo",
    "RJ": "Rio de Janeiro", "SP": "São Paulo", "PR": "Paraná",
    "SC": "Santa Catarina", "RS": "Rio Grande do Sul",
    "MS": "Mato Grosso do Sul", "MT": "Mato Grosso", "GO": "Goiás",
    "DF": "Distrito Federal",
}


def search_entity(name: str, uf: str) -> list:
    """Search Wikidata for a municipality entity."""
    search_terms = [
        f"{name}",
        f"{name} {UF_NAMES.get(uf, uf)}",
    ]

    for term in search_terms:
        params = urllib.parse.urlencode({
            "action": "wbsearchentities",
            "search": term,
            "language": "pt",
            "type": "item",
            "limit": "10",
            "format": "json",
        })

        url = f"{WIKIDATA_API}?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "BandeirasmunicipiosBR/2.0 (https://github.com/nataliasm23/icones-bandeiras-br-uf) Python/3",
        })

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))
                results = data.get("search", [])
                if results:
                    return results
        except Exception:
            pass

        time.sleep(REQUEST_DELAY)

    return []


def get_entity_claims(entity_id: str) -> dict:
    """Get claims (properties) for a Wikidata entity."""
    params = urllib.parse.urlencode({
        "action": "wbgetclaims",
        "entity": entity_id,
        "property": "P41",  # flag image
        "format": "json",
    })

    url = f"{WIKIDATA_API}?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "BandeirasmunicipiosBR/2.0 Python/3",
    })

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("claims", {})
    except Exception:
        return {}


def get_flag_from_entity(entity_id: str) -> str:
    """Get flag image filename from entity claims."""
    claims = get_entity_claims(entity_id)
    p41 = claims.get("P41", [])
    if p41:
        mainsnak = p41[0].get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        value = datavalue.get("value")
        if value:
            return value
    return None


def process_municipality(m: dict) -> dict:
    """Search for a municipality's flag on Wikidata by name."""
    results = search_entity(m["name"], m["uf"])

    for result in results:
        entity_id = result.get("id", "")
        description = result.get("description", "").lower()

        # Filter: should be a Brazilian municipality
        if any(kw in description for kw in [
            "município", "municipio", "municipality",
            "brasil", "brazil",
            UF_NAMES.get(m["uf"], "").lower(),
            m["uf"].lower(),
        ]):
            flag_file = get_flag_from_entity(entity_id)
            if flag_file:
                return {
                    "ibge_code": m["ibge_code"],
                    "name": m["name"],
                    "uf": m["uf"],
                    "found": True,
                    "wikidata_id": entity_id,
                    "flag_file": flag_file,
                    "flag_url": f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(flag_file)}",
                }

            time.sleep(REQUEST_DELAY)

    return {
        "ibge_code": m["ibge_code"],
        "name": m["name"],
        "uf": m["uf"],
        "found": False,
    }


def main():
    print("=" * 60)
    print("  🇧🇷 WIKIDATA NAME SEARCH")
    print("=" * 60)

    # Load database
    db_path = DATA_DIR / "municipios.json"
    with open(db_path, "r", encoding="utf-8") as f:
        municipios = json.load(f)

    # Filter to missing
    missing = [m for m in municipios if m["flag_status"] != "found"]
    print(f"\n  📂 {len(missing)} municipalities still missing flags")

    if not missing:
        print("  All flags already found!")
        return

    # Search Wikidata
    print(f"\n  Searching Wikidata by name...")
    found = []
    not_found = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_municipality, m): m for m in missing}

        with tqdm(total=len(missing), desc="  Searching Wikidata", unit="mun") as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result["found"]:
                    found.append(result)
                else:
                    not_found.append(result)
                pbar.update(1)
                pbar.set_postfix(found=len(found), miss=len(not_found))

    # Save results
    results_path = DATA_DIR / "wikidata-name-search.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({"found": found, "not_found": not_found}, f, ensure_ascii=False, indent=2)

    # Update database
    if found:
        found_codes = {r["ibge_code"] for r in found}
        for m in municipios:
            if m["ibge_code"] in found_codes and m["flag_status"] != "found":
                result = next(r for r in found if r["ibge_code"] == m["ibge_code"])
                m["flag_status"] = "found"
                m["flag_source"] = "wikidata-name"
                m["flag_url"] = result["flag_url"]
                m["flag_file"] = result["flag_file"]
                m["wikidata_id"] = result["wikidata_id"]

        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(municipios, f, ensure_ascii=False, indent=2)

    # Summary
    total_found = sum(1 for m in municipios if m["flag_status"] == "found")
    still_missing = len(municipios) - total_found
    pct = (total_found / len(municipios)) * 100

    print("\n" + "=" * 60)
    print("  📊 WIKIDATA NAME SEARCH SUMMARY")
    print("=" * 60)
    print(f"  Searched:          {len(missing):>6}")
    print(f"  Found:             {len(found):>6}")
    print(f"  Not found:         {len(not_found):>6}")
    print(f"  ─────────────────────────────────────")
    print(f"  🏴 Total flags (all sources): {total_found:>5} / {len(municipios)} ({pct:.1f}%)")
    print(f"  ❓ Still missing:             {still_missing:>5}")
    print("=" * 60)

    if found:
        print(f"\n  Sample found flags:")
        for r in found[:15]:
            print(f"    {r['name']:30s} ({r['uf']}) → {r['flag_file']}")

    if not_found:
        print(f"\n  Still missing by state:")
        by_uf = {}
        for r in not_found:
            by_uf.setdefault(r["uf"], []).append(r["name"])
        for uf in sorted(by_uf.keys()):
            print(f"    {uf}: {len(by_uf[uf])}")


if __name__ == "__main__":
    main()
