from __future__ import annotations
import hashlib
from pathlib import Path
import pandas as pd

def _key_to_path(cache_dir: Path, key: str) -> Path:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return cache_dir / f"{h}.parquet"

def load_parquet(cache_dir: Path, key: str) -> pd.DataFrame | None:
    p = _key_to_path(cache_dir, key)
    if p.exists():
        try:
            return pd.read_parquet(p)
        except Exception:
            return None
    return None

def save_parquet(cache_dir: Path, key: str, df: pd.DataFrame) -> Path:
    p = _key_to_path(cache_dir, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return p
