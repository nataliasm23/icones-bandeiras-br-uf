#!/usr/bin/env python3
"""
Fetch flag images from Portuguese Wikipedia for municipalities still missing flags.

Uses the Wikipedia API to query infobox images from pt.wikipedia.org articles.
Each Brazilian municipality has an article with an infobox containing the flag image.

Strategy:
1. Query pt.wikipedia API for each municipality article
2. Look for flag-related images in the article's images list
3. Download from Wikimedia Commons

This targets the ~1,775 municipalities NOT found via Wikidata.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import hashlib
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_FLAGS_DIR = DATA_DIR / "raw-flags"

WIKIPEDIA_API = "https://pt.wikipedia.org/w/api.php"
MAX_WORKERS = 4  # Be gentle with Wikipedia
REQUEST_DELAY = 0.5  # seconds between requests
REQUEST_TIMEOUT = 20

# Keywords that indicate a flag image
FLAG_KEYWORDS = [
    "bandeira", "flag", "bandera",
]

# Keywords to EXCLUDE (coat of arms, maps, etc.)
EXCLUDE_KEYWORDS = [
    "brasão", "brasao", "coat", "arms", "mapa", "map", "mapa",
    "localização", "localizacao", "location", "selo", "seal",
    "hino", "logo", "escudo", "shield", "panorama", "vista",
]

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


def build_article_titles(name: str, uf: str) -> list:
    """Build possible Wikipedia article titles for a municipality."""
    uf_name = UF_NAMES.get(uf, uf)
    return [
        name,                                    # e.g. "Abaetetuba"
        f"{name} ({uf_name})",                   # e.g. "Itapeva (São Paulo)"
        f"{name} ({uf})",                        # e.g. "Itapeva (SP)"
    ]


def get_article_images(title: str) -> list:
    """Query Wikipedia API for images in an article."""
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": title,
        "prop": "images",
        "imlimit": "50",
        "format": "json",
    })

    url = f"{WIKIPEDIA_API}?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "BandeirasmunicipiosBR/1.0 (https://github.com/nataliasm23/icones-bandeiras-br-uf) Python/3",
    })

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id == "-1":
                    continue
                images = page_data.get("images", [])
                return [img["title"] for img in images]
    except Exception:
        pass
    return []


def find_flag_image(images: list) -> str:
    """Find the flag image from a list of Wikipedia image titles."""
    candidates = []
    for img_title in images:
        img_lower = img_title.lower()

        # Skip excluded images
        if any(kw in img_lower for kw in EXCLUDE_KEYWORDS):
            continue

        # Check for flag keywords
        if any(kw in img_lower for kw in FLAG_KEYWORDS):
            candidates.append(img_title)

    if candidates:
        # Prefer SVG over other formats
        svg = [c for c in candidates if c.lower().endswith(".svg")]
        if svg:
            return svg[0]
        return candidates[0]

    return None


def get_commons_url(file_title: str) -> str:
    """Build Wikimedia Commons URL from a File: title."""
    # Remove "File:" or "Ficheiro:" prefix
    filename = re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", file_title)
    filename = filename.replace(" ", "_")
    md5 = hashlib.md5(filename.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{urllib.parse.quote(filename)}"


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension."""
    return Path(filename).suffix.lower()


def process_municipality(m: dict) -> dict:
    """Process a single municipality - find its flag on Wikipedia."""
    titles = build_article_titles(m["name"], m["uf"])

    for title in titles:
        images = get_article_images(title)
        if not images:
            continue

        flag_title = find_flag_image(images)
        if flag_title:
            filename = re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", flag_title)
            return {
                "ibge_code": m["ibge_code"],
                "name": m["name"],
                "uf": m["uf"],
                "found": True,
                "flag_title": flag_title,
                "flag_filename": filename,
                "flag_url": get_commons_url(flag_title),
                "wikipedia_title": title,
            }

        time.sleep(REQUEST_DELAY)

    return {
        "ibge_code": m["ibge_code"],
        "name": m["name"],
        "uf": m["uf"],
        "found": False,
    }


