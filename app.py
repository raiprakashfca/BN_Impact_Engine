# filename: app.py
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import streamlit as st

from src.constants import load_config, AppConfig
from src.fyers_auth import build_auth_code_url, exchange_auth_code_for_token
from src.ui import tab_live, tab_backtest

st.set_page_config(page_title="BANKNIFTY Impact Engine (FYERS)", layout="wide")


# -----------------------
# Token persistence utils
# -----------------------
def _token_file(cache_dir: Path) -> Path:
    return cache_dir / "fyers_token.json"


def load_persisted_token(cache_dir: Path) -> str:
    p = _token_file(cache_dir)
    if not p.exists():
        return ""
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return str(obj.get("access_token", "") or "")
    except Exception:
        return ""


def save_persisted_token(cache_dir: Path, access_token: str) -> None:
    p = _token_file(cache_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"access_token": access_token}, indent=2), encoding="utf-8")


def clear_persisted_token(cache_dir: Path) -> None:
    p = _token_file(cache_dir)
    if p.exists():
        p.unlink(missing_ok=True)


def extract_auth_code_from_url(url: str) -> str:
    """
    Accepts full redirect URL and extracts auth_code parameter.
    """
    try:
        q = parse_qs(urlparse(url.strip()).query)
        return (q.get("auth_code", [""])[0] or "").strip()
    except Exception:
        return ""


# -------- Load secrets-based config --------
cfg = load_config()

# Seed session from secrets ONCE (prevents blank overwrite)
if "fyers_app_id" not in st.session_state:
    st.session_state["fyers_app_id"] = cfg.client_id  # FYERS_APP_ID

if "fyers_secret_key" not in st.session_state:
    st.session_state["fyers_secret_key"] = cfg.secret_key

if "fyers_redirect_uri" not in st.session_state:
    st.session_state["fyers_redirect_uri"] = cfg.redirect_uri

# Seed access token from persisted cache (survives refresh/restart)
if "fyers_access_token" not in st.session_state:
    st.session_state["fyers_access_token"] = load_persisted_token(cfg.cache_dir)


# -------- Sidebar: FYERS Login --------
st.sidebar.header("FYERS Login")

allow_edit = st.sidebar.toggle("Edit credentials", value=False)
disabled_inputs = not allow_edit

app_id = st.sidebar.text_input("FYERS App ID", key="fyers_app_id", disabled=disabled_inputs)
secret_key = st.sidebar.text_input("Secret Key", key="fyers_secret_key", type="password", disabled=disabled_inputs)
redirect_uri = st.sidebar.text_input("Redirect URI", key="fyers_redirect_uri", disabled=disabled_inputs)

state = st.sidebar.text_input("State (optional)", value="state")

if app_id and redirect_uri:
    urls = build_auth_code_url(app_id, redirect_uri, state=state)
    st.sidebar.markdown(f"[Open FYERS Login]({urls.auth_code_url})")
else:
    st.sidebar.info("FYERS App ID and Redirect URI are required to generate login URL.")

st.sidebar.divider()
st.sidebar.subheader("Fast login (paste redirect URL)")

redirect_full_url = st.sidebar.text_input(
    "Paste FYERS redirect URL here",
    value="",
    placeholder="https://share.streamlit.io/?auth_code=...&state=...",
)

if st.sidebar.button("Extract auth_code"):
    code = extract_auth_code_from_url(redirect_full_url)
    if code:
        st.session_state["fyers_auth_code"] = code
        st.sidebar.success("auth_code extracted ✅")
    else:
        st.sidebar.error("Could not find auth_code in that URL.")

auth_code = st.sidebar.text_input("auth_code", value=st.session_state.get("fyers_auth_code", ""))

if st.sidebar.button("Generate Access Token"):
    if not (app_id and secret_key and redirect_uri and auth_code):
        st.sidebar.error("Missing App ID / Secret Key / Redirect URI / auth_code.")
    else:
        try:
            token = exchange_auth_code_for_token(app_id, secret_key, redirect_uri, auth_code.strip())
            st.session_state["fyers_access_token"] = token
            save_persisted_token(cfg.cache_dir, token)
            st.sidebar.success("Access token saved ✅ (persists across refresh)")
        except Exception as e:
            st.sidebar.error(str(e))

# Also allow directly pasting token, and persist it
token = st.sidebar.text_input(
    "Access Token",
    value=st.session_state.get("fyers_access_token", ""),
    type="password",
)

if token and token != st.session_state.get("fyers_access_token", ""):
    st.session_state["fyers_access_token"] = token
    save_persisted_token(cfg.cache_dir, token)
    st.sidebar.success("Access token updated + persisted ✅")

if st.sidebar.button("Clear saved token"):
    st.session_state["fyers_access_token"] = ""
    clear_persisted_token(cfg.cache_dir)
    st.sidebar.info("Saved token cleared.")


# Rebuild config object (for downstream modules)
cfg = AppConfig(
    client_id=app_id.strip(),
    secret_key=secret_key.strip(),
    redirect_uri=redirect_uri.strip(),
    app_id=cfg.app_id,
    index_symbol=cfg.index_symbol,
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
