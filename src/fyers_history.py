from __future__ import annotations
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd
import pytz
from fyers_apiv3 import fyersModel

IST = pytz.timezone("Asia/Kolkata")

@dataclass
class HistorySpec:
    symbol: str
    resolution: str  # "1" for 1-min, "5" for 5-min, "1D" for daily
    date_format: str = "1"  # 1 = yyyy-mm-dd
    cont_flag: str = "1"

def _to_ymd(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def _chunk_ranges(start: date, end: date, max_days: int) -> list[tuple[date, date]]:
    out = []
    cur = start
    while cur <= end:
        nxt = min(end, cur + timedelta(days=max_days - 1))
        out.append((cur, nxt))
        cur = nxt + timedelta(days=1)
    return out

def _parse_candles(resp: dict) -> pd.DataFrame:
    candles = resp.get("candles") or []
    if not candles:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","dt"])
    df = pd.DataFrame(candles, columns=["ts","open","high","low","close","volume"])
    df["dt"] = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_convert(IST)
    return df

def get_fyers_client(client_id: str, access_token: str):
    token = f"{client_id}:{access_token}"
    return fyersModel.FyersModel(client_id=client_id, token=token, log_path=None)

def fetch_history_chunk(fyers, spec: HistorySpec, start: date, end: date, sleep_s: float = 0.2) -> pd.DataFrame:
    payload = {
        "symbol": spec.symbol,
        "resolution": spec.resolution,
        "date_format": spec.date_format,
        "range_from": _to_ymd(start),
        "range_to": _to_ymd(end),
        "cont_flag": spec.cont_flag,
    }
    resp = fyers.history(data=payload)
    time.sleep(sleep_s)
    if not isinstance(resp, dict):
        raise RuntimeError(f"Unexpected response: {resp}")
    return _parse_candles(resp)

def fetch_history(fyers, spec: HistorySpec, start: date, end: date, max_days_per_req: int = 100) -> pd.DataFrame:
    parts = []
    for a, b in _chunk_ranges(start, end, max_days=max_days_per_req):
        parts.append(fetch_history_chunk(fyers, spec, a, b))
    if not parts:
        return pd.DataFrame(columns=["ts","open","high","low","close","volume","dt"])
    df = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["ts"]).sort_values("ts")
    return df.reset_index(drop=True)

def has_window_data(df: pd.DataFrame, day: date, start_hm=(15,0), end_hm=(15,30)) -> bool:
    if df.empty:
        return False
    start_dt = IST.localize(datetime(day.year, day.month, day.day, start_hm[0], start_hm[1]))
    end_dt = IST.localize(datetime(day.year, day.month, day.day, end_hm[0], end_hm[1]))
    w = df[(df["dt"] >= start_dt) & (df["dt"] <= end_dt)]
    return len(w) >= 10
