#!/usr/bin/env python3
"""
Download all found flag images from Wikimedia Commons.

Reads data/municipios.json for entries with flag_status=found,
downloads the original files organized by UF into data/raw-flags/{UF}/.
"""

import json
import os
import time
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_FLAGS_DIR = DATA_DIR / "raw-flags"

# Wikimedia Commons file URL pattern
# Special:FilePath redirects, but we can build the direct thumb/original URL
# https://upload.wikimedia.org/wikipedia/commons/{hash1}/{hash12}/Filename
# where hash = md5(filename), hash1 = hash[0], hash12 = hash[0:2]

MAX_WORKERS = 3  # Reduced to avoid 429 rate limiting
RETRY_COUNT = 5
RETRY_DELAY = 5  # seconds between retries
REQUEST_TIMEOUT = 30  # seconds


def get_commons_direct_url(filename: str) -> str:
    """Build the direct Wikimedia Commons URL for a file."""
    # Wikimedia uses MD5 hash of the filename for directory structure
    # Filename as used in URL (spaces → underscores)
    fname = filename.replace(" ", "_")
    md5 = hashlib.md5(fname.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{md5[0]}/{md5[0:2]}/{urllib.parse.quote(fname)}"


def get_file_extension(filename: str) -> str:
    """Get lowercase file extension."""
    return Path(filename).suffix.lower()


def download_file(url: str, dest: Path, retries: int = RETRY_COUNT) -> tuple:
    """Download a file with retries. Returns (success, dest, error_msg)."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "BandeirasmunicipiosBR/1.0 (https://github.com/nataliasm23/icones-bandeiras-br-uf) Python/3",
            })
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                data = response.read()
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(data)
                return (True, dest, len(data))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return (False, dest, f"404 Not Found")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                return (False, dest, f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                return (False, dest, str(e))
    return (False, dest, "Max retries exceeded")


def main():
    print("=" * 60)
    print("  🇧🇷 WIKIMEDIA COMMONS FLAG DOWNLOADER")
    print("=" * 60)

    # Load database
    db_path = DATA_DIR / "municipios.json"
    with open(db_path, "r", encoding="utf-8") as f:
        municipios = json.load(f)

    # Filter to those with flags found
    to_download = [m for m in municipios if m["flag_status"] == "found" and m.get("flag_file")]
    print(f"\n  📂 {len(to_download)} flags to download out of {len(municipios)} municipalities")

    # Skip already downloaded
    already_done = 0
    pending = []
    for m in to_download:
        uf = m["uf"]
        slug = m["slug"]
        ext = get_file_extension(m["flag_file"])
        dest = RAW_FLAGS_DIR / uf / f"{m['ibge_code']}-{slug}{ext}"
        if dest.exists() and dest.stat().st_size > 0:
            already_done += 1
        else:
            pending.append((m, dest))

    print(f"  ✅ Already downloaded: {already_done}")
    print(f"  ⏳ Pending download:   {len(pending)}")

    if not pending:
        print("\n  Nothing to download!")
        return

    # Prepare download tasks
    tasks = []
    for m, dest in pending:
        url = get_commons_direct_url(m["flag_file"])
        tasks.append((m, url, dest))

    # Download with thread pool and progress bar
    success_count = 0
    fail_count = 0
    total_bytes = 0
    errors = []

    print(f"\n  Downloading {len(tasks)} flags with {MAX_WORKERS} workers...\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_task = {}
        for m, url, dest in tasks:
            future = executor.submit(download_file, url, dest)
            future_to_task[future] = (m, url, dest)

        with tqdm(total=len(tasks), desc="  Downloading flags", unit="file",
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]") as pbar:
            for future in as_completed(future_to_task):
                m, url, dest = future_to_task[future]
                ok, path, result = future.result()
                if ok:
                    success_count += 1
                    total_bytes += result
                else:
                    fail_count += 1
                    errors.append({
                        "name": m["name"],
                        "uf": m["uf"],
                        "ibge_code": m["ibge_code"],
                        "url": url,
                        "error": result,
                    })
                pbar.update(1)
                pbar.set_postfix(ok=success_count, fail=fail_count)

    # Update database with download status
    downloaded_set = set()
    for m, url, dest in tasks:
        if dest.exists() and dest.stat().st_size > 0:
            downloaded_set.add(m["ibge_code"])

    for m in municipios:
        if m["ibge_code"] in downloaded_set:
            uf = m["uf"]
            slug = m["slug"]
            ext = get_file_extension(m["flag_file"])
            m["flag_local"] = f"raw-flags/{uf}/{m['ibge_code']}-{slug}{ext}"

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)

    # Save errors
    if errors:
        errors_path = DATA_DIR / "download-errors.json"
        with open(errors_path, "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)

    # Count file types
    ext_counts = {}
    for m, dest in [(m, d) for m, d in [(m, RAW_FLAGS_DIR / m["uf"] / f"{m['ibge_code']}-{m['slug']}{get_file_extension(m['flag_file'])}")
                                         for m in to_download] if d.exists()]:
        ext = get_file_extension(m["flag_file"])
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    # Print summary
    mb = total_bytes / (1024 * 1024)
    print("\n" + "=" * 60)
    print("  📊 DOWNLOAD SUMMARY")
    print("=" * 60)
    print(f"  ✅ Downloaded:      {success_count:>6} files ({mb:.1f} MB)")
    print(f"  ⏭️  Already cached:  {already_done:>6} files")
    print(f"  ❌ Failed:          {fail_count:>6} files")
    print(f"  ─────────────────────────────────────")
    print(f"  📁 Total on disk:   {success_count + already_done:>6} files")
    print(f"\n  File types:")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        print(f"    {ext:8s} {count:>5}")
    if errors:
        print(f"\n  ⚠️  {len(errors)} errors saved to data/download-errors.json")
        print(f"  First 5 errors:")
        for e in errors[:5]:
            print(f"    {e['name']:25s} ({e['uf']}) → {e['error']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
