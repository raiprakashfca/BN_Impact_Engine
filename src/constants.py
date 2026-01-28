from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import uuid

import streamlit as st

from .constituents import fetch_banknifty_constituents


@dataclass(frozen=True)
class AppConfig:
    client_id: str
    secret_key: str
    redirect_uri: str

    app_id: str
    index_symbol: str
    constituents: list[str]
    cache_dir: str


def _ensure_dir(path: str) -> str:
    p = Path(path).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def load_config() -> AppConfig:
    """
    Load config from Streamlit secrets with safe fallbacks so the UI can render
    even if secrets are missing.
    """

    # Defaults (safe)
    app_id = str(os.getenv("BN_IMPACT_APP_ID", "") or str(uuid.uuid4())[:8])
    index_symbol = os.getenv("BN_IMPACT_INDEX_SYMBOL", "BANKNIFTY")
    cache_dir = _ensure_dir(os.getenv("BN_IMPACT_CACHE_DIR", ".cache"))

    # Read secrets if available
    s = getattr(st, "secrets", {}) or {}
    fy = {}
    try:
        fy = s.get("fyers", {}) if hasattr(s, "get") else {}
    except Exception:
        fy = {}

    client_id = str(fy.get("client_id", "")) if isinstance(fy, dict) else ""
    secret_key = str(fy.get("secret_key", "")) if isinstance(fy, dict) else ""
    redirect_uri = str(fy.get("redirect_uri", "")) if isinstance(fy, dict) else ""

    # common alternate key
    if not secret_key and isinstance(fy, dict):
        secret_key = str(fy.get("secret", ""))

    # Constituents: allow override via secrets, else fetch dynamically
    constituents: list[str] = []
    try:
        override = s.get("constituents") if hasattr(s, "get") else None
        if isinstance(override, (list, tuple)) and override:
            constituents = [str(x).strip() for x in override if str(x).strip()]
    except Exception:
        constituents = []

    if not constituents:
        res = fetch_banknifty_constituents()
        constituents = res.fyers_symbols if res.fyers_symbols else []

    return AppConfig(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        app_id=app_id,
        index_symbol=index_symbol,
        constituents=constituents,
        cache_dir=cache_dir,
    )
