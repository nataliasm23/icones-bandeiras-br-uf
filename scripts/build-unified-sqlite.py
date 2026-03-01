#!/usr/bin/env python3
"""
Build the unified SQLite database from JSON sources.

Reads:
  data/municipios.json       - Source municipality data (5,571 rows)
  data/ceps/by-uf/*.json     - CEP records per UF (27 files, 918K+ rows)

Generates:
  database/municipios-br.sqlite  - Unified SQLite database with FTS5

Usage:
  python3 scripts/build-unified-sqlite.py
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATABASE_DIR = ROOT / "database"
DIST_DIR = ROOT / "dist"
MUNICIPIOS_JSON = DATA_DIR / "municipios.json"
CEPS_BY_UF_DIR = DATA_DIR / "ceps" / "by-uf"
OUTPUT_DB = DATABASE_DIR / "municipios-br.sqlite"


SCHEMA = """
CREATE TABLE municipios (
    ibge_code INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    uf TEXT NOT NULL,
    uf_name TEXT NOT NULL,
    region TEXT NOT NULL,
    region_name TEXT NOT NULL,
    microrregiao TEXT,
    mesorregiao TEXT,
    regiao_imediata TEXT,
    regiao_intermediaria TEXT,
    populacao_2022 INTEGER,
    populacao_estimada_2025 INTEGER,
    area_km2 REAL,
    densidade_demo REAL,
    latitude REAL,
    longitude REAL,
    ddd TEXT,
    cep_sede TEXT,
    gentilico TEXT,
    bioma TEXT,
    sistema_costeiro INTEGER,
    prefeito TEXT,
    pib REAL,
    pib_per_capita REAL,
    taxa_mortalidade_infantil REAL,
    indice_gini REAL,
    estabelecimentos_saude INTEGER,
    codigo_siafi TEXT,
    fuso_horario TEXT,
    capital INTEGER NOT NULL DEFAULT 0,
    has_flag INTEGER NOT NULL DEFAULT 0,
    has_icons INTEGER NOT NULL DEFAULT 0,
    flag_source TEXT,
    icons_json TEXT
);

CREATE INDEX idx_mun_uf ON municipios(uf);
CREATE INDEX idx_mun_slug ON municipios(slug);

CREATE VIRTUAL TABLE municipios_fts USING fts5(
    name, slug,
    content='municipios',
    content_rowid='ibge_code'
);

CREATE TABLE ceps (
    cep TEXT PRIMARY KEY,
    logradouro TEXT,
    complemento TEXT,
    bairro TEXT,
    localidade TEXT NOT NULL,
    uf TEXT NOT NULL,
    ibge TEXT,
    ddd TEXT,
    source TEXT NOT NULL,
    synced_at TEXT
);

CREATE INDEX idx_ceps_uf ON ceps(uf);
CREATE INDEX idx_ceps_ibge ON ceps(ibge);
CREATE INDEX idx_ceps_localidade ON ceps(localidade);
CREATE INDEX idx_ceps_synced_at ON ceps(synced_at);

CREATE VIRTUAL TABLE ceps_fts USING fts5(
    cep, logradouro, bairro, localidade
);

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


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


