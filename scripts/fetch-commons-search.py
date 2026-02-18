#!/usr/bin/env python3
"""
Search Wikimedia Commons for flags of missing municipalities.

Uses the Commons API search to find flag files by municipality name.
More targeted than category browsing.
"""

import json
import re
import time
import unicodedata
import urllib.request
import urllib.parse
import hashlib
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

STATE_FLAGS_LOWER = {
    "bandeira do acre", "bandeira de alagoas", "bandeira do amapa",
    "bandeira do amazonas", "bandeira da bahia", "bandeira do ceara",
    "bandeira do distrito federal", "bandeira do espirito santo",
    "bandeira de goias", "bandeira do maranhao", "bandeira de mato grosso",
    "bandeira de mato grosso do sul", "bandeira de minas gerais",
    "bandeira do para", "bandeira da paraiba", "bandeira do parana",
    "bandeira de pernambuco", "bandeira do piaui",
    "bandeira do rio de janeiro", "bandeira do rio grande do norte",
    "bandeira do rio grande do sul", "bandeira de rondonia",
    "bandeira de roraima", "bandeira de santa catarina",
    "bandeira de sao paulo", "bandeira de sergipe",
    "bandeira do tocantins", "bandeira do brasil",
}


def normalize(text):
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def get_commons_url(filename):
    """Build direct Wikimedia Commons URL."""
    fname = filename.replace(" ", "_")
    md5 = hashlib.md5(fname.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{urllib.parse.quote(fname)}"


def is_valid_flag(filename, municipality_name):
    """Check if filename is likely a valid municipality flag."""
    fn = normalize(filename)
    mun = normalize(municipality_name)

    # Must relate to flags
    if "bandeira" not in fn and "flag" not in fn:
        return False

    # Reject state/national flags
    for sf in STATE_FLAGS_LOWER:
        if sf in fn:
            return False

    # Reject brasão-only files
    if "brasao" in fn and "bandeira" not in fn:
        return False

    # Municipality name check - at least one 3+ char word
    mun_words = [w for w in mun.split() if len(w) >= 3]
    if mun_words:
        return any(w in fn for w in mun_words)

    return True


def search_commons(municipality_name, uf):
    """Search Wikimedia Commons for a municipality's flag."""
    queries = [
        f"Bandeira de {municipality_name}",
        f"Bandeira {municipality_name} {uf}",
        f"Flag of {municipality_name}",
    ]

    for query in queries:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srnamespace": "6",  # File namespace
            "srlimit": "10",
            "format": "json",
        }
        url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "User-Agent": "BandeirasmunicipiosBR/1.0 (https://github.com/nataliasm23/icones-bandeiras-br-uf) Python/3",
        })
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.load(resp)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = 10 * (attempt + 1)
                    time.sleep(wait)
                    continue
                break
            except Exception:
                break
        else:
            continue

        results = data.get("query", {}).get("search", [])
        for r in results:
            title = r["title"].replace("File:", "")
            if is_valid_flag(title, municipality_name):
                return title

    return None


def main():
    print("=" * 60)
    print("  WIKIMEDIA COMMONS SEARCH")
    print("=" * 60)

    missing = json.load(open(DATA_DIR / "missing-municipalities.json"))
    print(f"\n  Searching for {len(missing)} missing municipalities...")

    # Load previous results to resume
    out_path = DATA_DIR / "commons-search-flags.json"
    already_searched = set()
    found = []
    if out_path.exists():
        prev = json.load(open(out_path))
        found = prev.get("found", [])
        already_searched = {f["ibge_code"] for f in found}
        already_searched.update(m["ibge_code"] for m in prev.get("not_found", []))
        if already_searched:
            print(f"  Resuming: {len(already_searched)} already searched, {len(found)} found")
            missing = [m for m in missing if m["ibge_code"] not in already_searched]
            print(f"  Remaining: {len(missing)}")

    if not missing:
        print("  Nothing to search!")
        return

    not_found = []

    for i, m in enumerate(missing):
        if i % 50 == 0 and i > 0:
            print(f"  Progress: {i}/{len(missing)} ({len(found)} found)", flush=True)
            # Save progress periodically
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump({"found": found, "not_found": not_found}, f, ensure_ascii=False, indent=2)

        flag_file = search_commons(m["name"], m["uf"])
        if flag_file:
            found.append({
                "ibge_code": m["ibge_code"],
                "name": m["name"],
                "uf": m["uf"],
                "slug": m["slug"],
                "flag_file": flag_file,
                "flag_url": get_commons_url(flag_file),
            })
        else:
            not_found.append(m)

        time.sleep(2)  # Rate limit - Wikimedia enforces strict limits
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"found": found, "not_found": not_found}, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  RESULTS")
    print(f"{'=' * 60}")
    print(f"  Found:     {len(found)}")
    print(f"  Not found: {len(not_found)}")
    print(f"  Saved to:  {out_path}")

    if found:
        print(f"\n  First 10 found:")
        for item in found[:10]:
            print(f"    {item['name']:30s} ({item['uf']}) -> {item['flag_file']}")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
