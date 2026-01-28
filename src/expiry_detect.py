from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
import pandas as pd

from .fyers_history import has_window_data

@dataclass
class ExpiryDetectionResult:
    expiry_dates: list[date]
    method: str

def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday

def detect_weekly_expiries_from_data(bn_df_1m: pd.DataFrame, start: date, end: date) -> ExpiryDetectionResult:
    expiries: list[date] = []
    cur = week_start(start)
    while cur <= end:
        candidates = [cur + timedelta(days=i) for i in range(0, 4)]  # Mon..Thu
        valid = [d for d in candidates if start <= d <= end and has_window_data(bn_df_1m, d)]
        if valid:
            expiries.append(max(valid))
        cur += timedelta(days=7)
    expiries = sorted(set(expiries))
    return ExpiryDetectionResult(expiry_dates=expiries, method="data-driven (Mon–Thu latest valid)")
