#!/usr/bin/env python3
"""
export_sqlite.py  (was 04-export-sqlite.py)
───────────────────────────────────────────
Exporta CEPs validados para o banco SQLite unificado.

Le data/merged/ceps-validated.csv e insere/atualiza a tabela `ceps`
em database/municipios-br.sqlite, incluindo indices e FTS5.
"""

import csv
import logging
import sqlite3
import time
from pathlib import Path

from config import DATABASE_DIR, MERGED_DIR, UNIFIED_SQLITE

log = logging.getLogger(__name__)

# === Paths ===
INPUT_CSV = MERGED_DIR / "ceps-validated.csv"

BATCH_SIZE = 1000

COLUMNS = ["cep", "logradouro", "complemento", "bairro", "localidade", "uf", "ibge", "ddd", "source", "synced_at"]

INSERT_SQL = """
INSERT OR REPLACE INTO ceps (cep, logradouro, complemento, bairro, localidade, uf, ibge, ddd, source, synced_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def read_csv(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def populate_ceps(db_path: Path, rows: list[dict]) -> None:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ceps (
            cep TEXT PRIMARY KEY,
            logradouro TEXT, complemento TEXT, bairro TEXT,
            localidade TEXT NOT NULL, uf TEXT NOT NULL,
            ibge TEXT, ddd TEXT, source TEXT NOT NULL,
            synced_at TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceps_uf ON ceps(uf);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceps_ibge ON ceps(ibge);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceps_localidade ON ceps(localidade);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ceps_synced_at ON ceps(synced_at);")

    cursor.execute("DELETE FROM ceps")

    log.info("Inserindo %d CEPs...", len(rows))
    batch = []
    for row in rows:
        values = tuple(row.get(col, "") or "" for col in COLUMNS)
        batch.append(values)

        if len(batch) >= BATCH_SIZE:
            cursor.executemany(INSERT_SQL, batch)
            batch.clear()

    if batch:
        cursor.executemany(INSERT_SQL, batch)
        batch.clear()

    conn.commit()

    log.info("Reconstruindo indice FTS5...")
    cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS ceps_fts USING fts5(cep, logradouro, bairro, localidade)")
    cursor.execute("DELETE FROM ceps_fts")
    cursor.execute(
        "INSERT INTO ceps_fts (rowid, cep, logradouro, bairro, localidade) "
        "SELECT rowid, cep, logradouro, bairro, localidade FROM ceps"
    )

    conn.commit()
    conn.close()


def print_stats(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    total = cursor.execute("SELECT COUNT(*) FROM ceps").fetchone()[0]
    by_uf = cursor.execute(
        "SELECT uf, COUNT(*) FROM ceps GROUP BY uf ORDER BY uf"
    ).fetchall()
    by_source = cursor.execute(
        "SELECT source, COUNT(*) FROM ceps GROUP BY source ORDER BY source"
    ).fetchall()
    fts_count = cursor.execute("SELECT COUNT(*) FROM ceps_fts").fetchone()[0]

    conn.close()

    file_size_mb = db_path.stat().st_size / (1024 * 1024)

    log.info("=" * 50)
    log.info("  SQLite atualizado: %s", db_path)
    log.info("  Tamanho: %.1f MB", file_size_mb)
    log.info("  Total CEPs: %d", total)
    log.info("  Registros FTS5: %d", fts_count)
    log.info("=" * 50)

    for uf, count in by_uf:
        log.info("  %s: %10d", uf, count)

    for source, count in by_source:
        log.info("  %-12s %10d", source, count)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run(*, dry_run: bool = False) -> None:
    if not INPUT_CSV.exists():
        log.error("Arquivo nao encontrado: %s", INPUT_CSV)
        log.error("Execute os scripts anteriores primeiro.")
        return

    log.info("Lendo %s...", INPUT_CSV)
    start = time.time()

    rows = read_csv(INPUT_CSV)
    log.info("  %d registros lidos.", len(rows))

    if dry_run:
        log.info("[DRY-RUN] Would insert %d rows into %s", len(rows), UNIFIED_SQLITE)
        log.info("[DRY-RUN] Would rebuild FTS5 index")
        return

    populate_ceps(UNIFIED_SQLITE, rows)
    elapsed = time.time() - start

    print_stats(UNIFIED_SQLITE)
    log.info("Tempo total: %.1fs", elapsed)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    run()
