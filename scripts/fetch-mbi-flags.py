#!/usr/bin/env python3
"""
Scrape mbi.com.br/simbolopedia for municipality flag thumbnails.

While the thumbnails are small (67x45px), they serve as a reference
to confirm which municipalities HAVE flags. We can then try to find
the actual flag files on Wikipedia/Commons for those municipalities.
"""

import json
import re
import time
import urllib.request
import urllib.parse
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

UF_NAMES = {
    "AC": "acre", "AL": "alagoas", "AM": "amazonas", "AP": "amapa",
    "BA": "bahia", "CE": "ceara", "DF": "distrito-federal", "ES": "espirito-santo",
    "GO": "goias", "MA": "maranhao", "MG": "minas-gerais", "MS": "mato-grosso-do-sul",
    "MT": "mato-grosso", "PA": "para", "PB": "paraiba", "PE": "pernambuco",
    "PI": "piaui", "PR": "parana", "RJ": "rio-de-janeiro", "RN": "rio-grande-do-norte",
    "RO": "rondonia", "RR": "roraima", "RS": "rio-grande-do-sul", "SC": "santa-catarina",
    "SE": "sergipe", "SP": "sao-paulo", "TO": "tocantins",
}

def normalize(name):
    """Normalize municipality name for matching."""
    import unicodedata
    name = unicodedata.normalize("NFD", name.lower())
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = re.sub(r"[^a-z0-9]", "", name)
    return name


def scrape_state_page(uf, state_name):
    """Scrape MBI state page for municipality flag image URLs."""
    url = f"https://www.mbi.com.br/mbi/biblioteca/simbolopedia/municipios-estado-{state_name}-br/"
    req = urllib.request.Request(url, headers={
        "User-Agent": "BandeirasmunicipiosBR/1.0 Python/3",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"  Error fetching {uf}: {e}")
        return []

    # Extract all bandeira image URLs
    pattern = r'src="(/mbi/files/media/image/simbolopedia/municipio-([^"]*)-bandeira-mini-([^"]*?)\.jpg)"'
    matches = re.findall(pattern, html)

    results = []
    for full_path, slug, code_part in matches:
        results.append({
            "slug": slug,
            "img_url": f"https://www.mbi.com.br{full_path}",
            "code_part": code_part,
        })

    return results


def main():
    print("=" * 60)
    print("  MBI SIMBOLOPEDIA SCRAPER")
    print("=" * 60)

    # Load missing municipalities
    missing = json.load(open(DATA_DIR / "missing-municipalities.json"))
    missing_by_uf = {}
    for m in missing:
        missing_by_uf.setdefault(m["uf"], []).append(m)

    print(f"\n  Missing municipalities: {len(missing)}")

    # Only scrape states that have missing municipalities
    ufs_to_scrape = sorted(missing_by_uf.keys())
    print(f"  States to scrape: {len(ufs_to_scrape)}")

    all_found = []
    total_mbi = 0

    for uf in ufs_to_scrape:
        state_name = UF_NAMES[uf]
        print(f"\n  {uf} ({state_name}): {len(missing_by_uf[uf])} missing...")
        time.sleep(1)  # Be nice

        mbi_entries = scrape_state_page(uf, state_name)
        total_mbi += len(mbi_entries)

        if not mbi_entries:
            print(f"    No entries found")
            continue

        # Build lookup by normalized slug
        mbi_by_slug = {}
        for entry in mbi_entries:
            norm = normalize(entry["slug"])
            mbi_by_slug[norm] = entry

        # Match missing municipalities
        matched = 0
        for m in missing_by_uf[uf]:
            norm_name = normalize(m["name"])
            norm_slug = normalize(m["slug"])

            # Try exact slug match
            if norm_slug in mbi_by_slug:
                entry = mbi_by_slug[norm_slug]
                all_found.append({
                    "ibge_code": m["ibge_code"],
                    "name": m["name"],
                    "uf": uf,
                    "slug": m["slug"],
                    "mbi_slug": entry["slug"],
                    "mbi_img": entry["img_url"],
                })
                matched += 1
                continue

            # Try name match
            if norm_name in mbi_by_slug:
                entry = mbi_by_slug[norm_name]
                all_found.append({
                    "ibge_code": m["ibge_code"],
                    "name": m["name"],
                    "uf": uf,
                    "slug": m["slug"],
                    "mbi_slug": entry["slug"],
                    "mbi_img": entry["img_url"],
                })
                matched += 1
                continue

            # Try partial match (at least 80% of slug chars match)
            for mbi_norm, entry in mbi_by_slug.items():
                if len(norm_slug) > 4 and (norm_slug in mbi_norm or mbi_norm in norm_slug):
                    all_found.append({
                        "ibge_code": m["ibge_code"],
                        "name": m["name"],
                        "uf": uf,
                        "slug": m["slug"],
                        "mbi_slug": entry["slug"],
                        "mbi_img": entry["img_url"],
                        "match": "partial",
                    })
                    matched += 1
                    break

        print(f"    MBI entries: {len(mbi_entries)}, Matched: {matched}/{len(missing_by_uf[uf])}")

    # Save results
    out_path = DATA_DIR / "mbi-flags.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_found, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  RESULTS")
    print(f"{'=' * 60}")
    print(f"  Total MBI entries scraped: {total_mbi}")
    print(f"  Missing municipalities matched: {len(all_found)}/{len(missing)}")
    print(f"  Saved to: {out_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
