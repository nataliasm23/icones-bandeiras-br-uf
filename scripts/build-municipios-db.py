#!/usr/bin/env python3
"""
Build a clean municipalities database from IBGE API data.

Sources:
- IBGE Localidades API: https://servicodados.ibge.gov.br/api/v1/localidades/municipios
- Wikidata SPARQL: flag images (P41) for Brazilian municipalities

Outputs:
- data/municipios.json          → Full database with all fields
- data/municipios-by-uf.json    → Grouped by state (UF)
- data/municipios.csv           → CSV for easy viewing
- data/stats.json               → Summary statistics
"""

import json
import csv
import unicodedata
import re
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent.parent / "data"

UF_CODES = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15",
    "AP": "16", "TO": "17", "MA": "21", "PI": "22", "CE": "23",
    "RN": "24", "PB": "25", "PE": "26", "AL": "27", "SE": "28",
    "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35",
    "PR": "41", "SC": "42", "RS": "43", "MS": "50", "MT": "51",
    "GO": "52", "DF": "53",
}

UF_NAMES = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas", "RR": "Roraima",
    "PA": "Pará", "AP": "Amapá", "TO": "Tocantins", "MA": "Maranhão",
    "PI": "Piauí", "CE": "Ceará", "RN": "Rio Grande do Norte",
    "PB": "Paraíba", "PE": "Pernambuco", "AL": "Alagoas", "SE": "Sergipe",
    "BA": "Bahia", "MG": "Minas Gerais", "ES": "Espírito Santo",
    "RJ": "Rio de Janeiro", "SP": "São Paulo", "PR": "Paraná",
    "SC": "Santa Catarina", "RS": "Rio Grande do Sul",
    "MS": "Mato Grosso do Sul", "MT": "Mato Grosso", "GO": "Goiás",
    "DF": "Distrito Federal",
}

REGION_MAP = {
    "N": "Norte", "NE": "Nordeste", "SE": "Sudeste",
    "S": "Sul", "CO": "Centro-Oeste",
}


def slugify(text: str) -> str:
    """Convert text to URL/filename-safe slug."""
    # Normalize unicode (remove accents)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # Lowercase and replace non-alphanumeric with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    text = text.strip("-")
    return text


def build_wikipedia_slug(name: str) -> str:
    """Build the pt.wikipedia.org article slug for a municipality."""
    return name.replace(" ", "_")


def build_wikidata_search_name(name: str, uf: str) -> str:
    """Build search string for Wikidata queries."""
    return f"{name} ({UF_NAMES.get(uf, uf)})"


