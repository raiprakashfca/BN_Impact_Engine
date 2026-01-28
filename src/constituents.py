# filename: src/constituents.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
import io
import os

import pandas as pd
import requests
import streamlit as st


@dataclass
class ConstituentsResult:
    fyers_symbols: list[str]
    nse_symbols: list[str]
    source: str
    note: str


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/csv,*/*",
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


def _download_text(url: str, timeout: int = 20) -> str:
    r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def fetch_banknifty_constituents() -> ConstituentsResult:
    """
    Streamlit Cloud-friendly constituent fetch.

    Order:
      1) NiftyIndices CSV (preferred)
      2) GitHub raw CSV fallback (you host it in your repo)
      3) (Optional) NSE legacy CSV - disabled on Streamlit Cloud due to TLS issues
    """

    # 1) NiftyIndices (usually works in cloud)
    sources = [
        ("NiftyIndices", "https://www.niftyindices.com/IndexConstituent/ind_niftybanklist.csv"),
    ]

    # 2) GitHub fallback (YOU MUST ADD THIS FILE ONCE: data/ind_niftybanklist.csv)
    # Put the file in your repo and this will be stable forever.
    github_raw = os.environ.get(
        "BN_GITHUB_CONSTITUENTS_RAW",
        "https://raw.githubusercontent.com/raiprakashfca/BN_Impact_Engine/main/data/ind_niftybanklist.csv",
    )
    sources.append(("GitHubFallback", github_raw))

    # 3) NSE legacy CSV (disabled on Streamlit Cloud because TLS breaks)
    # If you want it for local runs only, uncomment AND wrap with a toggle/env flag.
    # sources.append(("NSELegacy", "https://www1.nseindia.com/content/indices/ind_niftybanklist.csv"))

    last_err = ""
    for name, url in sources:
        try:
            text = _download_text(url)
            nse_syms, note = _parse_constituent_csv(text)
            if not nse_syms:
                last_err = f"{name} parsed zero symbols"
                continue

            fyers_syms = [_to_fyers_symbol(s) for s in nse_syms]
            return ConstituentsResult(
                fyers_symbols=fyers_syms,
                nse_symbols=nse_syms,
                source=url,
                note=f"{name}: {note}",
            )
        except Exception as e:
            last_err = f"{name} failed: {e}"

    return ConstituentsResult([], [], "", f"Failed to fetch constituents. Last error: {last_err}")
