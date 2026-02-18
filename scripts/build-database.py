#!/usr/bin/env python3
"""
Build the final municipality flag database files.

Generates:
  database/municipios.json       - All 5,571 municipalities with flag availability and paths
  database/municipios-by-uf.json - Grouped by state
  database/stats.json            - Coverage statistics

Usage:
  python3 scripts/build-database.py
"""

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DIST_DIR = ROOT / "dist"
DATABASE_DIR = ROOT / "database"
MUNICIPIOS_JSON = DATA_DIR / "municipios.json"


def check_generated_files(ibge_code, slug, uf):
    """Check which generated icon files exist for a municipality."""
    styles = {
        "full": f"{ibge_code}-{slug}-full",
        "rounded": f"{ibge_code}-{slug}-rounded",
        "circle": f"{ibge_code}-{slug}-circle",
        "square-rounded": f"{ibge_code}-{slug}-sq",
    }

    paths = {}
    has_icons = False

    for style_name, basename in styles.items():
        svg_path = DIST_DIR / style_name / "svg" / uf / f"{basename}.svg"
        if svg_path.exists():
            has_icons = True
            paths[f"{style_name}_svg"] = f"{style_name}/svg/{uf}/{basename}.svg"

        for size_label in ["png-200", "png-800"]:
            png_path = DIST_DIR / style_name / size_label / uf / f"{basename}.png"
            if png_path.exists():
                has_icons = True
                paths[f"{style_name}_{size_label}"] = (
                    f"{style_name}/{size_label}/{uf}/{basename}.png"
                )

    return has_icons, paths


def build_database():
    """Build all database files."""
    print(f"Loading source data from {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
        municipios_raw = json.load(f)

    print(f"Loaded {len(municipios_raw)} municipalities")
    print(f"Checking generated icons in {DIST_DIR}...")

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    # Build enriched municipality list
    municipios = []
    by_uf = defaultdict(list)
    stats_by_uf = defaultdict(lambda: {"total": 0, "with_flag": 0, "with_icons": 0})
    stats_by_region = defaultdict(lambda: {"total": 0, "with_flag": 0, "with_icons": 0})

    total_with_flag = 0
    total_with_icons = 0

    for mun in municipios_raw:
        ibge_code = mun["ibge_code"]
        slug = mun["slug"]
        uf = mun["uf"]
        region = mun.get("region_name", mun.get("region", ""))

        has_raw_flag = bool(mun.get("flag_local"))
        has_icons, icon_paths = check_generated_files(ibge_code, slug, uf)

        entry = {
            "ibge_code": ibge_code,
            "name": mun["name"],
            "slug": slug,
            "uf": uf,
            "uf_name": mun.get("uf_name", ""),
            "region": mun.get("region", ""),
            "region_name": region,
            "has_flag": has_raw_flag,
            "has_icons": has_icons,
            "flag_source": mun.get("flag_source", ""),
        }

        if has_icons:
            entry["icons"] = icon_paths

        if has_raw_flag:
            total_with_flag += 1
        if has_icons:
            total_with_icons += 1

        municipios.append(entry)
        by_uf[uf].append(entry)

        stats_by_uf[uf]["total"] += 1
        if has_raw_flag:
            stats_by_uf[uf]["with_flag"] += 1
        if has_icons:
            stats_by_uf[uf]["with_icons"] += 1

        stats_by_region[region]["total"] += 1
        if has_raw_flag:
            stats_by_region[region]["with_flag"] += 1
        if has_icons:
            stats_by_region[region]["with_icons"] += 1

    # Sort municipalities by ibge_code
    municipios.sort(key=lambda m: m["ibge_code"])
    for uf_key in by_uf:
        by_uf[uf_key].sort(key=lambda m: m["ibge_code"])

    # Build stats
    total = len(municipios_raw)
    coverage_pct = (total_with_icons / total * 100) if total > 0 else 0
    raw_coverage_pct = (total_with_flag / total * 100) if total > 0 else 0

    uf_stats = {}
    for uf_key in sorted(stats_by_uf.keys()):
        s = stats_by_uf[uf_key]
        pct = (s["with_icons"] / s["total"] * 100) if s["total"] > 0 else 0
        uf_stats[uf_key] = {
            "total": s["total"],
            "with_flag": s["with_flag"],
            "with_icons": s["with_icons"],
            "coverage_pct": round(pct, 1),
        }

    region_stats = {}
    for region_key in sorted(stats_by_region.keys()):
        s = stats_by_region[region_key]
        pct = (s["with_icons"] / s["total"] * 100) if s["total"] > 0 else 0
        region_stats[region_key] = {
            "total": s["total"],
            "with_flag": s["with_flag"],
            "with_icons": s["with_icons"],
            "coverage_pct": round(pct, 1),
        }

    stats = {
        "total_municipios": total,
        "total_with_raw_flag": total_with_flag,
        "total_with_icons": total_with_icons,
        "raw_coverage_pct": round(raw_coverage_pct, 1),
        "icon_coverage_pct": round(coverage_pct, 1),
        "total_ufs": len(stats_by_uf),
        "styles": ["full", "rounded", "circle", "square-rounded"],
        "formats": {
            "svg": ["full/svg", "rounded/svg", "circle/svg", "square-rounded/svg"],
            "png-200": [
                "full/png-200", "rounded/png-200",
                "circle/png-200", "square-rounded/png-200",
            ],
            "png-800": [
                "full/png-800", "rounded/png-800",
                "circle/png-800", "square-rounded/png-800",
            ],
        },
        "by_uf": uf_stats,
        "by_region": region_stats,
    }

    # Write database files
    mun_path = DATABASE_DIR / "municipios.json"
    with open(mun_path, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)
    print(f"  {mun_path} ({len(municipios)} entries)")

    by_uf_path = DATABASE_DIR / "municipios-by-uf.json"
    with open(by_uf_path, "w", encoding="utf-8") as f:
        json.dump(dict(by_uf), f, ensure_ascii=False, indent=2)
    print(f"  {by_uf_path} ({len(by_uf)} states)")

    stats_path = DATABASE_DIR / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"  {stats_path}")

    # Print summary
    print()
    print("=" * 60)
    print(f"  Total municipalities:  {total:>6}")
    print(f"  With raw flag:         {total_with_flag:>6} ({raw_coverage_pct:.1f}%)")
    print(f"  With generated icons:  {total_with_icons:>6} ({coverage_pct:.1f}%)")
    print(f"  Missing flags:         {total - total_with_flag:>6}")
    print("=" * 60)
    print()

    # Per-state table
    print(f"{'UF':<4} {'Total':>6} {'Flag':>6} {'Icons':>6} {'Coverage':>10}")
    print("-" * 36)
    for uf_key in sorted(uf_stats.keys()):
        s = uf_stats[uf_key]
        print(
            f"{uf_key:<4} {s['total']:>6} {s['with_flag']:>6} "
            f"{s['with_icons']:>6} {s['coverage_pct']:>9.1f}%"
        )


if __name__ == "__main__":
    build_database()
