#!/usr/bin/env python3
"""
validate.py  (was 03-validate-deduplicate.py)
─────────────────────────────────────────────
Validates, normalizes, and deduplicates CEP data from multiple sources.

Input:
  - data/merged/ceps-bulk.csv   (from download)
  - data/viacep/viacep-all.csv  (from scrape)

Output:
  - data/merged/ceps-validated.csv
"""

import csv
import logging
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import config

log = logging.getLogger(__name__)

# === Constants ===
SOURCE_PRIORITY = {"viacep": 0, "cep.la": 1, "github": 2}

INPUT_BULK = config.MERGED_DIR / "ceps-bulk.csv"
INPUT_VIACEP = config.DATA_DIR / "viacep" / "viacep-all.csv"
OUTPUT_FILE = config.MERGED_DIR / "ceps-validated.csv"

OUTPUT_COLUMNS = [
    "cep", "logradouro", "complemento", "bairro",
    "localidade", "uf", "ibge", "ddd", "source",
]

VALID_UFS = set(config.ALL_UFS)


# === Helpers ===

def remove_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.category(c).startswith("M"))


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return text.strip().title()


def clean_logradouro(logradouro: str, complemento: str) -> tuple[str, str]:
    """Clean logradouro to match Correios canonical format."""
    if not logradouro:
        return logradouro, complemento

    extras: list[str] = []

    paren_match = re.search(r"\s*\(([^)]+)\)\s*$", logradouro)
    if paren_match:
        extras.append(paren_match.group(1).strip())
        logradouro = logradouro[: paren_match.start()].strip()

    logradouro = re.sub(
        r",\s*(Até|De)\s+\d+.*$", "", logradouro, flags=re.IGNORECASE
    ).strip()

    logradouro = re.sub(
        r"[,\s]*-?\s*Lado\s+(Ímpar|Impar|Par)\s*$", "", logradouro, flags=re.IGNORECASE
    ).strip()

    street_types = (
        r"(?:Rua|Rodovia|Avenida|Alameda|Travessa|Praça|Estrada|Via|Beco|"
        r"Largo|Viaduto|Viela|Servidão|Ladeira|Quadra|Setor)"
    )
    company_match = re.match(
        rf"^.+?,\s*({street_types}\s+.+)$", logradouro, flags=re.IGNORECASE
    )
    if company_match:
        logradouro = company_match.group(1).strip()

    logradouro = re.sub(r",\s*[Kk][Mm]\s+", " km ", logradouro).strip()
    logradouro = re.sub(r"\s+Comércio\s*$", "", logradouro, flags=re.IGNORECASE).strip()
    logradouro = re.sub(r"\b([A-Z])\s+(\d+)\b", r"\1\2", logradouro)
    logradouro = logradouro.rstrip(",- ").strip()

    if extras and not complemento:
        complemento = "; ".join(extras)

    return logradouro, complemento


_BRASILIA_SECTOR_PREFIXES = {
    "SBN", "SBS", "SBB", "SCN", "SCS", "SDN", "SDS", "SEN", "SES",
    "SGN", "SGS", "SHN", "SHS", "SIG", "SMHN", "SMHS", "SMPW",
    "SMU", "SQN", "SQS", "SQSW", "SQNW", "SRTVN", "SRTVS", "SCLRN",
    "SCLRS", "SLN", "SRN", "SRS", "QI", "QN", "QR", "QS", "QNB",
    "QNC", "QND", "QNE", "QNF", "QNG", "QNH", "QNJ", "QNL", "QNM",
    "QNN", "QNO", "QNP", "EQNL", "EQNM", "EQNN", "EQNO", "EQNP",
    "AE", "CA", "CL", "EQ",
}

