#!/usr/bin/env python3
"""
sync.py  (was 08-sync-sqlite-live.py)
─────────────────────────────────────
Resumable CEP sync runner — reads pending CEPs from SQLite, syncs via
BrasilAPI/ViaCEP, writes results back. The database IS the checkpoint.
"""

import logging
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone

import requests
from tqdm import tqdm

from _fetch import create_session, fetch_cep
from config import (
    UNIFIED_SQLITE,
    VIACEP_DELAY_SECONDS,
)

log = logging.getLogger(__name__)

COMMIT_EVERY = 500

# Graceful shutdown flag
_shutdown = False


def _handle_signal(sig, frame):
    global _shutdown
    _shutdown = True
    log.info("Interrupt received — finishing current batch...")


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(UNIFIED_SQLITE), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def get_pending_ceps(conn: sqlite3.Connection, stale_days: int,
                     ufs: list[str] | None, batch: int) -> list[sqlite3.Row]:
    if stale_days == 0:
        where = "synced_at IS NULL"
        params: list = []
    else:
        where = "synced_at IS NULL OR synced_at < datetime('now', ?)"
        params = [f"-{stale_days} days"]

    if ufs:
        placeholders = ",".join("?" for _ in ufs)
        where += f" AND uf IN ({placeholders})"
        params.extend(ufs)

    sql = f"SELECT cep, ibge, ddd FROM ceps WHERE {where} ORDER BY cep"
    if batch > 0:
        sql += f" LIMIT {batch}"

    return conn.execute(sql, params).fetchall()


UPDATE_SQL = """
UPDATE ceps SET logradouro=?, complemento=?, bairro=?, localidade=?,
    uf=?, ibge=?, ddd=?, source=?, synced_at=?
WHERE cep=?
"""


# ---------------------------------------------------------------------------
# Status display
# ---------------------------------------------------------------------------

def show_status(conn: sqlite3.Connection, stale_days: int) -> None:
    total = conn.execute("SELECT COUNT(*) FROM ceps").fetchone()[0]

    if stale_days == 0:
        fresh = conn.execute(
            "SELECT COUNT(*) FROM ceps WHERE synced_at IS NOT NULL"
        ).fetchone()[0]
        stale = 0
        never = total - fresh
    else:
        fresh = conn.execute(
            "SELECT COUNT(*) FROM ceps WHERE synced_at >= datetime('now', ?)",
            [f"-{stale_days} days"],
        ).fetchone()[0]
        stale = conn.execute(
            "SELECT COUNT(*) FROM ceps WHERE synced_at IS NOT NULL AND synced_at < datetime('now', ?)",
            [f"-{stale_days} days"],
        ).fetchone()[0]
        never = total - fresh - stale

    last_sync = conn.execute(
        "SELECT MAX(synced_at) FROM ceps WHERE synced_at IS NOT NULL"
    ).fetchone()[0] or "never"

    pct = lambda n: f"{n / total * 100:.1f}%" if total else "0%"

    print(f"\nCEP Sync Status (stale_days={stale_days})")
    print(f"  Total CEPs:      {total:>10,}")
    print(f"  Synced (fresh):  {fresh:>10,}  ({pct(fresh)})")
    if stale_days > 0:
        print(f"  Stale (>{stale_days}d):    {stale:>10,}  ({pct(stale)})")
    print(f"  Never synced:    {never:>10,}  ({pct(never)})")
    print(f"  Last sync:       {last_sync}")

    # Top pending UFs
    if stale_days == 0:
        where_pending = "synced_at IS NULL"
        params: list = []
    else:
        where_pending = "synced_at IS NULL OR synced_at < datetime('now', ?)"
        params = [f"-{stale_days} days"]

    rows = conn.execute(
        f"SELECT uf, COUNT(*) as cnt FROM ceps WHERE {where_pending} "
        "GROUP BY uf ORDER BY cnt DESC LIMIT 10",
        params,
    ).fetchall()

    if rows:
        print(f"\n  By UF (top pending):")
        for r in rows:
            print(f"    {r['uf']}: {r['cnt']:>10,} pending")
    print()


# ---------------------------------------------------------------------------
# Sync loop
# ---------------------------------------------------------------------------

