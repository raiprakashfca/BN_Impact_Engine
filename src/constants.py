from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
import streamlit as st

@dataclass(frozen=True)
class AppConfig:
    client_id: str
    secret_key: str
    redirect_uri: str
    app_id: str
    index_symbol: str
    constituents: list[str]
    cache_dir: Path

def _get_secret(key: str, default: str = "") -> str:
    return str(st.secrets.get(key, default) or default)

def load_config() -> AppConfig:
    client_id = _get_secret("FYERS_CLIENT_ID")
    secret_key = _get_secret("FYERS_SECRET_KEY")
    redirect_uri = _get_secret("FYERS_REDIRECT_URI")
    app_id = _get_secret("FYERS_APP_ID", client_id)
    index_symbol = _get_secret("FYERS_INDEX_SYMBOL", "NSE:NIFTYBANK-INDEX")
    cons_raw = _get_secret("FYERS_CONSTITUENTS", "[]")
    try:
        constituents = json.loads(cons_raw) if isinstance(cons_raw, str) else list(cons_raw)
    except Exception:
        constituents = []
    cache_dir = Path(_get_secret("CACHE_DIR", "data_cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        client_id=client_id.strip(),
        secret_key=secret_key.strip(),
        redirect_uri=redirect_uri.strip(),
        app_id=app_id.strip(),
        index_symbol=index_symbol.strip(),
        constituents=[str(c).strip() for c in constituents if str(c).strip()],
        cache_dir=cache_dir,
    )
