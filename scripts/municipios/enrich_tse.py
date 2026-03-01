#!/usr/bin/env python3
"""
Enrich municipios.json with TSE 2024 election data.

Downloads (if needed) and parses TSE candidate data for 2024 municipal elections.
Adds: codigo_tse, prefeito_eleito_2024, prefeito_partido, prefeito_coligacao,
      vice_prefeito_2024, vice_partido, vereadores_eleitos (count),
      prefeito_genero, prefeito_cor_raca, prefeito_escolaridade.

Source: TSE - Tribunal Superior Eleitoral
  https://dadosabertos.tse.jus.br/dataset/candidatos-2024

Usage:
  python3 scripts/municipios/enrich_tse.py [--dry-run]
"""

import csv
import json
import os
import sys
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data"
MUNICIPIOS_JSON = DATA_DIR / "municipios.json"

TSE_URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/consulta_cand_2024.zip"
TSE_CACHE_DIR = Path("/tmp/tse_cand_2024")
TSE_ZIP = Path("/tmp/consulta_cand_2024.zip")

# TSE column indices (from CSV header)
COL_TURNO = 5       # NR_TURNO
COL_UF = 10         # SG_UF
COL_TSE_CODE = 11   # SG_UE (TSE municipality code)
COL_MUN_NAME = 12   # NM_UE
COL_CARGO = 13      # CD_CARGO (11=prefeito, 12=vice, 13=vereador)
COL_NM_CAND = 17    # NM_CANDIDATO
COL_NM_URNA = 18    # NM_URNA_CANDIDATO
COL_PARTIDO = 26    # SG_PARTIDO
COL_COLIGACAO = 33  # NM_COLIGACAO
COL_GENERO = 39     # DS_GENERO
COL_ESCOLARIDADE = 41  # DS_GRAU_INSTRUCAO
COL_COR_RACA = 45   # DS_COR_RACA
COL_SQ_CAND = 15    # SQ_CANDIDATO (unique candidate ID)
COL_SIT_TOT = 49    # DS_SIT_TOT_TURNO

# Manual TSE→IBGE mappings for known spelling differences
MANUAL_TSE_TO_IBGE = {
    # TSE_CODE: IBGE_CODE
    "34118": 2905602,  # Camacan (BA) - TSE: CAMACÃ
    "44571": 3122900,  # Dona Euzébia (MG) - TSE: DONA EUSÉBIA
    "17035": 2405306,  # Januário Cicco (RN) - TSE name: BOA SAÚDE (modern name)
    "05290": 1506500,  # Santa Izabel do Pará (PA) - TSE: SANTA ISABEL DO PARÁ
    "00256": 1100098,  # Espigão D'Oeste (RO) - TSE: ESPIGÃO DO OESTE
    "04120": 1502954,  # Eldorado do Carajás (PA) - TSE: ELDORADO DOS CARAJÁS
    "41360": 3150539,  # Pingo-d'Água (MG) - TSE: PINGO D'ÁGUA
    "41092": 3105509,  # Barão do Monte Alto (MG) - TSE: Barão de Monte Alto
    "41203": 3145455,  # Olhos-d'Água (MG)
    "40827": 3165560,  # Sem-Peixe (MG)
    "16039": 2400208,  # Açu (RN) - TSE name: ASSÚ
    "53031": 3165206,  # São Tomé das Letras (MG) - TSE: SÃO THOMÉ
    "91553": 5107800,  # Santo Antônio de Leverger (MT) - TSE: DO LEVERGER
    "71013": 3550001,  # São Luiz do Paraitinga (SP) - TSE: SÃO LUÍS
    "31011": 2800100,  # Amparo do São Francisco (SE) - TSE: DE SÃO FRANCISCO
    "00337": 1100346,  # Alvorada D'Oeste (RO) - TSE: DO OESTE
    "16233": 2401206,  # Arês (RN) - TSE name: AREZ
}


