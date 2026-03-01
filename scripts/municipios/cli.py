#!/usr/bin/env python3
"""
cli.py — Unified CLI for the municipality flags pipeline.

Usage:
    python3 cli.py build-db                      # build municipality DB from IBGE
    python3 cli.py fetch wikidata                # Wikidata SPARQL bulk query
    python3 cli.py fetch wikidata-name           # Wikidata by-name search
    python3 cli.py fetch wikipedia               # Wikipedia article images
    python3 cli.py fetch wikipedia-v2            # Wikipedia v2 (stricter)
    python3 cli.py fetch wikipedia-targeted      # targeted Wikipedia search
    python3 cli.py fetch commons-category        # Wikimedia Commons categories
    python3 cli.py fetch commons-retry           # Commons retry (rate-limit safe)
    python3 cli.py fetch commons-search          # Commons direct search
    python3 cli.py fetch mbi                     # MBI thumbnails
    python3 cli.py fetch prefeitura              # prefeitura websites
    python3 cli.py download                      # download found flags
    python3 cli.py validate                      # basic file validation
    python3 cli.py deep-validate                 # deep validation + dedup
    python3 cli.py enrich ibge                   # add population/area/density
    python3 cli.py enrich geo                    # add geolocation/DDD/CEP
    python3 cli.py generate-icons                # generate SVG/PNG icon set
    python3 cli.py generate-icons --uf=SP --skip-png --workers=8 --limit=10

    python3 cli.py pipeline                      # run all steps
    python3 cli.py pipeline --from=download      # resume from step
    python3 cli.py pipeline --to=validate        # stop after step

All mutation commands accept --dry-run.
"""

from __future__ import annotations

import argparse
import logging
import sys

log = logging.getLogger("municipios")

# Pipeline steps in order.
# "fetch" runs ALL fetch sub-commands in sequence.
# "enrich" runs enrich-ibge + enrich-geo.
PIPELINE_STEPS = [
    "build-db",
    "fetch",
    "download",
    "validate",
    "deep-validate",
    "enrich",
    "generate-icons",
]


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )


# ── command handlers ────────────────────────────────────────────────────────

def cmd_build_db(args: argparse.Namespace) -> None:
    from build_db import run
    run(dry_run=args.dry_run)


def cmd_fetch_wikidata(args: argparse.Namespace) -> None:
    from fetch_wikidata import run
    run(dry_run=args.dry_run)


def cmd_fetch_wikidata_name(args: argparse.Namespace) -> None:
    from fetch_wikidata_name import run
    run(dry_run=args.dry_run)


def cmd_fetch_wikipedia(args: argparse.Namespace) -> None:
    from fetch_wikipedia import run
    run(dry_run=args.dry_run)


def cmd_fetch_wikipedia_v2(args: argparse.Namespace) -> None:
    from fetch_wikipedia_v2 import run
    run(dry_run=args.dry_run)


def cmd_fetch_wikipedia_targeted(args: argparse.Namespace) -> None:
    from fetch_wikipedia_targeted import run
    run(dry_run=args.dry_run)


def cmd_fetch_commons_category(args: argparse.Namespace) -> None:
    from fetch_commons_category import run
    run(dry_run=args.dry_run)


def cmd_fetch_commons_retry(args: argparse.Namespace) -> None:
    from fetch_commons_retry import run
    run(dry_run=args.dry_run)


def cmd_fetch_commons_search(args: argparse.Namespace) -> None:
    from fetch_commons_search import run
    run(dry_run=args.dry_run)


def cmd_fetch_mbi(args: argparse.Namespace) -> None:
    from fetch_mbi import run
    run(dry_run=args.dry_run)


def cmd_fetch_prefeitura(args: argparse.Namespace) -> None:
    from fetch_prefeitura import run
    run(dry_run=args.dry_run)


def cmd_download(args: argparse.Namespace) -> None:
    from download_flags import run
    run(dry_run=args.dry_run)


def cmd_validate(args: argparse.Namespace) -> None:
    from validate_flags import run
    run(dry_run=args.dry_run)


def cmd_deep_validate(args: argparse.Namespace) -> None:
    from deep_validate import run
    run(dry_run=args.dry_run)


def cmd_enrich_ibge(args: argparse.Namespace) -> None:
    from enrich_ibge import run
    run(dry_run=args.dry_run)


def cmd_enrich_geo(args: argparse.Namespace) -> None:
    from enrich_geo import run
    run(dry_run=args.dry_run)


