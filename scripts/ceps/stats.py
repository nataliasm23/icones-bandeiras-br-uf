#!/usr/bin/env python3
"""
stats.py  (was 06-build-stats.py)
─────────────────────────────────
Gera/atualiza metadata de CEPs no banco SQLite unificado.

Le a tabela `ceps` em database/municipios-br.sqlite e atualiza a
tabela `metadata` (key='cep_stats') com:
  - total_ceps, by_uf, generated_at, sources
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from config import UNIFIED_SQLITE

log = logging.getLogger(__name__)


def build_stats(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    total = cursor.execute("SELECT COUNT(*) FROM ceps").fetchone()[0]

    by_uf = {}
    for uf, count in cursor.execute(
        "SELECT uf, COUNT(*) FROM ceps GROUP BY uf ORDER BY uf"
    ).fetchall():
        by_uf[uf] = count

    sources = {}
    for source, count in cursor.execute(
        "SELECT source, COUNT(*) FROM ceps GROUP BY source ORDER BY source"
    ).fetchall():
        sources[source] = count

    conn.close()

    return {
        "total_ceps": total,
        "by_uf": by_uf,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
    }


def save_metadata(db_path: Path, stats_data: dict) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("cep_stats", json.dumps(stats_data, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def print_summary(stats_data: dict) -> None:
    log.info("=" * 50)
    log.info("  Banco: %s", UNIFIED_SQLITE)
    log.info("  Total CEPs: %d", stats_data["total_ceps"])
    log.info("  Gerado em: %s", stats_data["generated_at"])
    log.info("=" * 50)

    for uf, count in sorted(stats_data["by_uf"].items()):
        if count > 0:
            log.info("  %s: %10d", uf, count)

    empty = [uf for uf, count in stats_data["by_uf"].items() if count == 0]
    if empty:
        log.warning("  UFs sem dados: %s", ", ".join(empty))

    for source, count in stats_data["sources"].items():
        log.info("  %-12s %10d", source, count)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run(*, dry_run: bool = False) -> None:
    if not UNIFIED_SQLITE.exists():
        log.error("Banco nao encontrado: %s", UNIFIED_SQLITE)
        log.error("Execute scripts/build-unified-sqlite.py primeiro.")
        return

    log.info("Lendo estatisticas de %s...", UNIFIED_SQLITE)
    start = time.time()

    stats_data = build_stats(UNIFIED_SQLITE)

    if dry_run:
        log.info("[DRY-RUN] Stats computed (read-only):")
        print_summary(stats_data)
        log.info("[DRY-RUN] Would update metadata 'cep_stats' in %s", UNIFIED_SQLITE)
        return

    save_metadata(UNIFIED_SQLITE, stats_data)

    elapsed = time.time() - start
    print_summary(stats_data)
    log.info("Metadata 'cep_stats' atualizada no banco.")
    log.info("Tempo total: %.1fs", elapsed)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    run()