def insert_municipios(conn):
    """Load municipios from JSON and insert into SQLite."""
    print(f"Loading municipalities from {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
        municipios_raw = json.load(f)

    print(f"  Loaded {len(municipios_raw)} municipalities")
    print(f"  Checking generated icons in {DIST_DIR}...")

    cursor = conn.cursor()
    count = 0

    for mun in municipios_raw:
        ibge_code = mun["ibge_code"]
        slug = mun["slug"]
        uf = mun["uf"]

        # Re-check icons from dist/ (same logic as build-database.py)
        has_icons, icon_paths = check_generated_files(ibge_code, slug, uf)
        icons_json = json.dumps(icon_paths, ensure_ascii=False) if has_icons else None

        has_flag = 1 if mun.get("flag_status") == "found" else 0
        has_icons_int = 1 if has_icons else 0

        cursor.execute(
            """INSERT INTO municipios (
                ibge_code, name, slug, uf, uf_name,
                region, region_name,
                microrregiao, mesorregiao,
                regiao_imediata, regiao_intermediaria,
                populacao_2022, populacao_estimada_2025, area_km2, densidade_demo,
                latitude, longitude, ddd, cep_sede,
                gentilico, bioma, sistema_costeiro, prefeito,
                pib, pib_per_capita, taxa_mortalidade_infantil,
                indice_gini, estabelecimentos_saude,
                codigo_siafi, fuso_horario, capital,
                has_flag, has_icons, flag_source, icons_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ibge_code,
                mun["name"],
                slug,
                uf,
                mun.get("uf_name", ""),
                mun.get("region", ""),
                mun.get("region_name", ""),
                mun.get("microrregiao") or None,
                mun.get("mesorregiao") or None,
                mun.get("regiao_imediata") or None,
                mun.get("regiao_intermediaria") or None,
                mun.get("populacao_2022"),
                mun.get("populacao_estimada_2025"),
                mun.get("area_km2"),
                mun.get("densidade_demo"),
                mun.get("latitude"),
                mun.get("longitude"),
                mun.get("ddd") or None,
                mun.get("cep_sede") or None,
                mun.get("gentilico") or None,
                mun.get("bioma") or None,
                1 if mun.get("sistema_costeiro") else 0,
                mun.get("prefeito") or None,
                mun.get("pib"),
                mun.get("pib_per_capita"),
                mun.get("taxa_mortalidade_infantil"),
                mun.get("indice_gini"),
                mun.get("estabelecimentos_saude"),
                mun.get("codigo_siafi") or None,
                mun.get("fuso_horario") or None,
                1 if mun.get("capital") else 0,
                has_flag,
                has_icons_int,
                mun.get("flag_source") or None,
                icons_json,
            ),
        )
        count += 1

    # Populate FTS index
    cursor.execute(
        "INSERT INTO municipios_fts(rowid, name, slug) SELECT ibge_code, name, slug FROM municipios"
    )

    conn.commit()
    print(f"  Inserted {count} municipalities + FTS index")
    return count


def insert_ceps(conn):
    """Load CEP records from per-UF JSON files and insert into SQLite."""
    print(f"\nLoading CEPs from {CEPS_BY_UF_DIR}...")

    cursor = conn.cursor()
    total = 0

    uf_files = sorted(CEPS_BY_UF_DIR.glob("*.json"))
    if not uf_files:
        print("  WARNING: No CEP JSON files found!")
        return 0

    for uf_file in uf_files:
        uf = uf_file.stem
        with open(uf_file, "r", encoding="utf-8") as f:
            records = json.load(f)

        for rec in records:
            cursor.execute(
                """INSERT OR IGNORE INTO ceps (
                    cep, logradouro, complemento, bairro,
                    localidade, uf, ibge, ddd, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec["cep"],
                    rec.get("logradouro", ""),
                    rec.get("complemento", ""),
                    rec.get("bairro", ""),
                    rec["localidade"],
                    rec["uf"],
                    rec.get("ibge", ""),
                    rec.get("ddd", ""),
                    rec.get("source", "json-import"),
                ),
            )

        total += len(records)
        print(f"  {uf}: {len(records):>6} records")

    # Populate FTS index
    cursor.execute(
        "INSERT INTO ceps_fts(rowid, cep, logradouro, bairro, localidade) "
        "SELECT rowid, cep, logradouro, bairro, localidade FROM ceps"
    )

    conn.commit()
    print(f"  Total: {total} CEP records + FTS index")
    return total


def insert_metadata(conn, mun_count, cep_count):
    """Insert metadata stats."""
    cursor = conn.cursor()

    # Municipality stats
    row = cursor.execute(
        "SELECT COUNT(*) as total, "
        "SUM(has_flag) as with_flag, "
        "SUM(has_icons) as with_icons "
        "FROM municipios"
    ).fetchone()
    total, with_flag, with_icons = row

    stats = {
        "total_municipios": total,
        "total_with_raw_flag": with_flag,
        "total_with_icons": with_icons,
        "raw_coverage_pct": round(with_flag / total * 100, 1) if total > 0 else 0,
        "icon_coverage_pct": round(with_icons / total * 100, 1) if total > 0 else 0,
        "total_ufs": 27,
        "styles": ["full", "rounded", "circle", "square-rounded"],
        "formats": {
            "svg": ["full/svg", "rounded/svg", "circle/svg", "square-rounded/svg"],
            "png-200": ["full/png-200", "rounded/png-200", "circle/png-200", "square-rounded/png-200"],
            "png-800": ["full/png-800", "rounded/png-800", "circle/png-800", "square-rounded/png-800"],
        },
    }

    # Per-UF stats
    by_uf = {}
    for uf_row in cursor.execute(
        "SELECT uf, COUNT(*) as total, SUM(has_flag) as with_flag, SUM(has_icons) as with_icons "
        "FROM municipios GROUP BY uf ORDER BY uf"
    ):
        uf, t, wf, wi = uf_row
        by_uf[uf] = {
            "total": t,
            "with_flag": wf,
            "with_icons": wi,
            "coverage_pct": round(wi / t * 100, 1) if t > 0 else 0,
        }
    stats["by_uf"] = by_uf

    # Per-region stats
    by_region = {}
    for reg_row in cursor.execute(
        "SELECT region_name, COUNT(*) as total, SUM(has_flag) as with_flag, SUM(has_icons) as with_icons "
        "FROM municipios GROUP BY region_name ORDER BY region_name"
    ):
        rn, t, wf, wi = reg_row
        by_region[rn] = {
            "total": t,
            "with_flag": wf,
            "with_icons": wi,
            "coverage_pct": round(wi / t * 100, 1) if t > 0 else 0,
        }
    stats["by_region"] = by_region

    cursor.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        ("stats", json.dumps(stats, ensure_ascii=False)),
    )

    # CEP stats
    cep_stats = {"total_ceps": cep_count}
    by_uf_cep = {}
    for uf_row in cursor.execute(
        "SELECT uf, COUNT(*) as cnt FROM ceps GROUP BY uf ORDER BY uf"
    ):
        uf, cnt = uf_row
        by_uf_cep[uf] = cnt
    cep_stats["by_uf"] = by_uf_cep

    cursor.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        ("cep_stats", json.dumps(cep_stats, ensure_ascii=False)),
    )

    conn.commit()
    print("\n  Metadata written")


def main():
    # Remove existing database if present
    if OUTPUT_DB.exists():
        OUTPUT_DB.unlink()
        print(f"Removed existing {OUTPUT_DB}")

    print(f"Creating {OUTPUT_DB}...\n")

    conn = sqlite3.connect(str(OUTPUT_DB))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")

    # Create schema
    conn.executescript(SCHEMA)
    print("Schema created")

    # Insert data
    mun_count = insert_municipios(conn)
    cep_count = insert_ceps(conn)
    insert_metadata(conn, mun_count, cep_count)

    # Compact
    print("\nRunning VACUUM...")
    conn.execute("VACUUM")

    conn.close()

    size_mb = OUTPUT_DB.stat().st_size / (1024 * 1024)
    print(f"\nDone! {OUTPUT_DB} ({size_mb:.1f} MB)")
    print(f"  Municipalities: {mun_count}")
    print(f"  CEPs: {cep_count}")


if __name__ == "__main__":
    main()
