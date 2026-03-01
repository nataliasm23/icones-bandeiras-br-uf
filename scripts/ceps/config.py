"""
Configurações do pipeline de coleta de CEPs.
Faixas de CEP por UF baseadas na definição dos Correios.
"""

import os
from pathlib import Path

# === Paths ===
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root (up from scripts/ceps/)
SCRIPTS_DIR = BASE_DIR / "scripts" / "ceps"
DATA_DIR = BASE_DIR / "data" / "ceps"
MERGED_DIR = DATA_DIR / "merged"
DATABASE_DIR = BASE_DIR / "database"
CHECKPOINT_DIR = SCRIPTS_DIR / "checkpoint"
UNIFIED_SQLITE = DATABASE_DIR / "municipios-br.sqlite"

MUNICIPIOS_JSON = DATA_DIR.parent / "municipios.json"  # data/municipios.json (source)

# Ensure dirs exist
for d in [DATA_DIR, MERGED_DIR, DATABASE_DIR, CHECKPOINT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# === Rate limits ===
VIACEP_DELAY_SECONDS = 0.35  # ~3 req/sec
VIACEP_BASE_URL = "https://viacep.com.br/ws"
REQUEST_TIMEOUT = 15

# === Faixas de CEP por UF (Correios) ===
# Formato: (prefixo_inicio, prefixo_fim) — primeiros 5 dígitos × 1000
CEP_RANGES_BY_UF = {
    "AC": [(69900, 69999)],
    "AL": [(57000, 57999)],
    "AM": [(69000, 69299), (69400, 69899)],
    "AP": [(68900, 68999)],
    "BA": [(40000, 48999)],
    "CE": [(60000, 63999)],
    "DF": [(70000, 72799), (73000, 73699)],
    "ES": [(29000, 29999)],
    "GO": [(72800, 72999), (73700, 76799)],
    "MA": [(65000, 65999)],
    "MG": [(30000, 39999)],
    "MS": [(79000, 79999)],
    "MT": [(78000, 78899)],
    "PA": [(66000, 68899)],
    "PB": [(58000, 58999)],
    "PE": [(50000, 56999)],
    "PI": [(64000, 64999)],
    "PR": [(80000, 87999)],
    "RJ": [(20000, 28999)],
    "RN": [(59000, 59999)],
    "RO": [(76800, 76999)],
    "RR": [(69300, 69399)],
    "RS": [(90000, 99999)],
    "SC": [(88000, 89999)],
    "SE": [(49000, 49999)],
    "SP": [(1000, 19999)],
    "TO": [(77000, 77999)],
}

UF_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá",
    "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal", "ES": "Espírito Santo",
    "GO": "Goiás", "MA": "Maranhão", "MG": "Minas Gerais", "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba", "PE": "Pernambuco",
    "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RO": "Rondônia", "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina",
    "SE": "Sergipe", "SP": "São Paulo", "TO": "Tocantins",
}

ALL_UFS = sorted(UF_NAMES.keys())


def cep_belongs_to_uf(cep: str, uf: str) -> bool:
    """Verifica se um CEP (8 dígitos) pertence à UF."""
    if len(cep) != 8 or not cep.isdigit():
        return False
    prefix = int(cep[:5])
    ranges = CEP_RANGES_BY_UF.get(uf, [])
    return any(start <= prefix <= end for start, end in ranges)


def get_uf_from_cep(cep: str) -> str | None:
    """Retorna a UF de um CEP (8 dígitos)."""
    if len(cep) != 8 or not cep.isdigit():
        return None
    prefix = int(cep[:5])
    for uf, ranges in CEP_RANGES_BY_UF.items():
        if any(start <= prefix <= end for start, end in ranges):
            return uf
    return None
