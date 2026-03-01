"""
Shared BrasilAPI + ViaCEP fetch logic for the CEP pipeline.

Used by scrape.py, sync.py, and any script that needs to look up
a single CEP from external APIs.
"""

from __future__ import annotations

import logging
import time

import requests

from config import REQUEST_TIMEOUT, VIACEP_BASE_URL, VIACEP_DELAY_SECONDS

log = logging.getLogger(__name__)

MAX_RETRIES = 3
BRASILAPI_URL = "https://brasilapi.com.br/api/cep/v2"


def create_session() -> requests.Session:
    """Return a requests.Session with standard headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "ceps-br-pipeline/1.0",
        "Accept": "application/json",
    })
    return session


def fetch_cep(cep: str, session: requests.Session) -> dict | None:
    """Look up a single CEP — BrasilAPI first, ViaCEP fallback."""
    return _fetch_brasilapi(cep, session) or _fetch_viacep(cep, session)


def _fetch_brasilapi(cep: str, session: requests.Session) -> dict | None:
    """BrasilAPI returns: cep, state, city, neighborhood, street.

    Does NOT return ibge or ddd — callers must preserve those from
    existing data when the returned value is None.
    """
    url = f"{BRASILAPI_URL}/{cep}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "cep": str(data.get("cep", "")).replace("-", ""),
                    "logradouro": data.get("street") or "",
                    "complemento": "",
                    "bairro": data.get("neighborhood") or "",
                    "localidade": data.get("city") or "",
                    "uf": data.get("state") or "",
                    "ibge": None,   # not available — caller must preserve
                    "ddd": None,    # not available — caller must preserve
                    "source": "correios",
                }
            if resp.status_code in (400, 404):
                return None
            if resp.status_code == 429:
                time.sleep(2 * attempt)
                continue
        except requests.exceptions.RequestException:
            if attempt < MAX_RETRIES:
                time.sleep(1 * attempt)
    return None


def _fetch_viacep(cep: str, session: requests.Session) -> dict | None:
    """ViaCEP individual lookup: GET /ws/{cep}/json/"""
    url = f"{VIACEP_BASE_URL}/{cep}/json/"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and not data.get("erro"):
                    return {
                        "cep": data.get("cep", "").replace("-", ""),
                        "logradouro": data.get("logradouro", ""),
                        "complemento": data.get("complemento", ""),
                        "bairro": data.get("bairro", ""),
                        "localidade": data.get("localidade", ""),
                        "uf": data.get("uf", ""),
                        "ibge": data.get("ibge", ""),
                        "ddd": data.get("ddd", ""),
                        "source": "correios",
                    }
                return None
            if resp.status_code in (400, 404):
                return None
            if resp.status_code == 429:
                time.sleep(2 * attempt)
                continue
        except requests.exceptions.RequestException:
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
    return None
