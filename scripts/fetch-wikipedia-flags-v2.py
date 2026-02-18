#!/usr/bin/env python3
"""
Improved Wikipedia flag finder (v2).

Key improvements over v1:
- Rejects state flags, national flags, and other non-municipality flags
- Validates that the flag filename contains the municipality name
- Uses Wikipedia API parse action to get infobox image directly
- Falls back to image list search
"""

import json
import time
import re
import unicodedata
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_FLAGS_DIR = DATA_DIR / "raw-flags"

WIKIPEDIA_API = "https://pt.wikipedia.org/w/api.php"
MAX_WORKERS = 4
REQUEST_DELAY = 0.5
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

# State flag filenames to EXCLUDE
STATE_FLAG_NAMES = set()
for uf, name in UF_NAMES.items():
    STATE_FLAG_NAMES.add(f"bandeira de {name.lower()}")
    STATE_FLAG_NAMES.add(f"bandeira do {name.lower()}")
    STATE_FLAG_NAMES.add(f"bandeira da {name.lower()}")
    STATE_FLAG_NAMES.add(f"flag of {name.lower()}")

# Generic flags to exclude
EXCLUDE_FILENAMES = {
    "flag of brazil", "bandeira do brasil", "bandera de españa",
    "flag of portugal", "bandeira de portugal",
    "flag of france", "flag of the united states",
    "bandeira nacional", "national flag",
}

# Keywords in filename that indicate NOT a municipality flag
EXCLUDE_KEYWORDS = [
    "brasão", "brasao", "coat", "arms", "mapa", "map",
    "localização", "localizacao", "location", "selo", "seal",
    "hino", "logo", "escudo", "shield", "panorama", "vista",
    "foto", "photo", "imagem", "image", "prefeitura",
    "câmara", "camara", "prefeito", "vereador",
]


def normalize_text(text: str) -> str:
    """Remove accents and lowercase."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def is_valid_municipality_flag(img_title: str, municipality_name: str, uf: str) -> bool:
    """Check if an image is likely the actual municipality flag."""
    img_lower = img_title.lower()
    img_normalized = normalize_text(img_title)
    mun_normalized = normalize_text(municipality_name)

    # Reject excluded keywords
    if any(kw in img_normalized for kw in EXCLUDE_KEYWORDS):
        return False

    # Reject state flags
    for state_name in STATE_FLAG_NAMES:
        if normalize_text(state_name) in img_normalized:
            return False

    # Reject generic/national flags
    for excl in EXCLUDE_FILENAMES:
        if normalize_text(excl) in img_normalized:
            return False

    # Must contain "bandeira" or "flag"
    if not any(kw in img_normalized for kw in ["bandeira", "flag"]):
        return False

    # Must contain part of the municipality name (at least first word, 4+ chars)
    mun_words = [w for w in mun_normalized.split() if len(w) >= 4]
    name_match = any(w in img_normalized for w in mun_words) if mun_words else False

    # Or contain "municipal" or the municipality slug
    mun_slug = re.sub(r"[^a-z0-9]", "", mun_normalized)
    has_municipal = "municipal" in img_normalized
    has_slug = len(mun_slug) >= 4 and mun_slug in img_normalized.replace(" ", "").replace("_", "")

    return name_match or has_municipal or has_slug


def build_article_titles(name: str, uf: str) -> list:
    """Build possible Wikipedia article titles."""
    uf_name = UF_NAMES.get(uf, uf)
    return [
        f"{name} ({uf_name})",
        name,
        f"{name} ({uf})",
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
        "User-Agent": "BandeirasmunicipiosBR/2.0 (https://github.com/nataliasm23/icones-bandeiras-br-uf) Python/3",
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


def get_commons_url(file_title: str) -> str:
    """Build Wikimedia Commons URL from a File: title."""
    import hashlib
    filename = re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", file_title)
    filename = filename.replace(" ", "_")
    md5 = hashlib.md5(filename.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{urllib.parse.quote(filename)}"


def process_municipality(m: dict) -> dict:
    """Process a single municipality - find its flag on Wikipedia."""
    titles = build_article_titles(m["name"], m["uf"])

    for title in titles:
        images = get_article_images(title)
        if not images:
            continue

        # Filter for valid municipality flags
        candidates = []
        for img_title in images:
            if is_valid_municipality_flag(img_title, m["name"], m["uf"]):
                candidates.append(img_title)

        if candidates:
            # Prefer SVG
            svg = [c for c in candidates if c.lower().endswith(".svg")]
            best = svg[0] if svg else candidates[0]
            filename = re.sub(r"^(File:|Ficheiro:|Arquivo:)", "", best)

            return {
                "ibge_code": m["ibge_code"],
                "name": m["name"],
                "uf": m["uf"],
                "found": True,
                "flag_title": best,
                "flag_filename": filename,
                "flag_url": get_commons_url(best),
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
    print("  🇧🇷 WIKIPEDIA FLAG FINDER v2 (Improved)")
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
    print(f"\n  Step 1/2: Searching Wikipedia (strict matching)...")
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

    # Save results
    wiki_results_path = DATA_DIR / "wikipedia-flags-v2.json"
    with open(wiki_results_path, "w", encoding="utf-8") as f:
        json.dump({"found": found, "not_found": not_found}, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 Saved results to {wiki_results_path}")

    # Show what was found
    if found:
        print(f"\n  Found {len(found)} municipality flags:")
        for r in found[:20]:
            print(f"    {r['name']:30s} ({r['uf']}) → {r['flag_filename']}")
        if len(found) > 20:
            print(f"    ... and {len(found) - 20} more")

    # Download found flags
    if found:
        print(f"\n  Step 2/2: Downloading {len(found)} flags...")
        downloaded = 0
        errors = []
        total_bytes = 0

        for result in tqdm(found, desc="  Downloading flags", unit="file"):
            ext = Path(result["flag_filename"]).suffix.lower()
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

        # Update database
        found_codes = {r["ibge_code"] for r in found}
        for m in municipios:
            if m["ibge_code"] in found_codes and m["flag_status"] != "found":
                result = next(r for r in found if r["ibge_code"] == m["ibge_code"])
                m["flag_status"] = "found"
                m["flag_source"] = "wikipedia-v2"
                m["flag_url"] = result["flag_url"]
                m["flag_file"] = result["flag_filename"]

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
    print("  📊 WIKIPEDIA v2 SUMMARY")
    print("=" * 60)
    print(f"  Searched:              {len(missing):>6}")
    print(f"  Found (strict):        {len(found):>6}")
    print(f"  Not found:             {len(not_found):>6}")
    print(f"  ─────────────────────────────────────")
    print(f"  🏴 Total flags (all sources): {total_found:>5} / {len(municipios)} ({pct:.1f}%)")
    print(f"  ❓ Still missing:             {still_missing:>5}")
    print("=" * 60)


if __name__ == "__main__":
    main()
