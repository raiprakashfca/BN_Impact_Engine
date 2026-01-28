from __future__ import annotations
import streamlit as st

from src.constants import load_config, AppConfig
from src.ui import sidebar_auth, tab_live, tab_backtest

st.set_page_config(page_title="BANKNIFTY Expiry Impact (FYERS)", layout="wide")

cfg = load_config()

client_id, secret_key, redirect_uri, _token = sidebar_auth(
    default_client_id=cfg.client_id,
    default_secret=cfg.secret_key,
    default_redirect=cfg.redirect_uri,
)

cfg = AppConfig(
    client_id=client_id,
    secret_key=secret_key,
    redirect_uri=redirect_uri,
    app_id=cfg.app_id,
    index_symbol=cfg.index_symbol,
    constituents=cfg.constituents,
    cache_dir=cfg.cache_dir,
)

st.title("BANKNIFTY Expiry Impact 📈")
st.caption("Estimate BANKNIFTY points per ₹1 move in constituents (last 30 mins of expiry).")

tabs = st.tabs(["Expiry Live Impact", "Expiry Backtest"])
with tabs[0]:
    tab_live(cfg)
with tabs[1]:
    tab_backtest(cfg)