def cmd_generate_icons(args: argparse.Namespace) -> None:
    from generate_icons import run
    run(
        dry_run=args.dry_run,
        workers=args.workers,
        uf=args.uf or None,
        skip_png=args.skip_png,
        skip_svg=args.skip_svg,
        limit=args.limit,
    )


def cmd_pipeline(args: argparse.Namespace) -> None:
    dry_run = args.dry_run
    from_step = args.from_step
    to_step = args.to_step

    # Resolve step range
    step_names = list(PIPELINE_STEPS)

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
    log.info("Municipios Pipeline")
    log.info("  Steps: %s", " -> ".join(steps_to_run))
    if dry_run:
        log.info("  Mode: DRY-RUN")
    log.info("=" * 60)

    # Show flag_status counts if dry-run
    if dry_run:
        try:
            import json
            from pathlib import Path
            data_dir = Path(__file__).parent.parent.parent / "data"
            db_path = data_dir / "municipios.json"
            if db_path.exists():
                with open(db_path, "r", encoding="utf-8") as f:
                    municipios = json.load(f)
                statuses = {}
                for m in municipios:
                    s = m.get("flag_status", "unknown")
                    statuses[s] = statuses.get(s, 0) + 1
                log.info("  Current flag_status counts:")
                for status, count in sorted(statuses.items()):
                    log.info("    %-15s %5d", status, count)
        except Exception:
            pass

    for step in steps_to_run:
        log.info("")
        log.info("-" * 60)
        log.info("  Step: %s", step)
        log.info("-" * 60)

        if step == "build-db":
            from build_db import run as run_build_db
            run_build_db(dry_run=dry_run)

        elif step == "fetch":
            # Run ALL fetch sub-commands in sequence
            fetch_modules = [
                ("wikidata",           "fetch_wikidata"),
                ("wikidata-name",      "fetch_wikidata_name"),
                ("wikipedia",          "fetch_wikipedia"),
                ("wikipedia-v2",       "fetch_wikipedia_v2"),
                ("wikipedia-targeted", "fetch_wikipedia_targeted"),
                ("commons-category",   "fetch_commons_category"),
                ("commons-retry",      "fetch_commons_retry"),
                ("commons-search",     "fetch_commons_search"),
                ("mbi",                "fetch_mbi"),
                ("prefeitura",         "fetch_prefeitura"),
            ]
            for label, module_name in fetch_modules:
                log.info("  [fetch %s]", label)
                mod = __import__(module_name)
                mod.run(dry_run=dry_run)

        elif step == "download":
            from download_flags import run as run_download
            run_download(dry_run=dry_run)

        elif step == "validate":
            from validate_flags import run as run_validate
            run_validate(dry_run=dry_run)

        elif step == "deep-validate":
            from deep_validate import run as run_deep_validate
            run_deep_validate(dry_run=dry_run)

        elif step == "enrich":
            from enrich_ibge import run as run_enrich_ibge
            from enrich_geo import run as run_enrich_geo
            log.info("  [enrich ibge]")
            run_enrich_ibge(dry_run=dry_run)
            log.info("  [enrich geo]")
            run_enrich_geo(dry_run=dry_run)

        elif step == "generate-icons":
            from generate_icons import run as run_generate_icons
            run_generate_icons(dry_run=dry_run)

    log.info("")
    log.info("=" * 60)
    log.info("Pipeline complete.")
    log.info("=" * 60)