def _do_sync(*, batch: int, uf: str | None, stale_days: int,
             delay: float, dry_run: bool) -> None:
    conn = open_db()

    ufs = [u.strip().upper() for u in uf.split(",")] if uf else None

    log.info("Querying pending CEPs (stale_days=%d, uf=%s, batch=%s)...",
             stale_days, ufs or "all", batch or "unlimited")

    pending = get_pending_ceps(conn, stale_days, ufs, batch)

    if not pending:
        log.info("No CEPs to sync.")
        show_status(conn, stale_days)
        conn.close()
        return

    log.info("Found %d CEPs to sync.", len(pending))

    if dry_run:
        log.info("[DRY-RUN] Would sync %d CEPs from %s", len(pending), UNIFIED_SQLITE)
        # UF breakdown of pending
        uf_counts: dict[str, int] = {}
        for row in pending:
            # pending rows only have cep, ibge, ddd — derive UF from cep range
            pass
        log.info("[DRY-RUN] Delay between requests: %.2fs", delay)
        log.info("[DRY-RUN] No API calls would be made.")
        show_status(conn, stale_days)
        conn.close()
        return

    session = create_session()

    synced_count = 0
    not_found = 0
    errors = 0
    batch_updates: list[tuple] = []

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    pbar = tqdm(pending, desc="Syncing CEPs", unit="cep",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}")

    for row in pbar:
        if _shutdown:
            break

        cep = row["cep"]
        existing_ibge = row["ibge"] or ""
        existing_ddd = row["ddd"] or ""

        try:
            result = fetch_cep(cep, session)
        except Exception as e:
            log.debug("Exception fetching %s: %s", cep, e)
            errors += 1
            if (synced_count + not_found + errors) % COMMIT_EVERY == 0:
                pbar.set_postfix_str(f"synced={synced_count} notfound={not_found} errors={errors}")
            time.sleep(delay)
            continue

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        if result:
            ibge = result["ibge"] if result["ibge"] else existing_ibge
            ddd = result["ddd"] if result["ddd"] else existing_ddd

            batch_updates.append((
                result["logradouro"], result["complemento"], result["bairro"],
                result["localidade"], result["uf"], ibge, ddd,
                result["source"], now_iso, cep,
            ))
            synced_count += 1
        else:
            batch_updates.append((
                None, None, None, None, None, None, None, None, now_iso, cep,
            ))
            not_found += 1

        processed = synced_count + not_found + errors
        if processed % COMMIT_EVERY == 0:
            _flush_batch(conn, batch_updates, not_found)
            batch_updates.clear()
            pbar.set_postfix_str(f"synced={synced_count} notfound={not_found} errors={errors}")
            log.info("Progress: %d/%d (synced=%d, notfound=%d, errors=%d)",
                     processed, len(pending), synced_count, not_found, errors)

        time.sleep(delay)

    # Final flush
    _flush_batch(conn, batch_updates, not_found)
    batch_updates.clear()

    log.info("Done. synced=%d, notfound=%d, errors=%d, total_processed=%d/%d",
             synced_count, not_found, errors,
             synced_count + not_found + errors, len(pending))

    # Rebuild FTS and update metadata only on a clean full run
    if not _shutdown and batch == 0 and not ufs:
        log.info("Full run complete — rebuilding FTS index...")
        try:
            conn.execute("DELETE FROM ceps_fts")
            conn.execute(
                "INSERT INTO ceps_fts (rowid, cep, logradouro, bairro, localidade) "
                "SELECT rowid, cep, logradouro, bairro, localidade FROM ceps"
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("ceps_last_sync", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            log.info("FTS rebuilt and metadata updated.")
        except Exception as e:
            log.warning("FTS rebuild failed: %s", e)

    show_status(conn, stale_days)
    conn.close()


def _flush_batch(conn: sqlite3.Connection, updates: list[tuple],
                 not_found_count: int) -> None:
    if not updates:
        return

    synced_updates = []
    timestamp_only = []

    for row in updates:
        if row[0] is None:
            timestamp_only.append((row[8], row[9]))  # (synced_at, cep)
        else:
            synced_updates.append(row)

    if synced_updates:
        conn.executemany(UPDATE_SQL, synced_updates)

    if timestamp_only:
        conn.executemany(
            "UPDATE ceps SET synced_at=? WHERE cep=?",
            timestamp_only,
        )

    conn.commit()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

def run(*, dry_run: bool = False, batch: int = 0, uf: str | None = None,
        stale_days: int = 7, delay: float = VIACEP_DELAY_SECONDS) -> None:
    if not UNIFIED_SQLITE.exists():
        log.error("Database not found: %s", UNIFIED_SQLITE)
        log.error("Run the earlier pipeline steps first.")
        sys.exit(1)

    _do_sync(batch=batch, uf=uf, stale_days=stale_days,
             delay=delay, dry_run=dry_run)


def run_status(*, stale_days: int = 7) -> None:
    """Show sync status and exit."""
    if not UNIFIED_SQLITE.exists():
        log.error("Database not found: %s", UNIFIED_SQLITE)
        sys.exit(1)

    conn = open_db()
    show_status(conn, stale_days)
    conn.close()


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Resumable CEP sync runner (SQLite-native)")
    parser.add_argument("--batch", type=int, default=0,
                        help="Max CEPs to process (0=all)")
    parser.add_argument("--uf", type=str, default="",
                        help="Filter by UF (comma-separated, e.g. SP,RJ)")
    parser.add_argument("--stale-days", type=int, default=7,
                        help="Re-sync CEPs older than N days (0=only never-synced)")
    parser.add_argument("--status", action="store_true",
                        help="Show sync progress and exit")
    parser.add_argument("--delay", type=float, default=VIACEP_DELAY_SECONDS,
                        help=f"Delay between requests in seconds (default: {VIACEP_DELAY_SECONDS})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without making changes")
    args = parser.parse_args()

    if args.status:
        run_status(stale_days=args.stale_days)
    else:
        run(dry_run=args.dry_run, batch=args.batch,
            uf=args.uf or None, stale_days=args.stale_days, delay=args.delay)
