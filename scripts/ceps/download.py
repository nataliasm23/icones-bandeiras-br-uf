#!/usr/bin/env python3
"""
download.py  (was 01-download-bulk.py)
──────────────────────────────────────
Downloads CEP datasets from open sources and merges them into a single CSV.

Sources:
  1. thiamsantos/cep-databases — ~994K rows (gzip CSV)
  2. neves/cep                — ~643K rows (bzip2 CSV)
  3. kelvins/municipios-brasileiros — municipality metadata (IBGE codes, DDD)

Output:
  data/merged/ceps-bulk.csv
  Columns: cep, logradouro, complemento, bairro, localidade, uf, ibge, ddd, source
"""

from __future__ import annotations

import bz2
import csv
import gzip
import io
import logging
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

from config import (
    DATA_DIR,
    MERGED_DIR,
    UF_NAMES,
    get_uf_from_cep,
)

log = logging.getLogger(__name__)

# ── constants ───────────────────────────────────────────────────────────────
RAW_DIR = DATA_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Source 1: thiamsantos/cep-databases (~994K CEPs)
THIAMSANTOS_URL = "https://cdn.jsdelivr.net/gh/thiamsantos/cep-databases@master/final.csv.gz"
THIAMSANTOS_FILE = RAW_DIR / "thiamsantos_final.csv.gz"

# Source 2: neves/cep (~643K CEPs)
NEVES_URL = "https://cdn.jsdelivr.net/gh/neves/cep@master/cep.csv.bz2"
NEVES_FILE = RAW_DIR / "neves_cep.csv.bz2"

# Supplementary: kelvins/municipios-brasileiros (IBGE codes + DDD)
KELVINS_URL = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
KELVINS_FILE = RAW_DIR / "kelvins_municipios.csv"

OUTPUT_FILE = MERGED_DIR / "ceps-bulk.csv"

OUTPUT_COLUMNS = [
    "cep",
    "logradouro",
    "complemento",
    "bairro",
    "localidade",
    "uf",
    "ibge",
    "ddd",
    "source",
]

# Map UF code number -> UF abbreviation (for kelvins join)
CODIGO_UF_MAP = {
    11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO",
    21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP",
    41: "PR", 42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF",
}

MAX_RETRIES = 3
RETRY_BACKOFF = 2
REQUEST_TIMEOUT = 120
CHUNK_SIZE = 1024 * 64


# ── helpers ─────────────────────────────────────────────────────────────────

def _normalize_cep(raw: str) -> str | None:
    """Return an 8-digit CEP string or None if invalid."""
    cleaned = raw.strip().replace("-", "").replace(".", "").replace(" ", "")
    if len(cleaned) == 8 and cleaned.isdigit():
        return cleaned
    if cleaned.isdigit() and 1 <= len(cleaned) < 8:
        return cleaned.zfill(8)
    return None


