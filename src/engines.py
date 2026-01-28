from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
import pandas as pd

from .fyers_history import HistorySpec, fetch_history, get_fyers_client, IST
from .storage import load_parquet, save_parquet
from .impact_model import build_delta_matrix, fit_impacts_ridge_positive, ImpactFit
from .expiry_detect import detect_weekly_expiries_from_data, ExpiryDetectionResult

@dataclass
class BacktestResult:
    expiry_metrics: pd.DataFrame
    expiry_betas_long: pd.DataFrame
    detection: ExpiryDetectionResult

def _cache_key(symbol: str, resolution: str, start: date, end: date) -> str:
    return f"history::{symbol}::{resolution}::{start.isoformat()}::{end.isoformat()}"

def get_history_cached(cache_dir, fyers, symbol: str, resolution: str, start: date, end: date, max_days_per_req: int = 100) -> pd.DataFrame:
    key = _cache_key(symbol, resolution, start, end)
    cached = load_parquet(cache_dir, key)
    if cached is not None and not cached.empty:
        cached["dt"] = pd.to_datetime(cached["dt"]).dt.tz_convert(IST) if hasattr(pd.to_datetime(cached["dt"]).dt, "tz_convert") else pd.to_datetime(cached["dt"]).dt.tz_localize(IST)
        return cached

    df = fetch_history(fyers, HistorySpec(symbol=symbol, resolution=resolution), start, end, max_days_per_req=max_days_per_req)
    if not df.empty:
        out = df.copy()
        out["dt"] = out["dt"].astype(str)
        save_parquet(cache_dir, key, out)
    return df

def slice_window(df: pd.DataFrame, day: date, start_hm=(15,0), end_hm=(15,30)) -> pd.DataFrame:
    start_dt = IST.localize(datetime(day.year, day.month, day.day, start_hm[0], start_hm[1]))
    end_dt = IST.localize(datetime(day.year, day.month, day.day, end_hm[0], end_hm[1]))
    w = df[(df["dt"] >= start_dt) & (df["dt"] <= end_dt)].copy()
    return w.sort_values("dt")

def run_backtest(client_id: str, access_token: str, index_symbol: str, constituents: list[str], cache_dir, start: date, end: date, alpha: float = 1.0) -> BacktestResult:
    fyers = get_fyers_client(client_id, access_token)

    bn = get_history_cached(cache_dir, fyers, index_symbol, "1", start, end)
    detection = detect_weekly_expiries_from_data(bn, start, end)
    expiries = detection.expiry_dates

    stock_hist = {sym: get_history_cached(cache_dir, fyers, sym, "1", start, end) for sym in constituents}

    metrics_rows = []
    betas_rows = []

    for ex in expiries:
        bn_w = slice_window(bn, ex)
        sw = {sym: slice_window(stock_hist[sym], ex) for sym in constituents}
        y, X, feats = build_delta_matrix(bn_w, sw)
        fit: ImpactFit = fit_impacts_ridge_positive(y, X, feats, alpha=alpha)

        metrics_rows.append({"expiry": ex.isoformat(), "r2": fit.r2, "rmse": fit.rmse, "n_obs": fit.n_obs})
        for sym, beta in fit.betas.items():
            betas_rows.append({"expiry": ex.isoformat(), "symbol": sym, "beta_bn_points_per_rs1": float(beta)})

    return BacktestResult(
        expiry_metrics=pd.DataFrame(metrics_rows).sort_values("expiry"),
        expiry_betas_long=pd.DataFrame(betas_rows).sort_values(["expiry","beta_bn_points_per_rs1"], ascending=[True, False]),
        detection=detection,
    )

def run_live_snapshot(client_id: str, access_token: str, index_symbol: str, constituents: list[str], cache_dir, day: date, alpha: float = 1.0):
    fyers = get_fyers_client(client_id, access_token)

    bn = get_history_cached(cache_dir, fyers, index_symbol, "1", day, day)
    stock_hist = {sym: get_history_cached(cache_dir, fyers, sym, "1", day, day) for sym in constituents}

    bn_w = slice_window(bn, day)
    sw = {sym: slice_window(stock_hist[sym], day) for sym in constituents}
    y, X, feats = build_delta_matrix(bn_w, sw)
    fit = fit_impacts_ridge_positive(y, X, feats, alpha=alpha)

    table = fit.betas.reset_index()
    table.columns = ["symbol", "bn_points_per_rs1"]
    return fit, table
