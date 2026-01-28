# filename: src/constants.py
from __future__ import annotations
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
    cache_dir: Path


def _get_secret(key: str, default: str = "") -> str:
    return str(st.secrets.get(key, default) or default)


def load_config() -> AppConfig:
    """
    Centralised config loader.
    FYERS uses APP ID (not client id), but SDK naming is inconsistent.
    """
    app_id = _get_secret("FYERS_APP_ID")
    secret_key = _get_secret("FYERS_SECRET_KEY")
    redirect_uri = _get_secret("FYERS_REDIRECT_URI")

    index_symbol = _get_secret("FYERS_INDEX_SYMBOL", "NSE:NIFTYBANK-INDEX")
    cache_dir = Path(_get_secret("CACHE_DIR", "data_cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        client_id=app_id,     # FYERS_APP_ID used everywhere
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        app_id=app_id,
        index_symbol=index_symbol,
        cache_dir=cache_dir,
    )
