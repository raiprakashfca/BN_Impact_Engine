# filename: src/symbol_discovery.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

from .fyers_history import IST, get_fyers_client
from .engines import get_history_cached


@dataclass
class SymbolCandidate:
    symbol: str
    label: str


SYMBOL_MASTER_URLS = [
    # FYERS public Symbol Master files (no auth)
    # Docs/community references point to these files.
    "https://public.fyers.in/sym_details/NSE_CM.csv",
    "https://public.fyers.in/sym_details/NSE_FO.csv",
]

REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/csv,*/*",
}


def _find_symbol_column(df: pd.DataFrame) -> int:
    """
    Symbol master files often have NO header. We find the column that looks like FYERS symbols:
    e.g. NSE:TATAMOTORS-EQ, NSE:NIFTY50-INDEX, etc.
    """
    sym_regex = re.compile(r"^(NSE|BSE):[A-Z0-9_.-]+$", re.IGNORECASE)
    best_col = -1
    best_hits = 0

    for col in df.columns:
        s = df[col].astype(str).str.strip()
        hits = s.str.match(sym_regex).sum()
        if hits > best_hits:
            best_hits = hits
            best_col = col

    if best_col == -1 or best_hits < 5:
        raise ValueError("Could not infer FYERS symbol column from symbol master file.")
    return int(best_col)


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def load_fyers_symbol_master() -> pd.DataFrame:
    """
    Download + concatenate a couple of FYERS symbol master files.
    Cached for 24h.
    """
    frames: list[pd.DataFrame] = []
    last_err = ""

    for url in SYMBOL_MASTER_URLS:
        try:
            r = requests.get(url, headers=REQ_HEADERS, timeout=30)
            if r.status_code != 200 or not r.text:
                last_err = f"{url} -> {r.status_code}"
                continue

            df = pd.read_csv(pd.io.common.StringIO(r.text), header=None)
            sym_col = _find_symbol_column(df)
            out = pd.DataFrame({"fyers_symbol": df[sym_col].astype(str).str.strip()})
            out["source_url"] = url
            frames.append(out.dropna())
        except Exception as e:
            last_err = f"{url} failed: {e}"

    if not frames:
        raise ValueError(f"Failed to load FYERS symbol master. Last error: {last_err}")

    all_df = pd.concat(frames, ignore_index=True).drop_duplicates()
    return all_df


def find_banknifty_index_candidates() -> list[SymbolCandidate]:
    """
    Returns candidate symbols likely to be BANKNIFTY index symbols.
    We search for '-INDEX' + keyword variants.
    """
    df = load_fyers_symbol_master()

    s = df["fyers_symbol"].astype(str).str.upper()

    # Index-like symbols
    idx_mask = s.str.endswith("-INDEX")

    # BANKNIFTY naming variants seen in practice
    kw_mask = (
        s.str.contains("NIFTYBANK") |
        s.str.contains("NIFTY_BANK") |
        s.str.contains("BANKNIFTY") |
        s.str.contains("NIFTY BANK")
    )

    cand = df[idx_mask & kw_mask].copy()
    if cand.empty:
        # fallback: sometimes index symbols may not end with -INDEX (rare)
        cand = df[kw_mask].copy()

    # Rank likely candidates first
    def score(sym: str) -> int:
        sym = sym.upper()
        sc = 0
        if "NIFTYBANK" in sym: sc += 10
        if "BANKNIFTY" in sym: sc += 8
        if sym.endswith("-INDEX"): sc += 6
        if sym.startswith("NSE:"): sc += 2
        return sc

    cand["score"] = cand["fyers_symbol"].map(score)
    cand = cand.sort_values(["score", "fyers_symbol"], ascending=[False, True]).head(30)

    out: list[SymbolCandidate] = []
    for _, row in cand.iterrows():
        out.append(SymbolCandidate(symbol=row["fyers_symbol"], label=f'{row["fyers_symbol"]}  ({row["source_url"]})'))
    return out


def validate_symbol_history(
    client_id: str,
    access_token: str,
    symbol: str,
    cache_dir,
    probe_day: date | None = None,
) -> tuple[bool, str]:
    """
    Validates by fetching a tiny intraday slice (1-min) for the symbol.
    Returns (ok, message).
    """
    if probe_day is None:
        probe_day = date.today()

    fyers = get_fyers_client(client_id, access_token)

    # Probe a small window; if market closed/holiday, we still accept "no data",
    # but reject "valid symbol" errors.
    start = probe_day
    end = probe_day

    try:
        df = get_history_cached(cache_dir, fyers, symbol, "1", start, end)
        if df is None or df.empty:
            return True, "Symbol is valid (history call succeeded). No candles returned for probe day."
        return True, f"Symbol is valid. Returned {len(df)} candles for probe day."
    except Exception as e:
        msg = str(e)
        # FYERS often returns "Please provide valid symbol" for invalid ones
        if "valid symbol" in msg.lower():
            return False, f"Invalid symbol per FYERS: {msg}"
        return False, f"History validation failed: {msg}"
