#!/usr/bin/env python3
"""
cli.py — Unified CLI for the CEP data pipeline.

Usage:
    python3 cli.py download                    # download bulk CEP datasets
    python3 cli.py scrape                      # enrich via ViaCEP API
    python3 cli.py validate                    # validate, normalize, deduplicate
    python3 cli.py export sqlite               # export to SQLite + FTS5
    python3 cli.py export json                 # export to per-UF JSON files
    python3 cli.py stats                       # build statistics
    python3 cli.py sync                        # live SQLite sync (resumable)
    python3 cli.py sync --batch=5000 --uf=SP   # sync with filters
    python3 cli.py status                      # show DB sync status
    python3 cli.py pipeline                    # run download → stats
    python3 cli.py pipeline --from=validate    # resume from step
    python3 cli.py pipeline --to=export        # stop after export

All mutation commands accept --dry-run.
"""

from __future__ import annotations

import argparse
import logging
import sys

log = logging.getLogger("ceps")

# Pipeline steps in order.
# "export" is a virtual step that runs both sqlite and json exports.
PIPELINE_STEPS = [
    "download",
    "scrape",
    "validate",
    "export",   # runs export_sqlite + export_json
    "stats",
]


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )


# ── command handlers ────────────────────────────────────────────────────────

def cmd_download(args: argparse.Namespace) -> None:
    from download import run
    run(dry_run=args.dry_run)


def cmd_scrape(args: argparse.Namespace) -> None:
    from scrape import run
    run(dry_run=args.dry_run)


def cmd_validate(args: argparse.Namespace) -> None:
    from validate import run
    run(dry_run=args.dry_run)


def cmd_export_sqlite(args: argparse.Namespace) -> None:
    from export_sqlite import run
    run(dry_run=args.dry_run)


def cmd_export_json(args: argparse.Namespace) -> None:
    from export_json import run
    run(dry_run=args.dry_run)


def cmd_stats(args: argparse.Namespace) -> None:
    from stats import run
    run(dry_run=args.dry_run)


def cmd_sync(args: argparse.Namespace) -> None:
    from sync import run
    run(
        dry_run=args.dry_run,
        batch=args.batch,
        uf=args.uf or None,
        stale_days=args.stale_days,
        delay=args.delay,
    )


def cmd_status(args: argparse.Namespace) -> None:
    from sync import run_status
    run_status(stale_days=args.stale_days)


def cmd_pipeline(args: argparse.Namespace) -> None:
    dry_run = args.dry_run
    from_step = args.from_step
    to_step = args.to_step

    # Resolve step range
    step_names = [s for s in PIPELINE_STEPS]

    if from_step:
        if from_step not in step_names:
            log.error("Unknown step: %s. Valid: %s", from_step, ", ".join(step_names))
            sys.exit(1)
        start_idx = step_names.index(from_step)
    else:
        start_idx = 0

    if to_step:
        if to_step not in step_names:
            log.error("Unknown step: %s. Valid: %s", to_step, ", ".join(step_names))
            sys.exit(1)
        end_idx = step_names.index(to_step)
    else:
        end_idx = len(step_names) - 1

    if start_idx > end_idx:
        log.error("--from=%s comes after --to=%s", from_step, to_step)
        sys.exit(1)

    steps_to_run = step_names[start_idx:end_idx + 1]

    log.info("=" * 60)
    log.info("CEP Pipeline")
    log.info("  Steps: %s", " → ".join(steps_to_run))
    if dry_run:
        log.info("  Mode: DRY-RUN")
    log.info("=" * 60)

    for step in steps_to_run:
        log.info("")
        log.info("━" * 60)
        log.info("  Step: %s", step)
        log.info("━" * 60)

        if step == "download":
            from download import run as run_download
            run_download(dry_run=dry_run)
        elif step == "scrape":
            from scrape import run as run_scrape
            run_scrape(dry_run=dry_run)
        elif step == "validate":
            from validate import run as run_validate
            run_validate(dry_run=dry_run)
        elif step == "export":
            from export_sqlite import run as run_export_sqlite
            from export_json import run as run_export_json
            log.info("  [export sqlite]")
            run_export_sqlite(dry_run=dry_run)
            log.info("  [export json]")
            run_export_json(dry_run=dry_run)
        elif step == "stats":
            from stats import run as run_stats
            run_stats(dry_run=dry_run)

    log.info("")
    log.info("=" * 60)
    log.info("Pipeline complete.")
    log.info("=" * 60)


