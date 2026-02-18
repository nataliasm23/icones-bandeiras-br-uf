#!/usr/bin/env python3
"""
Targeted Wikipedia flag search for missing municipalities.

For each missing municipality, searches its Wikipedia article for flag images.
Uses strict matching to avoid state/national flags.
"""

import json
import re
import time
import unicodedata
import urllib.request
import urllib.parse
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

STATE_FLAGS = {
    "bandeira do acre", "bandeira de alagoas", "bandeira do amapá", "bandeira do amazonas",
    "bandeira da bahia", "bandeira do ceará", "bandeira do distrito federal",
    "bandeira do espírito santo", "bandeira de goiás", "bandeira do maranhão",
    "bandeira de mato grosso", "bandeira de mato grosso do sul", "bandeira de minas gerais",
    "bandeira do pará", "bandeira da paraíba", "bandeira do paraná", "bandeira de pernambuco",
    "bandeira do piauí", "bandeira do rio de janeiro", "bandeira do rio grande do norte",
    "bandeira do rio grande do sul", "bandeira de rondônia", "bandeira de roraima",
    "bandeira de santa catarina", "bandeira de são paulo", "bandeira de sergipe",
    "bandeira do tocantins", "bandeira do brasil",
}

# State name slugs to exclude from filenames
STATE_SLUGS = {
    "acre", "alagoas", "amapa", "amazonas", "bahia", "ceara", "distrito-federal",
    "espirito-santo", "goias", "maranhao", "mato-grosso", "mato-grosso-do-sul",
    "minas-gerais", "para", "paraiba", "parana", "pernambuco", "piaui",
    "rio-de-janeiro", "rio-grande-do-norte", "rio-grande-do-sul", "rondonia",
    "roraima", "santa-catarina", "sao-paulo", "sergipe", "tocantins",
}


def normalize(text):
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def slugify(text):
    text = normalize(text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def is_likely_flag(filename, municipality_name, uf):
    """Check if filename looks like a municipality flag."""
    fn = normalize(filename)
    mun = normalize(municipality_name)
    mun_slug = slugify(municipality_name)

    # Must contain "bandeira" or "flag"
    if "bandeira" not in fn and "flag" not in fn:
        return False

    # Reject state flags
    for state_flag in STATE_FLAGS:
        if normalize(state_flag) in fn:
            # Unless municipality name is also in the filename
            if mun_slug not in slugify(filename):
                return False

    # Reject if filename is just a state slug
    fn_slug = slugify(filename)
    for state_slug in STATE_SLUGS:
        if fn_slug == f"bandeira-de-{state_slug}" or fn_slug == f"bandeira-do-{state_slug}":
            return False

    # Must contain some part of the municipality name
    mun_words = [w for w in mun.split() if len(w) >= 3]
    if mun_words:
        matched_words = sum(1 for w in mun_words if w in fn)
        if matched_words == 0:
            return False

    return True


def search_wikipedia_flag(name, uf):
    """Search pt.wikipedia.org for a municipality's flag image."""
    # Try article title patterns
    titles = [
        f"{name} ({uf})",
        f"{name}",
    ]

    for title in titles:
        encoded = urllib.parse.quote(title)
        url = f"https://pt.wikipedia.org/w/api.php?action=query&titles={encoded}&prop=images&imlimit=50&format=json"
        req = urllib.request.Request(url, headers={
            "User-Agent": "BandeirasmunicipiosBR/1.0 (https://github.com/nataliasm23/icones-bandeiras-br-uf) Python/3",
        })
        data = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.load(resp)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(10 * (attempt + 1))
                    continue
                break
            except Exception:
                break
        if data is None:
            continue

        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id == "-1":
                continue
            images = page.get("images", [])
            for img in images:
                img_title = img["title"].replace("File:", "").replace("Ficheiro:", "")
                if is_likely_flag(img_title, name, uf):
                    return img_title

    return None


def main():
    print("=" * 60)
    print("  TARGETED WIKIPEDIA FLAG SEARCH")
    print("=" * 60)

    missing = json.load(open(DATA_DIR / "missing-municipalities.json"))
    print(f"\n  Searching for {len(missing)} missing municipalities...")

    found = []
    not_found = []
    errors = 0

    for i, m in enumerate(missing):
        if i % 50 == 0 and i > 0:
            print(f"  Progress: {i}/{len(missing)} ({len(found)} found)")

        flag_file = search_wikipedia_flag(m["name"], m["uf"])
        if flag_file:
            found.append({
                "ibge_code": m["ibge_code"],
                "name": m["name"],
                "uf": m["uf"],
                "slug": m["slug"],
                "flag_file": flag_file,
            })
        else:
            not_found.append(m)

        time.sleep(1)  # Rate limit

    # Save results
    out_path = DATA_DIR / "wikipedia-targeted-flags.json"
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
        for f_item in found[:10]:
            print(f"    {f_item['name']:30s} ({f_item['uf']}) → {f_item['flag_file']}")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