def normalize_name(s: str) -> str:
    """Remove accents, uppercase, strip."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.upper().strip()


def download_tse_data():
    """Download and extract TSE 2024 candidate data if not cached."""
    if TSE_CACHE_DIR.exists() and any(TSE_CACHE_DIR.glob("*.csv")):
        print(f"  Using cached TSE data in {TSE_CACHE_DIR}")
        return

    TSE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if not TSE_ZIP.exists():
        print(f"  Downloading TSE 2024 data from {TSE_URL}...")
        urllib.request.urlretrieve(TSE_URL, TSE_ZIP)
        print(f"  Downloaded {TSE_ZIP.stat().st_size / 1024 / 1024:.1f} MB")

    print(f"  Extracting to {TSE_CACHE_DIR}...")
    with zipfile.ZipFile(TSE_ZIP) as zf:
        for name in zf.namelist():
            if name.endswith(".csv") and "BRASIL" not in name:
                zf.extract(name, TSE_CACHE_DIR)
    print(f"  Extracted {len(list(TSE_CACHE_DIR.glob('*.csv')))} state CSV files")


def build_tse_ibge_mapping(municipios):
    """Build TSE code → IBGE code mapping using name+UF matching."""
    ibge_by_name_uf = {}
    for m in municipios:
        key = (normalize_name(m["name"]), m["uf"])
        ibge_by_name_uf[key] = m["ibge_code"]

    # Also build with more aggressive normalization (remove all non-alpha)
    ibge_by_clean_uf = {}
    for m in municipios:
        clean = "".join(c for c in normalize_name(m["name"]) if c.isalpha())
        key = (clean, m["uf"])
        ibge_by_clean_uf[key] = m["ibge_code"]

    return ibge_by_name_uf, ibge_by_clean_uf


def parse_tse_elections():
    """Parse all TSE CSV files and extract election results."""
    # Per TSE municipality: accumulate candidates, dedup by SQ_CANDIDATO
    # When turno 2 exists, the TSE file repeats all candidates — keep highest turno
    data = {}

    for csv_file in sorted(TSE_CACHE_DIR.glob("*.csv")):
        with open(csv_file, "r", encoding="latin-1") as f:
            reader = csv.reader(f, delimiter=";", quotechar='"')
            next(reader)  # skip header
            for row in reader:
                if len(row) < 50:
                    continue

                tse_code = row[COL_TSE_CODE].strip().strip('"')
                turno = int(row[COL_TURNO].strip().strip('"'))
                cargo = row[COL_CARGO].strip().strip('"')
                sit = row[COL_SIT_TOT].strip().strip('"')
                uf = row[COL_UF].strip().strip('"')
                mun_name = row[COL_MUN_NAME].strip().strip('"')
                sq_cand = row[COL_SQ_CAND].strip().strip('"')

                if tse_code not in data:
                    data[tse_code] = {"uf": uf, "name": mun_name, "candidates": {}}

                cand_entry = {
                    "turno": turno,
                    "cargo": cargo,
                    "sit": sit,
                    "nome": row[COL_NM_CAND].strip().strip('"'),
                    "nome_urna": row[COL_NM_URNA].strip().strip('"'),
                    "partido": row[COL_PARTIDO].strip().strip('"'),
                    "coligacao": row[COL_COLIGACAO].strip().strip('"'),
                    "genero": row[COL_GENERO].strip().strip('"'),
                    "escolaridade": row[COL_ESCOLARIDADE].strip().strip('"'),
                    "cor_raca": row[COL_COR_RACA].strip().strip('"'),
                }

                # Deduplicate: keep highest turno per candidate
                if sq_cand not in data[tse_code]["candidates"] or turno > data[tse_code]["candidates"][sq_cand]["turno"]:
                    data[tse_code]["candidates"][sq_cand] = cand_entry

    # Now extract winners per municipality
    results = {}

    for tse_code, mun_data in data.items():
        candidates = list(mun_data["candidates"].values())
        uf = mun_data["uf"]
        mun_name = mun_data["name"]

        result = {
            "tse_code": tse_code,
            "uf": uf,
            "municipio_tse": mun_name,
        }

        # --- Prefeito (cargo 11) ---
        prefeitos = [c for c in candidates if c["cargo"] == "11"]
        # Prefer highest turno with "ELEITO" status
        eleitos = [c for c in prefeitos if c["sit"] == "ELEITO"]
        if eleitos:
            # Pick the one from highest turno
            winner = max(eleitos, key=lambda x: x["turno"])
            result["prefeito_eleito_2024"] = winner["nome"]
            result["prefeito_nome_urna"] = winner["nome_urna"]
            result["prefeito_partido"] = winner["partido"]
            result["prefeito_coligacao"] = winner["coligacao"]
            result["prefeito_genero"] = winner["genero"]
            result["prefeito_escolaridade"] = winner["escolaridade"]
            result["prefeito_cor_raca"] = winner["cor_raca"]

        # --- Vice-prefeito (cargo 12) ---
        vices = [c for c in candidates if c["cargo"] == "12"]
        eleitos_v = [c for c in vices if c["sit"] == "ELEITO"]
        if eleitos_v:
            winner_v = max(eleitos_v, key=lambda x: x["turno"])
            result["vice_prefeito_2024"] = winner_v["nome"]
            result["vice_partido"] = winner_v["partido"]

        # --- Vereadores (cargo 13) ---
        # Vereadores use "ELEITO POR QP" (quociente partidário) or "ELEITO POR MÉDIA"
        vereadores = [c for c in candidates if c["cargo"] == "13"]
        eleitos_ver = [
            c for c in vereadores
            if c["sit"] in ("ELEITO POR QP", "ELEITO POR MÉDIA", "ELEITO")
        ]
        result["vereadores_eleitos"] = len(eleitos_ver)

        results[tse_code] = result

    return results


def run(*, dry_run=False):
    """Enrich municipios.json with TSE 2024 election data."""
    print("=== TSE 2024 Election Data Enrichment ===\n")

    # Download/cache TSE data
    download_tse_data()

    # Load municipios
    print(f"\nLoading {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "r", encoding="utf-8") as f:
        municipios = json.load(f)
    print(f"  {len(municipios)} municipalities loaded")

    # Build TSE→IBGE mapping
    ibge_by_name_uf, ibge_by_clean_uf = build_tse_ibge_mapping(municipios)

    # Parse TSE elections
    print("\nParsing TSE election results...")
    tse_results = parse_tse_elections()
    print(f"  {len(tse_results)} municipalities in TSE data")

    # Count prefeitos, vices, vereadores
    with_prefeito = sum(1 for r in tse_results.values() if "prefeito_eleito_2024" in r)
    with_vice = sum(1 for r in tse_results.values() if "vice_prefeito_2024" in r)
    total_vereadores = sum(r.get("vereadores_eleitos", 0) for r in tse_results.values())
    print(f"  Elected mayors: {with_prefeito}")
    print(f"  Elected vice-mayors: {with_vice}")
    print(f"  Elected vereadores: {total_vereadores}")

    # Map TSE→IBGE
    print("\nMapping TSE codes to IBGE codes...")
    tse_to_ibge = {}
    unmatched = []

    for tse_code, result in tse_results.items():
        # Try manual mapping first
        if tse_code in MANUAL_TSE_TO_IBGE:
            tse_to_ibge[tse_code] = MANUAL_TSE_TO_IBGE[tse_code]
            continue

        mun_name = result["municipio_tse"]
        uf = result["uf"]

        # Try exact normalized match
        key = (normalize_name(mun_name), uf)
        if key in ibge_by_name_uf:
            tse_to_ibge[tse_code] = ibge_by_name_uf[key]
            continue

        # Try aggressive clean match
        clean = "".join(c for c in normalize_name(mun_name) if c.isalpha())
        key2 = (clean, uf)
        if key2 in ibge_by_clean_uf:
            tse_to_ibge[tse_code] = ibge_by_clean_uf[key2]
            continue

        unmatched.append((tse_code, mun_name, uf))

    print(f"  Matched: {len(tse_to_ibge)}")
    if unmatched:
        print(f"  Unmatched: {len(unmatched)}")
        for t, n, u in unmatched[:10]:
            print(f"    {t}: {n} ({u})")

    # Build IBGE→TSE result map
    ibge_to_tse = {}
    for tse_code, ibge_code in tse_to_ibge.items():
        ibge_to_tse[ibge_code] = tse_results[tse_code]

    if dry_run:
        print(f"\n[DRY RUN] Would enrich {len(ibge_to_tse)} municipalities with TSE data")
        # Show sample
        sample_code = list(ibge_to_tse.keys())[:3]
        for code in sample_code:
            r = ibge_to_tse[code]
            print(f"  {code}: {r.get('prefeito_eleito_2024', 'N/A')} ({r.get('prefeito_partido', '?')}), "
                  f"{r.get('vereadores_eleitos', 0)} vereadores")
        return

    # Enrich municipios
    print(f"\nEnriching municipalities...")
    enriched = 0
    for m in municipios:
        ibge_code = m["ibge_code"]
        if ibge_code not in ibge_to_tse:
            continue

        tse = ibge_to_tse[ibge_code]
        m["codigo_tse"] = tse["tse_code"]

        if "prefeito_eleito_2024" in tse:
            m["prefeito_eleito_2024"] = tse["prefeito_eleito_2024"]
            m["prefeito_nome_urna"] = tse.get("prefeito_nome_urna")
            m["prefeito_partido"] = tse.get("prefeito_partido")
            m["prefeito_coligacao"] = tse.get("prefeito_coligacao")
            m["prefeito_genero"] = tse.get("prefeito_genero")
            m["prefeito_escolaridade"] = tse.get("prefeito_escolaridade")
            m["prefeito_cor_raca"] = tse.get("prefeito_cor_raca")

        if "vice_prefeito_2024" in tse:
            m["vice_prefeito_2024"] = tse["vice_prefeito_2024"]
            m["vice_partido"] = tse.get("vice_partido")

        m["vereadores_eleitos"] = tse.get("vereadores_eleitos", 0)
        enriched += 1

    print(f"  Enriched {enriched} / {len(municipios)} municipalities")

    # Save
    print(f"\nSaving {MUNICIPIOS_JSON}...")
    with open(MUNICIPIOS_JSON, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)
    print("  Done!")

    # Summary
    print(f"\n=== Summary ===")
    print(f"  Municipalities with TSE code: {enriched}")
    print(f"  With elected mayor: {sum(1 for m in municipios if m.get('prefeito_eleito_2024'))}")
    print(f"  With vice-mayor: {sum(1 for m in municipios if m.get('vice_prefeito_2024'))}")
    print(f"  Total elected vereadores: {sum(m.get('vereadores_eleitos', 0) for m in municipios)}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
