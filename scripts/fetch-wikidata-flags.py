#!/usr/bin/env python3
"""
Fetch flag images from Wikidata for all Brazilian municipalities.

Uses Wikidata SPARQL endpoint to query:
- P41 (flag image) for items that are municipalities of Brazil
- P31 (instance of) = Q3184121 (municipality of Brazil)
- P1585 (IBGE code) to match with our database

Output:
- data/wikidata-flags.json → Raw Wikidata results
- Updates data/municipios.json with flag_source, flag_url, flag_status
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

# Query all Brazilian municipalities with flag images
# P31 = instance of, Q3184121 = municipality of Brazil
# P41 = flag image
# P1585 = Brazilian IBGE municipality code
SPARQL_QUERY = """
SELECT ?municipality ?municipalityLabel ?ibgeCode ?flagImage ?coords WHERE {
  ?municipality wdt:P31/wdt:P279* wd:Q3184121 .
  OPTIONAL { ?municipality wdt:P1585 ?ibgeCode . }
  OPTIONAL { ?municipality wdt:P41 ?flagImage . }
  OPTIONAL { ?municipality wdt:P625 ?coords . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pt,en" . }
}
"""

# Secondary query: also get municipalities that are instance of Q747074 (municipality of state capital)
SPARQL_QUERY_CAPITALS = """
SELECT ?municipality ?municipalityLabel ?ibgeCode ?flagImage WHERE {
  {
    ?municipality wdt:P31 wd:Q3184121 .
  } UNION {
    ?municipality wdt:P31 wd:Q747074 .
  } UNION {
    ?municipality wdt:P31 wd:Q21200642 .
  }
  ?municipality wdt:P17 wd:Q155 .
  OPTIONAL { ?municipality wdt:P1585 ?ibgeCode . }
  OPTIONAL { ?municipality wdt:P41 ?flagImage . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pt,en" . }
}
"""


def query_wikidata(query: str, description: str) -> list:
    """Execute a SPARQL query against Wikidata."""
    print(f"\n  ⏳ Querying Wikidata: {description}...")

    params = urllib.parse.urlencode({
        "query": query,
        "format": "json",
    })

    url = f"{WIKIDATA_SPARQL_URL}?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "BandeirasmunicipiosBR/1.0 (https://github.com/nataliasm23/icones-bandeiras-br-uf) Python/3",
        "Accept": "application/sparql-results+json",
    })

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read()
            data = json.loads(raw.decode("utf-8"))
            results = data.get("results", {}).get("bindings", [])
            print(f"  ✅ Got {len(results)} results")
            return results
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        return []


def parse_wikidata_results(results: list) -> dict:
    """Parse Wikidata SPARQL results into a dict keyed by IBGE code."""
    by_ibge = {}
    by_name = {}
    flags_found = 0

    for r in tqdm(results, desc="  Parsing Wikidata results", unit="entry"):
        entry = {
            "wikidata_id": r.get("municipality", {}).get("value", "").split("/")[-1],
            "label": r.get("municipalityLabel", {}).get("value", ""),
            "ibge_code": r.get("ibgeCode", {}).get("value"),
            "flag_url": r.get("flagImage", {}).get("value"),
            "coords": r.get("coords", {}).get("value"),
        }

        if entry["flag_url"]:
            flags_found += 1

        if entry["ibge_code"]:
            try:
                code = int(entry["ibge_code"])
                by_ibge[code] = entry
            except ValueError:
                pass

        # Also index by name for fuzzy matching
        if entry["label"]:
            name_key = entry["label"].lower().strip()
            by_name[name_key] = entry

    print(f"  📊 Parsed: {len(by_ibge)} by IBGE code, {len(by_name)} by name, {flags_found} with flags")
    return by_ibge, by_name


def commons_url_to_filename(url: str) -> str:
    """Extract the filename from a Wikimedia Commons URL."""
    if not url:
        return None
    # URL format: https://commons.wikimedia.org/wiki/Special:FilePath/Filename.svg
    return urllib.parse.unquote(url.split("/")[-1])


def main():
    print("=" * 60)
    print("  🇧🇷 WIKIDATA FLAG COLLECTOR")
    print("=" * 60)

    # Load our database
    db_path = DATA_DIR / "municipios.json"
    with open(db_path, "r", encoding="utf-8") as f:
        municipios = json.load(f)
    print(f"\n  📂 Loaded {len(municipios)} municipalities from database")

    # Query Wikidata
    print("\n  Step 1/3: Query Wikidata for Brazilian municipality flags...")
    results = query_wikidata(SPARQL_QUERY_CAPITALS, "municipalities + capitals + districts")

    if not results:
        print("  ⚠️  No results from primary query. Trying simpler query...")
        results = query_wikidata(SPARQL_QUERY, "basic municipality query")

    # Save raw results
    raw_path = DATA_DIR / "wikidata-flags-raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 Saved raw results to {raw_path}")

    # Parse results
    print("\n  Step 2/3: Parse and match results...")
    by_ibge, by_name = parse_wikidata_results(results)

    # Match with our database
    matched_ibge = 0
    matched_name = 0
    flags_total = 0
    unmatched = []

    print("\n  Step 3/3: Matching with IBGE database...")
    for m in tqdm(municipios, desc="  Matching municipalities", unit="mun"):
        ibge_code = m["ibge_code"]
        entry = by_ibge.get(ibge_code)

        if not entry:
            # Try matching by name
            name_key = m["name"].lower().strip()
            entry = by_name.get(name_key)
            if entry:
                matched_name += 1
            else:
                unmatched.append({"name": m["name"], "uf": m["uf"], "ibge_code": ibge_code})
                continue
        else:
            matched_ibge += 1

        # Update municipality record
        m["wikidata_id"] = entry.get("wikidata_id")

        if entry.get("flag_url"):
            m["flag_status"] = "found"
            m["flag_source"] = "wikidata"
            m["flag_url"] = entry["flag_url"]
            m["flag_file"] = commons_url_to_filename(entry["flag_url"])
            flags_total += 1

    # Save updated database
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 Updated database at {db_path}")

    # Save Wikidata match index
    wikidata_index = {
        "by_ibge_code": {str(k): v for k, v in by_ibge.items()},
        "total_wikidata_entries": len(results),
        "matched_by_ibge": matched_ibge,
        "matched_by_name": matched_name,
        "flags_found": flags_total,
    }
    index_path = DATA_DIR / "wikidata-index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(wikidata_index, f, ensure_ascii=False, indent=2)

    # Save unmatched for manual review
    unmatched_path = DATA_DIR / "unmatched-municipalities.json"
    with open(unmatched_path, "w", encoding="utf-8") as f:
        json.dump(sorted(unmatched, key=lambda x: x["name"]), f, ensure_ascii=False, indent=2)

    # Print summary
    total = len(municipios)
    pct_flags = (flags_total / total) * 100 if total else 0
    pct_matched = ((matched_ibge + matched_name) / total) * 100 if total else 0

    print("\n" + "=" * 60)
    print("  📊 WIKIDATA RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Wikidata entries found:    {len(results):>6}")
    print(f"  Matched by IBGE code:      {matched_ibge:>6}")
    print(f"  Matched by name:           {matched_name:>6}")
    print(f"  Total matched:             {matched_ibge + matched_name:>6}  ({pct_matched:.1f}%)")
    print(f"  Unmatched municipalities:  {len(unmatched):>6}")
    print(f"  ─────────────────────────────────────")
    print(f"  🏴 Flags found:             {flags_total:>6}  ({pct_flags:.1f}%)")
    print(f"  ❓ Flags missing:           {total - flags_total:>6}  ({100 - pct_flags:.1f}%)")
    print("=" * 60)

    # Show sample of matched flags
    print("\n  🏴 Sample flags found:")
    count = 0
    for m in municipios:
        if m["flag_status"] == "found" and count < 15:
            print(f"    {m['name']:30s} ({m['uf']}) → {m['flag_file']}")
            count += 1

    # Show by-UF breakdown of flags found
    print("\n  📊 Flags found by state:")
    uf_flags = {}
    uf_total = {}
    for m in municipios:
        uf = m["uf"]
        uf_total[uf] = uf_total.get(uf, 0) + 1
        if m["flag_status"] == "found":
            uf_flags[uf] = uf_flags.get(uf, 0) + 1

    for uf in sorted(uf_total.keys()):
        found = uf_flags.get(uf, 0)
        total_uf = uf_total[uf]
        pct = (found / total_uf) * 100 if total_uf else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"    {uf} {bar} {found:>4}/{total_uf:<4} ({pct:>5.1f}%)")


if __name__ == "__main__":
    main()
