#!/usr/bin/env python3
"""
Fetch flag images from Brazilian prefeitura (city hall) websites.

Strategy:
- Brazilian municipal websites follow common URL patterns:
  - {slug}.{uf}.gov.br
  - www.{slug}.{uf}.gov.br
  - prefeitura{slug}.{uf}.gov.br
- They typically have a "símbolos" or "bandeira" page
- We try multiple URL patterns and look for flag images

This is the LAST RESORT scraper for municipalities not found via
Wikidata or Wikipedia.
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

REQUEST_TIMEOUT = 15
MAX_WORKERS = 4
REQUEST_DELAY = 1.0  # Be respectful to gov.br sites

UF_LOWER = {
    "RO": "ro", "AC": "ac", "AM": "am", "RR": "rr", "PA": "pa",
    "AP": "ap", "TO": "to", "MA": "ma", "PI": "pi", "CE": "ce",
    "RN": "rn", "PB": "pb", "PE": "pe", "AL": "al", "SE": "se",
    "BA": "ba", "MG": "mg", "ES": "es", "RJ": "rj", "SP": "sp",
    "PR": "pr", "SC": "sc", "RS": "rs", "MS": "ms", "MT": "mt",
    "GO": "go", "DF": "df",
}


def slugify_prefeitura(name: str) -> str:
    """Convert municipality name to prefeitura URL slug."""
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "", text.lower())
    return text


def build_prefeitura_urls(name: str, uf: str) -> list:
    """Build possible prefeitura website URLs."""
    slug = slugify_prefeitura(name)
    uf_lower = UF_LOWER.get(uf, uf.lower())

    base_urls = [
        f"https://{slug}.{uf_lower}.gov.br",
        f"https://www.{slug}.{uf_lower}.gov.br",
        f"https://prefeitura{slug}.{uf_lower}.gov.br",
        f"https://www.prefeitura{slug}.{uf_lower}.gov.br",
    ]

    # Pages where flags are typically found
    flag_pages = [
        "/simbolos",
        "/simbolos-municipais",
        "/cidade/simbolos",
        "/cidade/simbolo",
        "/municipio/simbolos",
        "/bandeira",
        "/bandeira-oficial",
        "/sobre/simbolos",
        "/a-cidade/simbolos",
        "/institucional/simbolos",
    ]

    urls = []
    for base in base_urls:
        for page in flag_pages:
            urls.append(base + page)

    return urls


def try_fetch_page(url: str) -> str:
    """Try to fetch a page. Returns HTML content or None."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BandeirasmunicipiosBR/1.0)",
        })
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            if response.status == 200:
                return response.read().decode("utf-8", errors="ignore")
    except Exception:
        pass
    return None


def find_flag_image_in_html(html: str, base_url: str) -> str:
    """Search HTML for flag image URLs."""
    # Look for <img> tags with flag-related keywords
    img_pattern = re.compile(
        r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>',
        re.IGNORECASE
    )

    for match in img_pattern.finditer(html):
        src = match.group(1)
        src_lower = src.lower()

        # Check if this is a flag image
        if any(kw in src_lower for kw in ["bandeira", "flag"]):
            # Skip tiny icons
            if any(kw in src_lower for kw in ["favicon", "icon", "thumb", "16x", "32x"]):
                continue

            # Make absolute URL
            if src.startswith("//"):
                return "https:" + src
            elif src.startswith("/"):
                parsed = urllib.parse.urlparse(base_url)
                return f"{parsed.scheme}://{parsed.netloc}{src}"
            elif src.startswith("http"):
                return src

    # Also look for <a> tags linking to flag downloads
    link_pattern = re.compile(
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>[^<]*(?:bandeira|flag)[^<]*</a>',
        re.IGNORECASE
    )

    for match in link_pattern.finditer(html):
        href = match.group(1)
        href_lower = href.lower()
        if any(ext in href_lower for ext in [".svg", ".png", ".jpg", ".jpeg", ".webp"]):
            if href.startswith("/"):
                parsed = urllib.parse.urlparse(base_url)
                return f"{parsed.scheme}://{parsed.netloc}{href}"
            elif href.startswith("http"):
                return href

    return None


