#!/usr/bin/env python3
"""
scrape.py  (was 02-scrape-viacep.py)
────────────────────────────────────
Enriquece CEPs existentes com ibge/ddd via consulta individual ao ViaCEP,
e também busca novos CEPs por endereço usando o endpoint de busca.

Fase A: Consulta individual GET /ws/{cep}/json/ para CEPs sem ibge/ddd
Fase B: Busca por município GET /ws/{UF}/{cidade}/{logradouro}/json/ para novos CEPs

Resultados salvos em data/viacep/viacep-all.csv (resumível via checkpoint).
"""

import csv
import json
import logging
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

from _fetch import create_session
from config import (
    CHECKPOINT_DIR,
    DATA_DIR,
    MERGED_DIR,
    MUNICIPIOS_JSON,
    REQUEST_TIMEOUT,
    VIACEP_BASE_URL,
    VIACEP_DELAY_SECONDS,
)

log = logging.getLogger(__name__)

VIACEP_DIR = DATA_DIR / "viacep"
VIACEP_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = VIACEP_DIR / "viacep-all.csv"
CHECKPOINT_FILE = CHECKPOINT_DIR / "viacep_progress.json"
INPUT_CSV = MERGED_DIR / "ceps-validated.csv"

CSV_COLUMNS = ["cep", "logradouro", "complemento", "bairro", "localidade", "uf", "ibge", "ddd", "source"]

# Common logradouro prefixes for address search (Phase B)
LOGRADOURO_PREFIXES = ["Rua", "Avenida", "Travessa", "Alameda", "Praça"]

MAX_RETRIES = 3
INITIAL_BACKOFF = 2


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"enriched_ceps": [], "searched_cities": []}


def save_checkpoint(data: dict) -> None:
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# ---------------------------------------------------------------------------
# ViaCEP request helpers (scrape-specific — address search not in _fetch)
# ---------------------------------------------------------------------------

def fetch_cep(cep: str, session: requests.Session) -> dict | None:
    """Consulta individual: GET /ws/{cep}/json/"""
    url = f"{VIACEP_BASE_URL}/{cep}/json/"
    backoff = INITIAL_BACKOFF

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and not data.get("erro"):
                    return data
                return None
            if resp.status_code in (400, 404):
                return None
            if resp.status_code == 429:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except requests.exceptions.RequestException:
            if attempt < MAX_RETRIES:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
            else:
                return None

    return None


def fetch_address_search(uf: str, cidade: str, logradouro: str, session: requests.Session) -> list[dict]:
    """Busca por endereço: GET /ws/{UF}/{cidade}/{logradouro}/json/"""
    url = f"{VIACEP_BASE_URL}/{uf}/{cidade}/{logradouro}/json/"
    backoff = INITIAL_BACKOFF

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data
                return []
            if resp.status_code in (400, 404):
                return []
            if resp.status_code == 429:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
        except requests.exceptions.RequestException:
            if attempt < MAX_RETRIES:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
            else:
                return []

    return []


# ---------------------------------------------------------------------------
# Phase A: Enrich existing CEPs missing ibge/ddd
# ---------------------------------------------------------------------------