def main():
    # Load raw IBGE data
    raw_path = DATA_DIR / "ibge-municipios-raw.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    print(f"Loaded {len(raw_data)} municipalities from IBGE API")

    # Parse into clean structure
    municipios = []
    by_uf = defaultdict(list)

    for item in raw_data:
        # Extract UF info from microrregiao or regiao-imediata (fallback for newer municipalities)
        micro = item.get("microrregiao")
        regiao_imediata = item.get("regiao-imediata")

        if micro and micro.get("mesorregiao"):
            uf_data = micro["mesorregiao"]["UF"]
            micro_nome = micro["nome"]
            meso_nome = micro["mesorregiao"]["nome"]
        elif regiao_imediata and regiao_imediata.get("regiao-intermediaria"):
            uf_data = regiao_imediata["regiao-intermediaria"]["UF"]
            micro_nome = regiao_imediata["nome"]
            meso_nome = regiao_imediata["regiao-intermediaria"]["nome"]
        else:
            print(f"  WARNING: Skipping {item['id']} {item['nome']} - no UF data")
            continue

        uf_sigla = uf_data["sigla"]
        uf_nome = uf_data["nome"]
        regiao_sigla = uf_data["regiao"]["sigla"]
        regiao_nome = uf_data["regiao"]["nome"]

        municipio = {
            "ibge_code": item["id"],
            "name": item["nome"],
            "slug": slugify(item["nome"]),
            "uf": uf_sigla,
            "uf_name": uf_nome,
            "region": regiao_sigla,
            "region_name": regiao_nome,
            "microrregiao": micro_nome,
            "mesorregiao": meso_nome,
            # Will be populated by flag-collection scripts
            "flag_status": "pending",  # pending | found | not_found | placeholder
            "flag_source": None,  # wikidata | wikimedia | wikipedia | prefeitura | manual
            "flag_url": None,  # Original source URL
            "flag_file": None,  # Local filename in dist/
            # Wikipedia/Wikidata references
            "wikipedia_slug": build_wikipedia_slug(item["nome"]),
            "wikidata_search": build_wikidata_search_name(item["nome"], uf_sigla),
        }

        municipios.append(municipio)
        by_uf[uf_sigla].append(municipio)

    # Sort municipalities by UF, then name
    municipios.sort(key=lambda m: (m["uf"], m["name"]))
    for uf in by_uf:
        by_uf[uf].sort(key=lambda m: m["name"])

    # Write full database
    out_path = DATA_DIR / "municipios.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(municipios)} municipalities to {out_path}")

    # Write grouped by UF
    by_uf_path = DATA_DIR / "municipios-by-uf.json"
    with open(by_uf_path, "w", encoding="utf-8") as f:
        json.dump(dict(by_uf), f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(by_uf)} states to {by_uf_path}")

    # Write CSV
    csv_path = DATA_DIR / "municipios.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "ibge_code", "name", "slug", "uf", "uf_name",
            "region", "region_name", "microrregiao", "mesorregiao",
            "flag_status", "flag_source", "flag_url", "flag_file",
            "wikipedia_slug", "wikidata_search",
        ])
        writer.writeheader()
        writer.writerows(municipios)
    print(f"Wrote CSV to {csv_path}")

    # Generate statistics
    region_counts = defaultdict(int)
    uf_counts = {}
    for m in municipios:
        region_counts[m["region_name"]] += 1
    for uf, items in by_uf.items():
        uf_counts[uf] = len(items)

    # Sort UF counts descending
    uf_counts_sorted = dict(sorted(uf_counts.items(), key=lambda x: x[1], reverse=True))

    stats = {
        "total_municipios": len(municipios),
        "total_ufs": len(by_uf),
        "by_region": dict(region_counts),
        "by_uf": uf_counts_sorted,
        "flag_coverage": {
            "found": sum(1 for m in municipios if m["flag_status"] == "found"),
            "pending": sum(1 for m in municipios if m["flag_status"] == "pending"),
            "not_found": sum(1 for m in municipios if m["flag_status"] == "not_found"),
            "placeholder": sum(1 for m in municipios if m["flag_status"] == "placeholder"),
        },
        "top_10_states": list(uf_counts_sorted.items())[:10],
    }

    stats_path = DATA_DIR / "stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"Wrote stats to {stats_path}")

    # Print summary
    print("\n" + "=" * 60)
    print(f"  MUNICIPALITIES DATABASE - BRAZIL")
    print("=" * 60)
    print(f"  Total municipalities: {len(municipios)}")
    print(f"  Total states (UFs):   {len(by_uf)}")
    print()
    print("  By region:")
    for region, count in sorted(region_counts.items()):
        print(f"    {region:20s} {count:5d}")
    print()
    print("  Top 10 states:")
    for uf, count in list(uf_counts_sorted.items())[:10]:
        print(f"    {uf} ({UF_NAMES.get(uf, ''):25s}) {count:5d}")
    print()
    print("  Flag collection status:")
    print(f"    Pending:     {stats['flag_coverage']['pending']:5d}")
    print(f"    Found:       {stats['flag_coverage']['found']:5d}")
    print(f"    Not found:   {stats['flag_coverage']['not_found']:5d}")
    print(f"    Placeholder: {stats['flag_coverage']['placeholder']:5d}")
    print("=" * 60)


if __name__ == "__main__":
    main()
