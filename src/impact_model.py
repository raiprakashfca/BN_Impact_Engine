from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_squared_error

@dataclass
class ImpactFit:
    betas: pd.Series
    r2: float
    rmse: float
    n_obs: int

def build_delta_matrix(bn_window: pd.DataFrame, stock_windows: dict[str, pd.DataFrame]):
    base = bn_window[["dt","close"]].copy().sort_values("dt").rename(columns={"close":"bn"})
    base["y"] = base["bn"].diff()
    base = base.dropna()

    feats = []
    merged = base[["dt","y"]]
    for sym, df in stock_windows.items():
        t = df[["dt","close"]].copy().sort_values("dt").rename(columns={"close": sym})
        t[sym] = t[sym].diff()
        t = t.dropna()
        merged = merged.merge(t[["dt", sym]], on="dt", how="inner")
        feats.append(sym)

    if merged.empty or len(merged) < 10:
        return np.array([]), np.array([[]]), feats

    y = merged["y"].to_numpy(float)
    X = merged[feats].to_numpy(float)
    return y, X, feats

def fit_impacts_ridge_positive(y: np.ndarray, X: np.ndarray, feats: list[str], alpha: float = 1.0) -> ImpactFit:
    if y.size == 0 or X.size == 0:
        return ImpactFit(betas=pd.Series(dtype=float), r2=float("nan"), rmse=float("nan"), n_obs=0)

    model = Ridge(alpha=alpha, fit_intercept=True, positive=True, random_state=42)
    model.fit(X, y)
    yhat = model.predict(X)

    r2 = float(r2_score(y, yhat))
    rmse = float(mean_squared_error(y, yhat, squared=False))
    betas = pd.Series(model.coef_, index=feats).sort_values(ascending=False)
    return ImpactFit(betas=betas, r2=r2, rmse=rmse, n_obs=int(len(y)))
