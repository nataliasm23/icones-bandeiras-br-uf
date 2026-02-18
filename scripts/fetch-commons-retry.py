#!/usr/bin/env python3
"""
Retry Wikimedia Commons category scraper for states missed due to 429 errors.

Uses longer delays and individual requests (no threading) to avoid rate limits.
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
REQUEST_DELAY = 2.0  # Longer delay to avoid 429s

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

CATEGORY_PATTERNS = [
    "Flags of municipalities of {state}",
    "Flags of municipalities in {state}",
    "Flags of municipalities of {state} (state)",
    "Municipal flags of {state}",
    "Bandeiras de municípios de {state}",
    "Bandeiras de municípios do {state}",
    "Bandeiras de municípios da {state}",
    "Flags of cities in {state}",
    "Flags of cities of {state}",
]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def get_category_members(category_name: str, max_retries: int = 3) -> list:
    """Get all files in a Commons category with retry."""
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

        for attempt in range(max_retries):
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
                    else:
                        return members
                    break  # Success, go to next page
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = REQUEST_DELAY * (attempt + 2)
                    print(f"      429 rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    return members
            except Exception:
                time.sleep(REQUEST_DELAY)

        time.sleep(REQUEST_DELAY)

    return members


def extract_municipality_name(filename: str) -> str:
    """Try to extract municipality name from a flag filename."""
    name = filename
    name = re.sub(r"\.(svg|png|jpg|jpeg|gif|webp)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", name)

    patterns = [
        r"(?:Bandeira|Flag)\s+(?:de|do|da|of|del?)\s+(?:Município\s+de\s+)?(.+)",
        r"(?:Bandeira|Flag)\s+(?:municipal\s+de\s+)(.+)",
        r"(?:Bandeira|Flag)\s+(.+)",
    ]

    for pattern in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            extracted = re.sub(r"\s*[\(-].*$", "", extracted)
            return extracted

    return name


def get_commons_url(filename: str) -> str:
    fname = filename.replace(" ", "_")
    fname = re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", fname)
    md5 = hashlib.md5(fname.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{urllib.parse.quote(fname)}"


def download_file(url: str, dest: Path) -> tuple:
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
    print("  🇧🇷 COMMONS CATEGORY SCRAPER (RETRY)")
    print("=" * 60)

    db_path = DATA_DIR / "municipios.json"
    with open(db_path, "r", encoding="utf-8") as f:
        municipios = json.load(f)

    missing = [m for m in municipios if m["flag_status"] != "found"]
    print(f"\n  📂 {len(missing)} municipalities still missing flags")

    if not missing:
        print("  All flags already found!")
        return

    # Build lookup
    by_name_uf = {}
    for m in missing:
        key = (normalize(m["name"]), m["uf"])
        by_name_uf[key] = m

    by_partial = {}
    for m in missing:
        words = normalize(m["name"]).split()
        for word in words:
            if len(word) >= 4:
                by_partial.setdefault((word, m["uf"]), []).append(m)

    # Check which states already have Commons data
    existing_path = DATA_DIR / "commons-category-flags.json"
    already_covered = set()
    if existing_path.exists():
        with open(existing_path) as f:
            existing = json.load(f)
        for m in existing.get("matched", []):
            already_covered.add(m["uf"])

    # Only search states that still have missing municipalities
    states_to_search = set()
    for m in missing:
        states_to_search.add(m["uf"])

    # Remove already-covered states (unless they still have many missing)
    # Actually let's search ALL states with missing municipalities
    print(f"\n  States to search: {sorted(states_to_search)}")
    print(f"  Already covered: {sorted(already_covered)}")

    # Search
    print(f"\n  Step 1/2: Searching Wikimedia Commons categories...")
    all_flag_files = {}

    for uf in tqdm(sorted(states_to_search), desc="  Scanning categories", unit="state"):
        state_name = UF_NAMES_PT.get(uf, uf)
        uf_missing = sum(1 for m in missing if m["uf"] == uf)

        found_category = False
        for pattern in CATEGORY_PATTERNS:
            cat_name = pattern.format(state=state_name)
            time.sleep(REQUEST_DELAY)  # Be respectful
            members = get_category_members(cat_name)
            if members:
                print(f"    {uf}: Found {len(members)} files in '{cat_name}'")
                for member in members:
                    title = member.get("title", "")
                    if title and any(title.lower().endswith(ext) for ext in [".svg", ".png", ".jpg", ".jpeg", ".gif"]):
                        all_flag_files[title] = {"category": cat_name, "uf": uf}
                found_category = True
                break

        if not found_category:
            print(f"    {uf}: No category found ({uf_missing} missing)")

    print(f"\n  📁 Found {len(all_flag_files)} flag files total")

    # Match
    print(f"\n  Step 2/2: Matching files to municipalities...")
    matched = []
    unmatched_files = []

    for filename, info in all_flag_files.items():
        uf = info["uf"]
        extracted_name = extract_municipality_name(filename)
        extracted_normalized = normalize(extracted_name)

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

        words = extracted_normalized.split()
        found_match = False
        for word in words:
            if len(word) >= 4 and (word, uf) in by_partial:
                candidates = by_partial[(word, uf)]
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
                        "matched_by": f"partial ({best_score})",
                    })
                    found_match = True
                    break
        if not found_match:
            unmatched_files.append({"filename": filename, "extracted_name": extracted_name, "uf": uf})

    # Deduplicate
    seen = set()
    unique = []
    for m in matched:
        if m["ibge_code"] not in seen:
            seen.add(m["ibge_code"])
            unique.append(m)
    matched = unique

    print(f"\n  ✅ Matched {len(matched)} flags")

    # Save
    results_path = DATA_DIR / "commons-retry-flags.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump({"matched": matched, "unmatched": unmatched_files[:100]}, f, ensure_ascii=False, indent=2)

    # Download and update
    if matched:
        print(f"\n  Downloading {len(matched)} flags...")
        downloaded = 0
        total_bytes = 0
        errors = []

        for result in tqdm(matched, desc="  Downloading", unit="file"):
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
            time.sleep(0.3)

        matched_codes = {r["ibge_code"] for r in matched}
        for m in municipios:
            if m["ibge_code"] in matched_codes and m["flag_status"] != "found":
                result = next(r for r in matched if r["ibge_code"] == m["ibge_code"])
                m["flag_status"] = "found"
                m["flag_source"] = "commons-retry"
                m["flag_url"] = result["flag_url"]
                m["flag_file"] = result["flag_file"]

        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(municipios, f, ensure_ascii=False, indent=2)

        mb = total_bytes / (1024 * 1024)
        print(f"\n  💾 Downloaded {downloaded} flags ({mb:.1f} MB)")

    # Summary
    total_found = sum(1 for m in municipios if m["flag_status"] == "found")
    still_missing = len(municipios) - total_found
    pct = (total_found / len(municipios)) * 100

    print("\n" + "=" * 60)
    print("  📊 COMMONS RETRY SUMMARY")
    print("=" * 60)
    print(f"  New flags found:       {len(matched):>6}")
    print(f"  Unmatched files:       {len(unmatched_files):>6}")
    print(f"  ─────────────────────────────────────")
    print(f"  🏴 Total flags (all sources): {total_found:>5} / {len(municipios)} ({pct:.1f}%)")
    print(f"  ❓ Still missing:             {still_missing:>5}")
    print("=" * 60)

    if matched:
        print(f"\n  Sample new flags:")
        for r in matched[:15]:
            print(f"    {r['name']:30s} ({r['uf']}) → {r['flag_file']}")


if __name__ == "__main__":
    main()