def download_file(url: str, dest: Path) -> tuple:
    """Download a file. Returns (success, size_or_error)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; BandeirasmunicipiosBR/1.0)",
        })
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
            if len(data) < 500:  # Too small to be a real flag
                return (False, "File too small")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
            return (True, len(data))
    except Exception as e:
        return (False, str(e))


def process_municipality(m: dict) -> dict:
    """Try to find a flag on prefeitura website."""
    urls = build_prefeitura_urls(m["name"], m["uf"])

    for url in urls:
        html = try_fetch_page(url)
        if not html:
            continue

        flag_url = find_flag_image_in_html(html, url)
        if flag_url:
            return {
                "ibge_code": m["ibge_code"],
                "name": m["name"],
                "uf": m["uf"],
                "found": True,
                "flag_url": flag_url,
                "source_page": url,
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
    print("  🇧🇷 PREFEITURA FLAG SCRAPER")
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

    # Process municipalities
    print(f"\n  Step 1/2: Searching prefeitura websites...")
    found = []
    not_found = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_municipality, m): m for m in missing}

        with tqdm(total=len(missing), desc="  Scanning prefeituras", unit="mun") as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result["found"]:
                    found.append(result)
                else:
                    not_found.append(result)
                pbar.update(1)
                pbar.set_postfix(found=len(found), miss=len(not_found))

    # Save results
    prefeitura_results_path = DATA_DIR / "prefeitura-flags.json"
    with open(prefeitura_results_path, "w", encoding="utf-8") as f:
        json.dump({"found": found, "not_found": not_found}, f, ensure_ascii=False, indent=2)

    # Download found flags
    if found:
        print(f"\n  Step 2/2: Downloading {len(found)} flags...")
        downloaded = 0
        total_bytes = 0

        for result in tqdm(found, desc="  Downloading flags", unit="file"):
            ext_match = re.search(r'\.(svg|png|jpg|jpeg|webp|gif)(\?|$)', result["flag_url"].lower())
            ext = f".{ext_match.group(1)}" if ext_match else ".png"
            slug = slugify_prefeitura(result["name"])
            dest = RAW_FLAGS_DIR / result["uf"] / f"{result['ibge_code']}-{slug}{ext}"

            if dest.exists() and dest.stat().st_size > 0:
                downloaded += 1
                continue

            ok, size_or_error = download_file(result["flag_url"], dest)
            if ok:
                downloaded += 1
                total_bytes += size_or_error

            time.sleep(0.5)

        # Update database
        found_codes = {r["ibge_code"] for r in found}
        for m in municipios:
            if m["ibge_code"] in found_codes and m["flag_status"] != "found":
                result = next(r for r in found if r["ibge_code"] == m["ibge_code"])
                m["flag_status"] = "found"
                m["flag_source"] = "prefeitura"
                m["flag_url"] = result["flag_url"]

        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(municipios, f, ensure_ascii=False, indent=2)

        mb = total_bytes / (1024 * 1024)
        print(f"\n  💾 Downloaded {downloaded} flags ({mb:.1f} MB)")

    # Final summary
    total_found = sum(1 for m in municipios if m["flag_status"] == "found")
    still_missing = len(municipios) - total_found
    pct = (total_found / len(municipios)) * 100

    print("\n" + "=" * 60)
    print("  📊 PREFEITURA SCRAPER SUMMARY")
    print("=" * 60)
    print(f"  Searched:              {len(missing):>6} prefeitura sites")
    print(f"  Found flags:           {len(found):>6}")
    print(f"  Not found:             {len(not_found):>6}")
    print(f"  ─────────────────────────────────────")
    print(f"  🏴 Total flags (all sources): {total_found:>5} / {len(municipios)} ({pct:.1f}%)")
    print(f"  ❓ Still missing:             {still_missing:>5}")
    print("=" * 60)

    # Group remaining by UF
    if not_found:
        print(f"\n  Remaining {len(not_found)} without flags by state:")
        by_uf = {}
        for r in not_found:
            by_uf.setdefault(r["uf"], []).append(r["name"])
        for uf in sorted(by_uf.keys()):
            print(f"    {uf}: {len(by_uf[uf])}")


if __name__ == "__main__":
    main()