# ── argparse setup ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cep-cli",
        description="Unified CLI for the CEP data pipeline.",
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")

    sub = parser.add_subparsers(dest="command", required=True)

    # download
    p = sub.add_parser("download", help="Download bulk CEP datasets")
    p.add_argument("--dry-run", action="store_true",
                   help="Show source URLs, skip download")

    # scrape
    p = sub.add_parser("scrape", help="Enrich via ViaCEP API")
    p.add_argument("--dry-run", action="store_true",
                   help="Show CEPs missing IBGE/DDD, skip API calls")

    # validate
    p = sub.add_parser("validate", help="Validate, normalize, deduplicate")
    p.add_argument("--dry-run", action="store_true",
                   help="Run validation, print stats, don't write output")

    # export (with nested subcommands: sqlite, json)
    p_export = sub.add_parser("export", help="Export to SQLite or JSON")
    export_sub = p_export.add_subparsers(dest="export_target", required=True)

    p_sqlite = export_sub.add_parser("sqlite", help="Export to SQLite + FTS5")
    p_sqlite.add_argument("--dry-run", action="store_true",
                          help="Show input row count and target DB path")

    p_json = export_sub.add_parser("json", help="Export to per-UF JSON files")
    p_json.add_argument("--dry-run", action="store_true",
                        help="Show row count per UF and file paths")

    # stats
    p = sub.add_parser("stats", help="Build and save statistics")
    p.add_argument("--dry-run", action="store_true",
                   help="Print stats read-only, don't update metadata")

    # sync
    p = sub.add_parser("sync", help="Live SQLite sync (resumable)")
    p.add_argument("--batch", type=int, default=0,
                   help="Max CEPs to process (0=all)")
    p.add_argument("--uf", type=str, default="",
                   help="Filter by UF (comma-separated, e.g. SP,RJ)")
    p.add_argument("--stale-days", type=int, default=7,
                   help="Re-sync CEPs older than N days (0=only never-synced)")
    p.add_argument("--delay", type=float, default=0.35,
                   help="Delay between requests in seconds (default: 0.35)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show pending CEP count, skip API calls")

    # status
    p = sub.add_parser("status", help="Show DB sync status")
    p.add_argument("--stale-days", type=int, default=7,
                   help="Stale threshold in days (default: 7)")

    # pipeline
    p = sub.add_parser("pipeline", help="Run full pipeline (download → stats)")
    p.add_argument("--from", dest="from_step", type=str, default=None,
                   metavar="STEP",
                   help="Resume from step (download|scrape|validate|export|stats)")
    p.add_argument("--to", dest="to_step", type=str, default=None,
                   metavar="STEP",
                   help="Stop after step (download|scrape|validate|export|stats)")
    p.add_argument("--dry-run", action="store_true",
                   help="List steps and check prerequisites")

    return parser


# ── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    cmd = args.command

    if cmd == "download":
        cmd_download(args)
    elif cmd == "scrape":
        cmd_scrape(args)
    elif cmd == "validate":
        cmd_validate(args)
    elif cmd == "export":
        if args.export_target == "sqlite":
            cmd_export_sqlite(args)
        elif args.export_target == "json":
            cmd_export_json(args)
    elif cmd == "stats":
        cmd_stats(args)
    elif cmd == "sync":
        cmd_sync(args)
    elif cmd == "status":
        cmd_status(args)
    elif cmd == "pipeline":
        cmd_pipeline(args)


if __name__ == "__main__":
    main()
