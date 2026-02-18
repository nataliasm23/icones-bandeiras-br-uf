#!/usr/bin/env python3
"""
Fetch flag images from Wikimedia Commons categories.

Wikimedia Commons has organized categories like:
- "Flags of municipalities of São Paulo (state)"
- "Flags of municipalities of Minas Gerais"

This queries those categories to find flag files, then matches them
to our municipality database by name similarity.
"""

import json
import time
import re
import unicodedata
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_FLAGS_DIR = DATA_DIR / "raw-flags"

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.5

UF_NAMES_PT = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
    "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco",
    "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima",
    "SC": "Santa Catarina", "SP": "São Paulo", "SE": "Sergipe",
    "TO": "Tocantins",
}

# Category name patterns on Commons
CATEGORY_PATTERNS = [
    "Flags of municipalities of {state}",
    "Flags of municipalities in {state}",
    "Municipal flags of {state}",
    "Bandeiras de municípios de {state}",
    "Bandeiras de municípios do {state}",
    "Bandeiras de municípios da {state}",
]


def normalize(text: str) -> str:
    """Normalize text for comparison."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def get_category_members(category_name: str) -> list:
    """Get all files in a Commons category."""
    members = []
    cmcontinue = None

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category_name}",
            "cmtype": "file",
            "cmlimit": "500",
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "BandeirasmunicipiosBR/2.0 (https://github.com/nataliasm23/icones-bandeiras-br-uf) Python/3",
        })

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                data = json.loads(response.read().decode("utf-8"))
                cm = data.get("query", {}).get("categorymembers", [])
                members.extend(cm)

                cont = data.get("continue", {})
                if "cmcontinue" in cont:
                    cmcontinue = cont["cmcontinue"]
                    time.sleep(REQUEST_DELAY)
                else:
                    break
        except Exception as e:
            print(f"    Error fetching category '{category_name}': {e}")
            break

    return members


def extract_municipality_name(filename: str) -> str:
    """Try to extract municipality name from a flag filename."""
    # Common patterns:
    # "Bandeira de São Paulo.svg"
    # "Bandeira do Município de Campinas.svg"
    # "Flag of Campinas.svg"
    # "Bandeira municipal de Votuporanga.png"

    name = filename
    # Remove file extension
    name = re.sub(r"\.(svg|png|jpg|jpeg|gif|webp)$", "", name, flags=re.IGNORECASE)
    # Remove "File:" prefix
    name = re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", name)

    # Try known patterns
    patterns = [
        r"(?:Bandeira|Flag)\s+(?:de|do|da|of|del?)\s+(?:Município\s+de\s+)?(.+)",
        r"(?:Bandeira|Flag)\s+(?:municipal\s+de\s+)(.+)",
        r"(?:Bandeira|Flag)\s+(.+)",
    ]

    for pattern in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            # Remove trailing state info like " (São Paulo)" or " - SP"
            extracted = re.sub(r"\s*[\(-].*$", "", extracted)
            return extracted

    return name


def get_commons_url(filename: str) -> str:
    """Build Wikimedia Commons URL."""
    fname = filename.replace(" ", "_")
    fname = re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", fname)
    md5 = hashlib.md5(fname.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{urllib.parse.quote(fname)}"


def download_file(url: str, dest: Path) -> tuple:
    """Download a file."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "BandeirasmunicipiosBR/2.0 Python/3",
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            if len(data) < 100:
                return (False, "File too small")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
            return (True, len(data))
    except Exception as e:
        return (False, str(e))


