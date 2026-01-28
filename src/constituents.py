from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
import io

import pandas as pd
import requests
import streamlit as st

@dataclass
class ConstituentsResult:
    fyers_symbols: list[str]
    nse_symbols: list[str]
    source: str
    note: str

CSV_SOURCES = [
    "https://www.niftyindices.com/IndexConstituent/ind_niftybanklist.csv",
    "https://www1.nseindia.com/content/indices/ind_niftybanklist.csv",
]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/csv;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

def _to_fyers_symbol(nse_symbol: str) -> str:
    return f"NSE:{nse_symbol.strip().upper()}-EQ"

def _parse_constituent_csv(text: str) -> Tuple[list[str], str]:
    df = pd.read_csv(io.StringIO(text))
    cols = [c.strip().lower() for c in df.columns]
    sym_col = None
    for cand in ["symbol", "sym", "ticker"]:
        if cand in cols:
            sym_col = df.columns[cols.index(cand)]
            break
    if sym_col is None:
        sym_col = df.columns[0]

    nse = (
        df[sym_col]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"NAN": ""})
    )
    nse = [s for s in nse.tolist() if s and s != ""]
    return nse, f"Parsed {len(nse)} rows from CSV."

@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_banknifty_constituents() -> ConstituentsResult:
    last_err = ""
    for url in CSV_SOURCES:
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=20)
            if resp.status_code != 200 or not resp.text:
                last_err = f"{url} returned {resp.status_code}"
                continue
            nse_syms, note = _parse_constituent_csv(resp.text)
            if not nse_syms:
                last_err = f"{url} parsed zero symbols"
                continue
            fyers_syms = [_to_fyers_symbol(s) for s in nse_syms]
            return ConstituentsResult(fyers_syms, nse_syms, url, note)
        except Exception as e:
            last_err = f"{url} failed: {e}"

    return ConstituentsResult([], [], "", f"Failed to fetch constituents. Last error: {last_err}")