# ── argparse setup ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="municipios-cli",
        description="Unified CLI for the municipality flags pipeline.",
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")

    sub = parser.add_subparsers(dest="command", required=True)

    # build-db
    p = sub.add_parser("build-db", help="Build municipality DB from IBGE data")
    p.add_argument("--dry-run", action="store_true",
                   help="Show input/output paths, skip processing")

    # fetch (with nested subcommands)
    p_fetch = sub.add_parser("fetch", help="Fetch flags from various sources")
    fetch_sub = p_fetch.add_subparsers(dest="fetch_source", required=True)

    for name, help_text in [
        ("wikidata",           "Wikidata SPARQL bulk query"),
        ("wikidata-name",      "Wikidata by-name search"),
        ("wikipedia",          "Wikipedia article images"),
        ("wikipedia-v2",       "Wikipedia v2 (stricter matching)"),
        ("wikipedia-targeted", "Targeted Wikipedia search"),
        ("commons-category",   "Wikimedia Commons categories"),
        ("commons-retry",      "Commons retry (rate-limit safe)"),
        ("commons-search",     "Commons direct search"),
        ("mbi",                "MBI thumbnails"),
        ("prefeitura",         "Prefeitura websites"),
    ]:
        fp = fetch_sub.add_parser(name, help=help_text)
        fp.add_argument("--dry-run", action="store_true",
                        help="Show what would be fetched, skip API calls")

    # download
    p = sub.add_parser("download", help="Download found flags from sources")
    p.add_argument("--dry-run", action="store_true",
                   help="Show pending download count, skip downloads")

    # validate
    p = sub.add_parser("validate", help="Basic file validation")
    p.add_argument("--dry-run", action="store_true",
                   help="Show file count, skip writing invalid list")

    # deep-validate
    p = sub.add_parser("deep-validate", help="Deep validation + dedup")
    p.add_argument("--dry-run", action="store_true",
                   help="Show file count, skip writing reports")

    # enrich (with nested subcommands)
    p_enrich = sub.add_parser("enrich", help="Enrich municipality data")
    enrich_sub = p_enrich.add_subparsers(dest="enrich_source", required=True)

    p_ibge = enrich_sub.add_parser("ibge", help="Add population/area/density from IBGE")
    p_ibge.add_argument("--dry-run", action="store_true",
                        help="Show API URLs and municipality count, skip fetching")

    p_geo = enrich_sub.add_parser("geo", help="Add geolocation/DDD/CEP data")
    p_geo.add_argument("--dry-run", action="store_true",
                       help="Show source file paths, skip enrichment")

    # generate-icons
    p = sub.add_parser("generate-icons", help="Generate SVG/PNG icon set")
    p.add_argument("--dry-run", action="store_true",
                   help="Show municipality count and formats, skip generation")
    p.add_argument("--workers", type=int, default=4,
                   help="Number of parallel workers (default: 4)")
    p.add_argument("--uf", type=str, default=None,
                   help="Process only a specific UF (e.g., SP)")
    p.add_argument("--skip-png", action="store_true",
                   help="Skip PNG generation")
    p.add_argument("--skip-svg", action="store_true",
                   help="Skip SVG generation")
    p.add_argument("--limit", type=int, default=0,
                   help="Process only first N municipalities (for testing)")

    # pipeline
    p = sub.add_parser("pipeline", help="Run full pipeline (build-db -> generate-icons)")
    p.add_argument("--from", dest="from_step", type=str, default=None,
                   metavar="STEP",
                   help="Resume from step (%s)" % "|".join(PIPELINE_STEPS))
    p.add_argument("--to", dest="to_step", type=str, default=None,
                   metavar="STEP",
                   help="Stop after step (%s)" % "|".join(PIPELINE_STEPS))
    p.add_argument("--dry-run", action="store_true",
                   help="List steps and show flag_status counts")

    return parser


# ── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    cmd = args.command

    if cmd == "build-db":
        cmd_build_db(args)
    elif cmd == "fetch":
        src = args.fetch_source
        if src == "wikidata":
            cmd_fetch_wikidata(args)
        elif src == "wikidata-name":
            cmd_fetch_wikidata_name(args)
        elif src == "wikipedia":
            cmd_fetch_wikipedia(args)
        elif src == "wikipedia-v2":
            cmd_fetch_wikipedia_v2(args)
        elif src == "wikipedia-targeted":
            cmd_fetch_wikipedia_targeted(args)
        elif src == "commons-category":
            cmd_fetch_commons_category(args)
        elif src == "commons-retry":
            cmd_fetch_commons_retry(args)
        elif src == "commons-search":
            cmd_fetch_commons_search(args)
        elif src == "mbi":
            cmd_fetch_mbi(args)
        elif src == "prefeitura":
            cmd_fetch_prefeitura(args)
    elif cmd == "download":
        cmd_download(args)
    elif cmd == "validate":
        cmd_validate(args)
    elif cmd == "deep-validate":
        cmd_deep_validate(args)
    elif cmd == "enrich":
        src = args.enrich_source
        if src == "ibge":
            cmd_enrich_ibge(args)
        elif src == "geo":
            cmd_enrich_geo(args)
    elif cmd == "generate-icons":
        cmd_generate_icons(args)
    elif cmd == "pipeline":
        cmd_pipeline(args)


if __name__ == "__main__":
    main()