def main():
    print("=" * 60)
    print("  🇧🇷 WIKIMEDIA COMMONS CATEGORY SCRAPER")
    print("=" * 60)

    # Load database
    db_path = DATA_DIR / "municipios.json"
    with open(db_path, "r", encoding="utf-8") as f:
        municipios = json.load(f)

    # Build lookup by normalized name + UF
    missing = [m for m in municipios if m["flag_status"] != "found"]
    print(f"\n  📂 {len(missing)} municipalities still missing flags")

    if not missing:
        print("  All flags already found!")
        return

    # Build name lookup
    by_name_uf = {}
    for m in missing:
        key = (normalize(m["name"]), m["uf"])
        by_name_uf[key] = m

    # Also build partial name lookup (first significant word)
    by_partial = {}
    for m in missing:
        words = normalize(m["name"]).split()
        for word in words:
            if len(word) >= 4:
                by_partial.setdefault((word, m["uf"]), []).append(m)

    # Search Commons categories for each state
    print(f"\n  Step 1/2: Searching Wikimedia Commons categories...")
    all_flag_files = {}  # filename -> category

    for uf, state_name in tqdm(sorted(UF_NAMES_PT.items()), desc="  Scanning categories", unit="state"):
        uf_missing = sum(1 for m in missing if m["uf"] == uf)
        if uf_missing == 0:
            continue

        for pattern in CATEGORY_PATTERNS:
            cat_name = pattern.format(state=state_name)
            members = get_category_members(cat_name)
            if members:
                for member in members:
                    title = member.get("title", "")
                    if title and any(title.lower().endswith(ext) for ext in [".svg", ".png", ".jpg", ".jpeg", ".gif"]):
                        all_flag_files[title] = {"category": cat_name, "uf": uf}
                break  # Found a working category
            time.sleep(REQUEST_DELAY)

    print(f"\n  📁 Found {len(all_flag_files)} flag files in Commons categories")

    # Match files to municipalities
    print(f"\n  Step 2/2: Matching files to municipalities...")
    matched = []
    unmatched_files = []

    for filename, info in tqdm(all_flag_files.items(), desc="  Matching names", unit="file"):
        uf = info["uf"]
        extracted_name = extract_municipality_name(filename)
        extracted_normalized = normalize(extracted_name)

        # Try exact match
        key = (extracted_normalized, uf)
        if key in by_name_uf:
            m = by_name_uf[key]
            matched.append({
                "ibge_code": m["ibge_code"],
                "name": m["name"],
                "uf": m["uf"],
                "flag_file": re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", filename),
                "flag_url": get_commons_url(filename),
                "category": info["category"],
                "matched_by": "exact",
            })
            continue

        # Try partial match
        words = extracted_normalized.split()
        found_match = False
        for word in words:
            if len(word) >= 4 and (word, uf) in by_partial:
                candidates = by_partial[(word, uf)]
                # Find best match — most words in common
                best = None
                best_score = 0
                for cand in candidates:
                    cand_norm = normalize(cand["name"])
                    common = len(set(extracted_normalized.split()) & set(cand_norm.split()))
                    if common > best_score:
                        best_score = common
                        best = cand

                if best and best_score >= 1:
                    matched.append({
                        "ibge_code": best["ibge_code"],
                        "name": best["name"],
                        "uf": best["uf"],
                        "flag_file": re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", filename),
                        "flag_url": get_commons_url(filename),
                        "category": info["category"],
                        "matched_by": f"partial ({best_score} words)",
                    })
                    found_match = True
                    break

        if not found_match:
            unmatched_files.append({
                "filename": filename,
                "extracted_name": extracted_name,
                "uf": uf,
            })

    # Deduplicate (keep first match per ibge_code)
    seen_codes = set()
    unique_matched = []
    for m in matched:
        if m["ibge_code"] not in seen_codes:
            seen_codes.add(m["ibge_code"])
            unique_matched.append(m)
    matched = unique_matched

    print(f"\n  ✅ Matched {len(matched)} flags to municipalities")
    if unmatched_files:
        print(f"  ❓ {len(unmatched_files)} files couldn't be matched")

    # Save results
    results_path = DATA_DIR / "commons-category-flags.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({
            "matched": matched,
            "unmatched_files": unmatched_files[:100],  # limit size
        }, f, ensure_ascii=False, indent=2)

    # Download and update database
    if matched:
        print(f"\n  Downloading {len(matched)} flags...")
        downloaded = 0
        total_bytes = 0
        errors = []

        for result in tqdm(matched, desc="  Downloading flags", unit="file"):
            ext = Path(result["flag_file"]).suffix.lower()
            slug = re.sub(r"[^a-z0-9-]", "", result["name"].lower().replace(" ", "-"))
            dest = RAW_FLAGS_DIR / result["uf"] / f"{result['ibge_code']}-{slug}{ext}"

            if dest.exists() and dest.stat().st_size > 0:
                downloaded += 1
                continue

            ok, size_or_error = download_file(result["flag_url"], dest)
            if ok:
                downloaded += 1
                total_bytes += size_or_error
            else:
                errors.append({**result, "error": size_or_error})

            time.sleep(0.2)

        # Update database
        matched_codes = {r["ibge_code"] for r in matched}
        for m in municipios:
            if m["ibge_code"] in matched_codes and m["flag_status"] != "found":
                result = next(r for r in matched if r["ibge_code"] == m["ibge_code"])
                m["flag_status"] = "found"
                m["flag_source"] = "commons-category"
                m["flag_url"] = result["flag_url"]
                m["flag_file"] = result["flag_file"]

        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(municipios, f, ensure_ascii=False, indent=2)

        mb = total_bytes / (1024 * 1024)
        print(f"\n  💾 Downloaded {downloaded} flags ({mb:.1f} MB)")
        if errors:
            print(f"  ⚠️  {len(errors)} download errors")

    # Summary
    total_found = sum(1 for m in municipios if m["flag_status"] == "found")
    still_missing = len(municipios) - total_found
    pct = (total_found / len(municipios)) * 100

    print("\n" + "=" * 60)
    print("  📊 COMMONS CATEGORY SUMMARY")
    print("=" * 60)
    print(f"  Categories searched:   {len(UF_NAMES_PT):>6} states")
    print(f"  Files found:           {len(all_flag_files):>6}")
    print(f"  Matched to missing:    {len(matched):>6}")
    print(f"  ─────────────────────────────────────")
    print(f"  🏴 Total flags (all sources): {total_found:>5} / {len(municipios)} ({pct:.1f}%)")
    print(f"  ❓ Still missing:             {still_missing:>5}")
    print("=" * 60)

    # Show matched examples
    if matched:
        print(f"\n  Sample matched flags:")
        for r in matched[:15]:
            print(f"    {r['name']:30s} ({r['uf']}) → {r['flag_file']}")

    # Group remaining by UF
    remaining = [m for m in municipios if m["flag_status"] != "found"]
    if remaining:
        print(f"\n  Remaining {len(remaining)} without flags by state:")
        by_uf = {}
        for m in remaining:
            by_uf.setdefault(m["uf"], []).append(m["name"])
        for uf in sorted(by_uf.keys()):
            print(f"    {uf}: {len(by_uf[uf])}")


if __name__ == "__main__":
    main()