def _download(url: str, dest: Path, *, description: str = "") -> Path:
    """Download url to dest with retries."""
    desc = description or url
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info("GET %s  (attempt %d/%d)", url, attempt, MAX_RETRIES)
            resp = requests.get(
                url,
                timeout=REQUEST_TIMEOUT,
                stream=True,
                headers={"User-Agent": "ceps-br-pipeline/1.0"},
            )
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0)) or None
            with (
                open(dest, "wb") as fh,
                tqdm(total=total, unit="B", unit_scale=True, desc=desc, leave=False) as pbar,
            ):
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    fh.write(chunk)
                    pbar.update(len(chunk))

            size_mb = dest.stat().st_size / (1024 * 1024)
            log.info("  -> saved %s (%.1f MB)", dest.name, size_mb)
            return dest

        except (requests.RequestException, IOError) as exc:
            log.warning("  attempt %d failed: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF * (2 ** (attempt - 1))
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to download {url} after {MAX_RETRIES} attempts") from exc

    raise RuntimeError(f"Failed to download {url}")


# ── municipality metadata (IBGE + DDD) ─────────────────────────────────────

def load_municipio_metadata() -> dict[str, dict]:
    """Download and parse kelvins/municipios-brasileiros for IBGE code + DDD."""
    try:
        _download(KELVINS_URL, KELVINS_FILE, description="kelvins/municipios")
    except RuntimeError:
        log.warning("Could not download municipality metadata — IBGE/DDD enrichment disabled")
        return {}

    import unicodedata

    def _normalize_name(name: str) -> str:
        nfkd = unicodedata.normalize("NFKD", name)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

    lookup: dict[str, dict] = {}
    with open(KELVINS_FILE, encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            ibge = (row.get("codigo_ibge") or "").strip()
            nome = (row.get("nome") or "").strip()
            codigo_uf = int(row.get("codigo_uf", 0))
            ddd = (row.get("ddd") or "").strip()
            uf = CODIGO_UF_MAP.get(codigo_uf, "")

            if nome and uf:
                key = f"{_normalize_name(nome)}|{uf}"
                lookup[key] = {"ibge": ibge, "ddd": ddd}

    log.info("Municipality metadata loaded: %d entries", len(lookup))
    return lookup


def _enrich_ibge_ddd(row: dict, mun_lookup: dict[str, dict]) -> dict:
    """Try to fill ibge/ddd from municipality lookup if missing."""
    if row.get("ibge") and row.get("ddd"):
        return row

    import unicodedata

    def _normalize_name(name: str) -> str:
        nfkd = unicodedata.normalize("NFKD", name)
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

    city = row.get("localidade", "")
    uf = row.get("uf", "")
    if city and uf:
        key = f"{_normalize_name(city)}|{uf}"
        meta = mun_lookup.get(key)
        if meta:
            if not row.get("ibge"):
                row["ibge"] = meta["ibge"]
            if not row.get("ddd"):
                row["ddd"] = meta["ddd"]

    return row


# ── source 1: thiamsantos/cep-databases ─────────────────────────────────────

def download_and_parse_thiamsantos(mun_lookup: dict[str, dict]) -> list[dict]:
    """Download and parse thiamsantos/cep-databases final.csv.gz."""
    _download(THIAMSANTOS_URL, THIAMSANTOS_FILE, description="thiamsantos/cep-databases")

    rows: list[dict] = []
    log.info("Parsing thiamsantos CSV.GZ ...")

    with gzip.open(THIAMSANTOS_FILE, "rt", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh)
        for parts in tqdm(reader, desc="thiamsantos parse", unit=" rows", leave=False):
            if len(parts) < 6:
                continue

            cep = _normalize_cep(parts[0])
            if cep is None:
                continue

            logradouro = parts[1].strip()
            bairro = parts[2].strip()
            localidade = parts[3].strip()
            uf = parts[5].strip().upper()

            if len(uf) != 2 or uf not in UF_NAMES:
                uf = get_uf_from_cep(cep) or ""

            row = {
                "cep": cep,
                "logradouro": logradouro,
                "complemento": "",
                "bairro": bairro,
                "localidade": localidade,
                "uf": uf,
                "ibge": "",
                "ddd": "",
                "source": "thiamsantos",
            }
            row = _enrich_ibge_ddd(row, mun_lookup)
            rows.append(row)

    log.info("thiamsantos: %d rows parsed", len(rows))
    return rows


# ── source 2: neves/cep ─────────────────────────────────────────────────────

def download_and_parse_neves(mun_lookup: dict[str, dict]) -> list[dict]:
    """Download and parse neves/cep cep.csv.bz2."""
    _download(NEVES_URL, NEVES_FILE, description="neves/cep")

    rows: list[dict] = []
    log.info("Parsing neves CSV.BZ2 ...")

    with bz2.open(NEVES_FILE, "rt", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for record in tqdm(reader, desc="neves parse", unit=" rows", leave=False):
            raw_cep = (record.get("cep") or "").strip()
            cep = _normalize_cep(raw_cep)
            if cep is None:
                continue

            uf = (record.get("uf") or "").strip().upper()
            if len(uf) != 2 or uf not in UF_NAMES:
                uf = get_uf_from_cep(cep) or ""

            cidade = (record.get("cidade") or "").strip()
            logradouro_name = (record.get("logradouro") or "").strip()
            tipo = (record.get("tipo_logradouro") or "").strip()
            bairro = (record.get("bairro") or "").strip()

            if tipo and logradouro_name:
                logradouro = f"{tipo} {logradouro_name}"
            else:
                logradouro = logradouro_name or tipo

            row = {
                "cep": cep,
                "logradouro": logradouro,
                "complemento": "",
                "bairro": bairro,
                "localidade": cidade,
                "uf": uf,
                "ibge": "",
                "ddd": "",
                "source": "neves",
            }
            row = _enrich_ibge_ddd(row, mun_lookup)
            rows.append(row)

    log.info("neves: %d rows parsed", len(rows))
    return rows


# ── merge & write ───────────────────────────────────────────────────────────

def merge_and_write(all_rows: list[dict]) -> Path:
    """Deduplicate by CEP (prefer the most complete row) and write the CSV."""
    log.info("Merging %d total rows …", len(all_rows))

    best: dict[str, dict] = {}
    for row in all_rows:
        cep = row["cep"]
        if cep not in best:
            best[cep] = row
        else:
            existing_score = sum(1 for k, v in best[cep].items() if v and k != "source")
            new_score = sum(1 for k, v in row.items() if v and k != "source")
            if new_score > existing_score:
                best[cep] = row

    merged = sorted(best.values(), key=lambda r: r["cep"])
    log.info("Unique CEPs after merge: %d", len(merged))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(merged)

    size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    log.info("Written %s  (%.1f MB, %d rows)", OUTPUT_FILE, size_mb, len(merged))
    return OUTPUT_FILE


# ── run ────────────────────────────────────────────────────────────────────

def run(*, dry_run: bool = False) -> None:
    log.info("=" * 60)
    log.info("CEP bulk download & merge pipeline")
    log.info("=" * 60)

    if dry_run:
        log.info("[DRY-RUN] Would download from:")
        log.info("  1. %s", THIAMSANTOS_URL)
        log.info("  2. %s", NEVES_URL)
        log.info("  3. %s (municipality metadata)", KELVINS_URL)
        log.info("[DRY-RUN] Output would be written to: %s", OUTPUT_FILE)
        return

    # Load municipality metadata first (for IBGE/DDD enrichment)
    mun_lookup = load_municipio_metadata()

    all_rows: list[dict] = []
    errors: list[str] = []

    try:
        all_rows.extend(download_and_parse_thiamsantos(mun_lookup))
    except Exception as exc:
        msg = f"thiamsantos failed: {exc}"
        log.error(msg)
        errors.append(msg)

    try:
        all_rows.extend(download_and_parse_neves(mun_lookup))
    except Exception as exc:
        msg = f"neves/cep failed: {exc}"
        log.error(msg)
        errors.append(msg)

    if not all_rows:
        log.error("No data collected from any source — aborting.")
        sys.exit(1)

    output = merge_and_write(all_rows)

    log.info("=" * 60)
    log.info("DONE  ->  %s", output)
    if errors:
        log.warning("Finished with %d source error(s):", len(errors))
        for e in errors:
            log.warning("  • %s", e)
    else:
        log.info("All sources downloaded and merged successfully.")
    log.info("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    run()