_DF_ADMIN_REGIONS = {
    "Gama", "Taguatinga", "Brazlândia", "Sobradinho", "Planaltina",
    "Paranoá", "Núcleo Bandeirante", "Ceilândia", "Guará", "Cruzeiro",
    "Samambaia", "Santa Maria", "São Sebastião", "Recanto Das Emas",
    "Lago Sul", "Lago Norte", "Candangolândia", "Águas Claras",
    "Riacho Fundo", "Riacho Fundo Ii", "Sudoeste", "Octogonal",
    "Varjão", "Park Way", "Scia", "Sobradinho Ii", "Jardim Botânico",
    "Itapoã", "Sia", "Vicente Pires", "Fercal", "Sol Nascente",
    "Pôr Do Sol", "Arniqueira",
}


def fix_brasilia_quadra(logradouro: str) -> str:
    if not logradouro:
        return logradouro
    first_word = logradouro.split()[0] if logradouro.split() else ""
    if first_word.upper() in _BRASILIA_SECTOR_PREFIXES:
        rest = logradouro[len(first_word):].strip()
        return f"Quadra {first_word.upper()} {rest}".strip()
    return logradouro


def fix_brasilia_city(localidade: str, uf: str, bairro: str) -> tuple[str, str]:
    if uf != "DF":
        return localidade, bairro
    if localidade.title() in _DF_ADMIN_REGIONS or localidade == "Brasília":
        if localidade.title() != "Brasília" and localidade.title() not in bairro:
            if bairro:
                bairro = f"{bairro} ({localidade})"
            else:
                bairro = localidade
        return "Brasília", bairro
    return localidade, bairro


def normalize_cep(cep: str | None) -> str:
    if not cep:
        return ""
    digits = re.sub(r"\D", "", str(cep))
    return digits.zfill(8) if len(digits) <= 8 else digits


def validate_row(row: dict, stats: Counter) -> dict | None:
    cep = normalize_cep(row.get("cep", ""))

    if len(cep) != 8 or not cep.isdigit():
        stats["invalid_cep_format"] += 1
        return None

    uf = row.get("uf", "").strip().upper()
    if uf not in VALID_UFS:
        stats["invalid_uf"] += 1
        return None

    expected_uf = config.get_uf_from_cep(cep)
    if expected_uf and expected_uf != uf:
        stats["cep_uf_mismatch"] += 1
        return None

    if expected_uf is None:
        stats["cep_unknown_range"] += 1
        return None

    localidade = normalize_text(row.get("localidade", ""))
    if not localidade:
        stats["empty_localidade"] += 1
        return None

    logradouro = normalize_text(row.get("logradouro", ""))
    complemento = row.get("complemento", "").strip() if row.get("complemento") else ""
    bairro = normalize_text(row.get("bairro", ""))

    logradouro, complemento = clean_logradouro(logradouro, complemento)
    logradouro = fix_brasilia_quadra(logradouro)
    localidade, bairro = fix_brasilia_city(localidade, uf, bairro)

    ibge = row.get("ibge", "").strip() if row.get("ibge") else ""
    ddd = row.get("ddd", "").strip() if row.get("ddd") else ""
    source = row.get("source", "").strip().lower()

    return {
        "cep": cep,
        "logradouro": logradouro,
        "complemento": complemento,
        "bairro": bairro,
        "localidade": localidade,
        "uf": uf,
        "ibge": ibge,
        "ddd": ddd,
        "source": source,
    }


def source_priority(source: str) -> int:
    return SOURCE_PRIORITY.get(source, 99)