def phase_a_enrich(session: requests.Session, checkpoint: dict) -> list[dict]:
    """Look up CEPs missing ibge/ddd via individual ViaCEP queries."""
    if not INPUT_CSV.exists():
        log.warning("Input CSV not found: %s — skipping Phase A", INPUT_CSV)
        return []

    done_ceps = set(checkpoint.get("enriched_ceps", []))

    missing = []
    with open(INPUT_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cep = row.get("cep", "").strip()
            if not row.get("ibge", "").strip() or not row.get("ddd", "").strip():
                if cep and cep not in done_ceps:
                    missing.append(cep)

    if not missing:
        log.info("Phase A: No CEPs missing ibge/ddd (or all already enriched).")
        return []

    log.info("Phase A: %d CEPs missing ibge/ddd, %d already enriched. Processing %d.",
             len(missing) + len(done_ceps), len(done_ceps), len(missing))

    results: list[dict] = []
    batch_counter = 0

    pbar = tqdm(missing, desc="Phase A (enrich)", unit="cep")
    for cep in pbar:
        data = fetch_cep(cep, session)
        if data and data.get("ibge"):
            results.append({
                "cep": data.get("cep", "").replace("-", ""),
                "logradouro": data.get("logradouro", ""),
                "complemento": data.get("complemento", ""),
                "bairro": data.get("bairro", ""),
                "localidade": data.get("localidade", ""),
                "uf": data.get("uf", ""),
                "ibge": data.get("ibge", ""),
                "ddd": data.get("ddd", ""),
                "source": "viacep",
            })

        done_ceps.add(cep)
        batch_counter += 1

        if batch_counter % 100 == 0:
            checkpoint["enriched_ceps"] = sorted(done_ceps)
            save_checkpoint(checkpoint)

        time.sleep(VIACEP_DELAY_SECONDS)

    checkpoint["enriched_ceps"] = sorted(done_ceps)
    save_checkpoint(checkpoint)

    log.info("Phase A: Enriched %d CEPs with ibge/ddd data.", len(results))
    return results


# ---------------------------------------------------------------------------
# Phase B: Discover new CEPs via address search
# ---------------------------------------------------------------------------

def phase_b_search(session: requests.Session, checkpoint: dict, existing_ceps: set[str]) -> list[dict]:
    """Search for new CEPs using ViaCEP address search by municipality."""
    if not MUNICIPIOS_JSON.exists():
        log.warning("municipios.json not found — skipping Phase B")
        return []

    with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
        municipios = json.load(f)

    done_cities = set(checkpoint.get("searched_cities", []))
    pending = [m for m in municipios if str(m["ibge_code"]) not in done_cities]

    if not pending:
        log.info("Phase B: All municipalities already searched.")
        return []

    log.info("Phase B: %d/%d municipalities remaining.", len(pending), len(municipios))

    results: list[dict] = []
    new_ceps_found = 0
    seen_ceps = set(existing_ceps)

    pbar = tqdm(pending, desc="Phase B (search)", unit="mun",
                initial=len(municipios) - len(pending), total=len(municipios))

    try:
        for mun in pbar:
            ibge_code = str(mun["ibge_code"])
            uf = mun["uf"]
            nome = mun["name"]
            pbar.set_postfix_str(f"{uf}/{nome[:20]}", refresh=False)

            for prefix in LOGRADOURO_PREFIXES:
                entries = fetch_address_search(uf, nome, prefix, session)
                for entry in entries:
                    cep = entry.get("cep", "").replace("-", "")
                    if cep and cep not in seen_ceps:
                        seen_ceps.add(cep)
                        new_ceps_found += 1
                        results.append({
                            "cep": cep,
                            "logradouro": entry.get("logradouro", ""),
                            "complemento": entry.get("complemento", ""),
                            "bairro": entry.get("bairro", ""),
                            "localidade": entry.get("localidade", ""),
                            "uf": entry.get("uf", ""),
                            "ibge": entry.get("ibge", ""),
                            "ddd": entry.get("ddd", ""),
                            "source": "viacep",
                        })
                time.sleep(VIACEP_DELAY_SECONDS)

            done_cities.add(ibge_code)
            checkpoint["searched_cities"] = sorted(done_cities)
            save_checkpoint(checkpoint)

    except KeyboardInterrupt:
        log.info("\nInterrompido pelo usuário. Progresso salvo.")

    log.info("Phase B: Found %d new CEPs from address search.", new_ceps_found)
    return results


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def write_results(rows: list[dict], append: bool = False) -> None:
    file_exists = OUTPUT_CSV.exists() and OUTPUT_CSV.stat().st_size > 0
    mode = "a" if (append and file_exists) else "w"
    with open(OUTPUT_CSV, mode, newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if mode == "w" or not file_exists:
            writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run(*, dry_run: bool = False) -> None:
    log.info("=" * 60)
    log.info("ViaCEP enrichment & search pipeline")
    log.info("=" * 60)

    if dry_run:
        # Count CEPs missing ibge/ddd
        missing_count = 0
        total_count = 0
        if INPUT_CSV.exists():
            with open(INPUT_CSV, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    total_count += 1
                    if not row.get("ibge", "").strip() or not row.get("ddd", "").strip():
                        missing_count += 1
        log.info("[DRY-RUN] Input: %s (%d rows)", INPUT_CSV, total_count)
        log.info("[DRY-RUN] CEPs missing ibge/ddd: %d", missing_count)
        # Count municipalities for Phase B
        mun_count = 0
        if MUNICIPIOS_JSON.exists():
            with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
                mun_count = len(json.load(f))
        log.info("[DRY-RUN] Municipalities for address search: %d", mun_count)
        log.info("[DRY-RUN] Output would be: %s", OUTPUT_CSV)
        return

    checkpoint = load_checkpoint()
    session = create_session()

    # Load existing CEPs for dedup in Phase B
    existing_ceps: set[str] = set()
    if INPUT_CSV.exists():
        with open(INPUT_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing_ceps.add(row.get("cep", "").strip())
    log.info("Existing CEPs in bulk data: %d", len(existing_ceps))

    all_results: list[dict] = []

    try:
        phase_a_results = phase_a_enrich(session, checkpoint)
        all_results.extend(phase_a_results)
    except KeyboardInterrupt:
        log.info("Interrupted during Phase A. Saving progress...")

    try:
        phase_b_results = phase_b_search(session, checkpoint, existing_ceps)
        all_results.extend(phase_b_results)
    except KeyboardInterrupt:
        log.info("Interrupted during Phase B. Saving progress...")

    if all_results:
        write_results(all_results, append=False)
        log.info("Total results written: %d to %s", len(all_results), OUTPUT_CSV)
    else:
        log.info("No new data collected.")

    log.info("=" * 60)
    log.info("Done. Checkpoint saved to %s", CHECKPOINT_FILE)
    log.info("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    run()
