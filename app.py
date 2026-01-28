# filename: app.py
from __future__ import annotations

import streamlit as st

from src.constants import load_config, AppConfig
from src.fyers_auth import build_auth_code_url, exchange_auth_code_for_token
from src.ui import tab_live, tab_backtest

st.set_page_config(page_title="BANKNIFTY Impact Engine (FYERS)", layout="wide")

# -------- Load secrets-based config --------
cfg = load_config()

# -------- Sidebar: FYERS Login (secrets-first, no overwrite) --------
st.sidebar.header("FYERS Login")

# Initialize session state ONCE from secrets
# This prevents Streamlit text inputs from wiping defaults on reruns.
if "fyers_app_id" not in st.session_state:
    st.session_state["fyers_app_id"] = cfg.client_id  # cfg.client_id is FYERS_APP_ID in our config loader

if "fyers_secret_key" not in st.session_state:
    st.session_state["fyers_secret_key"] = cfg.secret_key

if "fyers_redirect_uri" not in st.session_state:
    st.session_state["fyers_redirect_uri"] = cfg.redirect_uri

# Optional: allow editing (OFF by default to prevent accidental blanking)
allow_edit = st.sidebar.toggle("Edit credentials", value=False)
disabled_inputs = not allow_edit

app_id = st.sidebar.text_input(
    "FYERS App ID",
    key="fyers_app_id",
    disabled=disabled_inputs,
)

secret_key = st.sidebar.text_input(
    "Secret Key",
    key="fyers_secret_key",
    type="password",
    disabled=disabled_inputs,
)

redirect_uri = st.sidebar.text_input(
    "Redirect URI",
    key="fyers_redirect_uri",
    disabled=disabled_inputs,
)

state = st.sidebar.text_input("State (optional)", value="state")

# Build login URL only if essentials exist
if app_id and redirect_uri:
    urls = build_auth_code_url(app_id, redirect_uri, state=state)
    st.sidebar.markdown(f"[Open FYERS Login]({urls.auth_code_url})")
else:
    st.sidebar.info("FYERS App ID and Redirect URI are required to generate login URL.")

auth_code = st.sidebar.text_input("Paste auth_code here", value="")

if st.sidebar.button("Generate Access Token"):
    if not (app_id and secret_key and redirect_uri and auth_code):
        st.sidebar.error("Missing App ID / Secret Key / Redirect URI / auth_code.")
    else:
        try:
            token = exchange_auth_code_for_token(app_id, secret_key, redirect_uri, auth_code.strip())
            st.session_state["fyers_access_token"] = token
            st.sidebar.success("Access token saved in this session ✅")
        except Exception as e:
            st.sidebar.error(str(e))

token = st.sidebar.text_input(
    "Access Token (session)",
    value=st.session_state.get("fyers_access_token", ""),
    type="password",
)

if token:
    st.session_state["fyers_access_token"] = token

# Rebuild config object using whatever is in session state (secrets or manual override)
cfg = AppConfig(
    client_id=app_id.strip(),
    secret_key=secret_key.strip(),
    redirect_uri=redirect_uri.strip(),
    app_id=cfg.app_id,              # kept for compatibility
    index_symbol=cfg.index_symbol,  # default index symbol (can be auto-detected in UI)
    cache_dir=cfg.cache_dir,
)

# -------- Main UI --------
st.title("BANKNIFTY Expiry Impact 📈")
st.caption("Estimate BANKNIFTY points per ₹1 move in constituents (last 30 mins of expiry).")

tabs = st.tabs(["Expiry Live Impact", "Expiry Backtest"])
with tabs[0]:
    tab_live(cfg)
with tabs[1]:
    tab_backtest(cfg)