def download_file(url: str, dest: Path) -> tuple:
    """Download a file. Returns (success, size_or_error)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "BandeirasmunicipiosBR/1.0 Python/3",
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
            return (True, len(data))
    except Exception as e:
        return (False, str(e))


def main():
    print("=" * 60)
    print("  🇧🇷 WIKIPEDIA FLAG FINDER")
    print("=" * 60)

    # Load database
    db_path = DATA_DIR / "municipios.json"
    with open(db_path, "r", encoding="utf-8") as f:
        municipios = json.load(f)

    # Filter to those still missing flags
    missing = [m for m in municipios if m["flag_status"] != "found"]
    print(f"\n  📂 {len(missing)} municipalities still missing flags")

    if not missing:
        print("  All flags already found!")
        return

    # Process municipalities with Wikipedia API
    print(f"\n  Step 1/2: Searching Wikipedia for flag images...")
    found = []
    not_found = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_municipality, m): m for m in missing}

        with tqdm(total=len(missing), desc="  Searching Wikipedia", unit="mun") as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result["found"]:
                    found.append(result)
                else:
                    not_found.append(result)
                pbar.update(1)
                pbar.set_postfix(found=len(found), missing=len(not_found))

    # Save Wikipedia results
    wiki_results_path = DATA_DIR / "wikipedia-flags.json"
    with open(wiki_results_path, "w", encoding="utf-8") as f:
        json.dump({"found": found, "not_found": not_found}, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 Saved results to {wiki_results_path}")

    # Download found flags
    print(f"\n  Step 2/2: Downloading {len(found)} flags from Wikimedia...")
    downloaded = 0
    download_errors = []
    total_bytes = 0

    for result in tqdm(found, desc="  Downloading flags", unit="file"):
        ext = get_file_extension(result["flag_filename"])
        dest = RAW_FLAGS_DIR / result["uf"] / f"{result['ibge_code']}-{result['name'].lower().replace(' ', '-')}{ext}"

        if dest.exists() and dest.stat().st_size > 0:
            downloaded += 1
            continue

        ok, size_or_error = download_file(result["flag_url"], dest)
        if ok:
            downloaded += 1
            total_bytes += size_or_error
        else:
            download_errors.append({**result, "error": size_or_error})

        time.sleep(0.3)

    # Update main database
    found_codes = {r["ibge_code"] for r in found}
    for m in municipios:
        if m["ibge_code"] in found_codes:
            result = next(r for r in found if r["ibge_code"] == m["ibge_code"])
            m["flag_status"] = "found"
            m["flag_source"] = "wikipedia"
            m["flag_url"] = result["flag_url"]
            m["flag_file"] = result["flag_filename"]
            ext = get_file_extension(result["flag_filename"])
            m["flag_local"] = f"raw-flags/{m['uf']}/{m['ibge_code']}-{m['name'].lower().replace(' ', '-')}{ext}"

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)

    # Summary
    still_missing = sum(1 for m in municipios if m["flag_status"] != "found")
    total_found = sum(1 for m in municipios if m["flag_status"] == "found")
    pct = (total_found / len(municipios)) * 100

    mb = total_bytes / (1024 * 1024)
    print("\n" + "=" * 60)
    print("  📊 WIKIPEDIA RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Searched:              {len(missing):>6} municipalities")
    print(f"  Found on Wikipedia:    {len(found):>6}")
    print(f"  Not found:             {len(not_found):>6}")
    print(f"  Downloaded:            {downloaded:>6} ({mb:.1f} MB)")
    if download_errors:
        print(f"  Download errors:       {len(download_errors):>6}")
    print(f"  ─────────────────────────────────────")
    print(f"  🏴 Total flags (all sources): {total_found:>5} / {len(municipios)} ({pct:.1f}%)")
    print(f"  ❓ Still missing:             {still_missing:>5}")
    print("=" * 60)

    if not_found:
        print(f"\n  Still missing flags ({len(not_found)} municipalities):")
        # Group by UF
        by_uf = {}
        for r in not_found:
            by_uf.setdefault(r["uf"], []).append(r["name"])
        for uf in sorted(by_uf.keys()):
            names = by_uf[uf]
            print(f"    {uf}: {len(names)} missing")


if __name__ == "__main__":
    main()