def read_csv_file(filepath: Path, default_source: str | None = None) -> list[dict]:
    rows = []
    if not filepath.exists():
        log.info("  [SKIP] %s not found", filepath)
        return rows

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if default_source and not row.get("source"):
                row["source"] = default_source
            rows.append(row)

    log.info("  [OK]   %s: %10d rows", filepath.name, len(rows))
    return rows


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run(*, dry_run: bool = False) -> None:
    log.info("=" * 60)
    log.info("Validate, Normalize & Deduplicate CEPs")
    log.info("=" * 60)

    # 1. Read input files
    log.info("1. Reading input files...")
    bulk_rows = read_csv_file(INPUT_BULK)
    viacep_rows = read_csv_file(INPUT_VIACEP, default_source="viacep")

    all_rows = bulk_rows + viacep_rows
    total_input = len(all_rows)
    log.info("   Total input rows: %d", total_input)

    if total_input == 0:
        if dry_run:
            log.info("[DRY-RUN] No input data found — nothing to validate.")
            return
        log.error("No input data found. Ensure download and scrape ran first.")
        sys.exit(1)

    # 2. Validate & normalize
    log.info("2. Validating and normalizing...")
    stats = Counter()
    valid_rows = []

    for row in all_rows:
        normalized = validate_row(row, stats)
        if normalized:
            valid_rows.append(normalized)
        else:
            stats["total_invalid"] += 1

    total_invalid = stats["total_invalid"]
    log.info("   Valid rows:   %10d", len(valid_rows))
    log.info("   Invalid rows: %10d", total_invalid)

    for key in ("invalid_cep_format", "invalid_uf", "cep_uf_mismatch", "cep_unknown_range", "empty_localidade"):
        if stats[key]:
            log.info("     - %-20s %8d", key + ":", stats[key])

    # 3. Deduplicate
    log.info("3. Deduplicating...")
    best: dict[str, dict] = {}
    for row in valid_rows:
        cep = row["cep"]
        if cep not in best:
            best[cep] = row
        else:
            existing_priority = source_priority(best[cep]["source"])
            new_priority = source_priority(row["source"])
            if new_priority < existing_priority:
                best[cep] = row

    duplicates_removed = len(valid_rows) - len(best)
    deduped = sorted(best.values(), key=lambda r: r["cep"])

    log.info("   Before dedup: %10d", len(valid_rows))
    log.info("   Duplicates:   %10d", duplicates_removed)
    log.info("   After dedup:  %10d", len(deduped))

    # 4. Build search-friendly field
    log.info("4. Building search-friendly text...")
    for row in deduped:
        parts = [row["logradouro"], row["bairro"], row["localidade"]]
        search_text = " ".join(p for p in parts if p)
        row["search"] = remove_accents(search_text).lower()

    if dry_run:
        log.info("[DRY-RUN] Would write %d rows to %s", len(deduped), OUTPUT_FILE)
        log.info("[DRY-RUN] Summary: %d input -> %d valid -> %d deduped",
                 total_input, len(valid_rows), len(deduped))
        # Per-UF breakdown
        uf_counts = Counter(row["uf"] for row in deduped)
        for uf in config.ALL_UFS:
            count = uf_counts.get(uf, 0)
            if count > 0:
                log.info("    %s (%s): %d", uf, config.UF_NAMES.get(uf, uf), count)
        return

    # 5. Write output
    log.info("5. Writing output...")
    output_columns = OUTPUT_COLUMNS + ["search"]
    config.MERGED_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_columns)
        writer.writeheader()
        writer.writerows(deduped)

    log.info("   Output: %s", OUTPUT_FILE)
    log.info("   Rows:   %d", len(deduped))

    # 6. Print summary
    log.info("=" * 60)
    log.info("SUMMARY")
    log.info("  Total input:     %10d", total_input)
    log.info("  Invalid:         %10d", total_invalid)
    log.info("  Duplicates:      %10d", duplicates_removed)
    log.info("  Final count:     %10d", len(deduped))

    uf_counts = Counter(row["uf"] for row in deduped)
    for uf in config.ALL_UFS:
        count = uf_counts.get(uf, 0)
        if count > 0:
            name = config.UF_NAMES.get(uf, uf)
            log.info("    %s (%-20s): %10d", uf, name, count)

    source_counts = Counter(row["source"] for row in deduped)
    for source, count in source_counts.most_common():
        log.info("    %-10s: %10d", source, count)

    log.info("=" * 60)
    log.info("Done.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    run()
