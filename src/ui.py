# filename: src/ui.py
from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import streamlit as st

from .fyers_auth import build_auth_code_url, exchange_auth_code_for_token
from .engines import run_backtest, run_live_snapshot, get_history_cached
from .fyers_history import IST, get_fyers_client
from .expiry_detect import detect_weekly_expiries_from_data
from .constituents import fetch_banknifty_constituents

# Auto-detect + validate index symbol
from .symbol_discovery import find_banknifty_index_candidates, validate_symbol_history


# -------------------------------------------------------------------
# Sidebar auth (kept for compatibility; your app.py may handle auth now)
# -------------------------------------------------------------------
def sidebar_auth(default_client_id: str, default_secret: str, default_redirect: str):
    st.sidebar.header("FYERS Login")

    client_id = st.sidebar.text_input("FYERS App ID", value=default_client_id)
    secret_key = st.sidebar.text_input("Secret Key", value=default_secret, type="password")
    redirect_uri = st.sidebar.text_input("Redirect URI", value=default_redirect)

    state = st.sidebar.text_input("State (optional)", value="state")
    urls = build_auth_code_url(client_id, redirect_uri, state=state)
    st.sidebar.markdown(f"[Open FYERS Login]({urls.auth_code_url})")

    auth_code = st.sidebar.text_input("Paste auth_code here", value="")
    if st.sidebar.button("Generate Access Token"):
        if not (client_id and secret_key and redirect_uri and auth_code):
            st.sidebar.error("Missing app_id/secret/redirect/auth_code.")
        else:
            try:
                token = exchange_auth_code_for_token(client_id, secret_key, redirect_uri, auth_code.strip())
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

    return client_id, secret_key, redirect_uri, st.session_state.get("fyers_access_token", "")


# -------------------------
# Constituents UI (auto-load)
# -------------------------
def _get_constituents_ui() -> list[str]:
    auto = fetch_banknifty_constituents()

    if auto.fyers_symbols:
        st.caption(f"Auto-loaded {len(auto.fyers_symbols)} constituents from: {auto.source}")
        with st.expander("See auto constituents"):
            st.code("\n".join(auto.fyers_symbols))
    else:
        st.warning(auto.note)

    allow_override = st.toggle("Override constituents manually (not recommended)", value=False)
    if allow_override:
        default = json.dumps(auto.fyers_symbols or [], indent=2)
        cons_text = st.text_area("Constituents override (JSON list of FYERS symbols)", value=default, height=220)
        try:
            constituents = json.loads(cons_text)
            if not isinstance(constituents, list) or not constituents:
                raise ValueError("Must be a non-empty JSON list.")
            return [str(x).strip() for x in constituents if str(x).strip()]
        except Exception as e:
            st.error(f"Bad override JSON: {e}")
            return []

    return auto.fyers_symbols


# ---------------------------------------------------------
# Index Symbol Control (Render ONCE per run; reuse everywhere)
# ---------------------------------------------------------
def _ensure_index_symbol_defaults(config) -> None:
    # Default symbol
    if "banknifty_index_symbol" not in st.session_state:
        st.session_state["banknifty_index_symbol"] = (
            st.session_state.get("validated_index_symbol") or config.index_symbol
        )

    # Candidate list cache
    if "index_candidates" not in st.session_state:
        st.session_state["index_candidates"] = []


def _render_index_symbol_controls_once(config) -> str:
    """
    This renders the index symbol UI exactly once per script run.
    Subsequent calls in the same run just return the stored value.

    This avoids DuplicateWidgetID with tabs.
    """
    _ensure_index_symbol_defaults(config)

    # If already rendered during this run, don't create widgets again.
    if st.session_state.get("_index_symbol_controls_rendered_this_run"):
        return st.session_state["banknifty_index_symbol"]

    st.session_state["_index_symbol_controls_rendered_this_run"] = True

    st.markdown("### Index symbol (auto-detect) 🔎")

    st.text_input(
        "BANKNIFTY index symbol",
        key="banknifty_index_symbol",
        help="Used for history fetch + impact estimation. Auto-detect can validate the correct FYERS index symbol for your account.",
    )

    if not st.session_state.get("fyers_access_token"):
        st.info("Login in the sidebar to auto-detect/validate index symbol.")
        return st.session_state["banknifty_index_symbol"]

    colA, colB = st.columns([1, 2])

    with colA:
        if st.button("Auto-detect candidates", key="btn_detect_index_candidates"):
            try:
                cands = find_banknifty_index_candidates()
                st.session_state["index_candidates"] = [(c.symbol, c.label) for c in cands]
                if not cands:
                    st.warning("No candidates found in FYERS symbol master.")
            except Exception as e:
                st.error(str(e))

    with colB:
        cands = st.session_state.get("index_candidates", [])
        if cands:
            symbols = [x[0] for x in cands]
            labels = [x[1] for x in cands]

            choice = st.selectbox(
                "Detected candidates (from FYERS Symbol Master)",
                options=list(range(len(symbols))),
                format_func=lambda i: labels[i],
                key="sel_index_candidate",
            )

            chosen = symbols[choice]

            v1, v2 = st.columns([1, 2])
            with v1:
                if st.button("Validate selected", key="btn_validate_index_symbol"):
                    ok, msg = validate_symbol_history(
                        client_id=config.client_id,
                        access_token=st.session_state["fyers_access_token"],
                        symbol=chosen,
                        cache_dir=config.cache_dir,
                        probe_day=datetime.now(IST).date(),
                    )
                    if ok:
                        st.session_state["validated_index_symbol"] = chosen
                        st.session_state["banknifty_index_symbol"] = chosen
                        st.success(msg)
                        st.info(f"Saved for this session: {chosen}")
                    else:
                        st.error(msg)

            with v2:
                st.caption("Validation hits a tiny history call. If it returns without 'valid symbol' error, we accept it.")

    return st.session_state["banknifty_index_symbol"]


def _get_index_symbol_value(config) -> str:
    """
    Read-only getter for other tabs.
    Ensures defaults exist, but DOES NOT render widgets (prevents duplicates).
    """
    _ensure_index_symbol_defaults(config)
    return st.session_state["banknifty_index_symbol"]


# -------------------------
# Tabs
# -------------------------
def tab_live(config):
    st.subheader("Expiry Live Impact (15:00–15:30 IST) 📌")

    # Reset the per-run render-flag here.
    # This works because Streamlit tabs execute sequentially in one run,
    # and tab_live will always run (even if tab not selected).
    st.session_state["_index_symbol_controls_rendered_this_run"] = False

    idx_sym = _render_index_symbol_controls_once(config)

    constituents = _get_constituents_ui()
    if not constituents:
        st.stop()

    alpha = st.number_input("Ridge alpha (stability)", min_value=0.0, value=1.0, step=0.5)

    today = datetime.now(IST).date()
    st.caption(f"Today (IST): {today.isoformat()}")

    if not st.session_state.get("fyers_access_token"):
        st.warning("Login in the sidebar first.")
        return

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("Run live snapshot", key="btn_run_live_snapshot"):
            try:
                fit, table = run_live_snapshot(
                    client_id=config.client_id,
                    access_token=st.session_state["fyers_access_token"],
                    index_symbol=idx_sym,
                    constituents=constituents,
                    cache_dir=config.cache_dir,
                    day=today,
                    alpha=float(alpha),
                )
                st.metric("R²", f"{fit.r2:.3f}" if fit.r2 == fit.r2 else "NA")
                st.metric("RMSE (BN pts)", f"{fit.rmse:.3f}" if fit.rmse == fit.rmse else "NA")
                st.metric("Observations", f"{fit.n_obs}")
                st.dataframe(table, use_container_width=True)
                st.download_button(
                    "Download impacts CSV",
                    table.to_csv(index=False),
                    file_name=f"live_impacts_{today}.csv",
                )
            except Exception as e:
                st.error(str(e))

    with col2:
        if st.button("Check expiry detection (this week)", key="btn_check_expiry_this_week"):
            try:
                fyers = get_fyers_client(config.client_id, st.session_state["fyers_access_token"])
                wk_start = today - timedelta(days=today.weekday())
                wk_end = wk_start + timedelta(days=6)
                bn = get_history_cached(config.cache_dir, fyers, idx_sym, "1", wk_start, wk_end)
                det = detect_weekly_expiries_from_data(bn, wk_start, wk_end)
                st.write({"method": det.method, "expiry_dates": [d.isoformat() for d in det.expiry_dates]})
                if today in det.expiry_dates:
                    st.success("Today is detected as expiry day ✅")
                else:
                    st.info("Today is not detected as expiry day.")
            except Exception as e:
                st.error(str(e))


def tab_backtest(config):
    st.subheader("Expiry Backtest (max history within FYERS limits) 🧪")

    if not st.session_state.get("fyers_access_token"):
        st.warning("Login in the sidebar first.")
        return

    # IMPORTANT: Do NOT render the index symbol widgets here.
    idx_sym = _get_index_symbol_value(config)

    constituents = _get_constituents_ui()
    if not constituents:
        st.stop()

    alpha = st.number_input("Ridge alpha (stability)", min_value=0.0, value=1.0, step=0.5, key="bt_alpha")

    today = datetime.now(IST).date()
    default_start = date(today.year - 2, 1, 1)
    start = st.date_input("Start date", value=default_start)
    end = st.date_input("End date", value=today)
    if start > end:
        st.error("Start > End")
        return

    st.caption("1-min intraday history is fetched in 100-day chunks and cached. FYERS history calls count toward rate limits.")

    if st.button("Run backtest", key="btn_run_backtest"):
        with st.spinner("Fetching data + running per-expiry fits..."):
            try:
                res = run_backtest(
                    client_id=config.client_id,
                    access_token=st.session_state["fyers_access_token"],
                    index_symbol=idx_sym,
                    constituents=constituents,
                    cache_dir=config.cache_dir,
                    start=start,
                    end=end,
                    alpha=float(alpha),
                )
                st.success(f"Detected {len(res.detection.expiry_dates)} weekly expiries. Method: {res.detection.method}")
                st.dataframe(res.expiry_metrics, use_container_width=True)
                st.download_button(
                    "Download expiry metrics CSV",
                    res.expiry_metrics.to_csv(index=False),
                    file_name="expiry_metrics.csv",
                )

                st.subheader("Impacts (long format)")
                st.dataframe(res.expiry_betas_long, use_container_width=True, height=420)
                st.download_button(
                    "Download impacts CSV",
                    res.expiry_betas_long.to_csv(index=False),
                    file_name="expiry_impacts_long.csv",
                )

                if not res.expiry_betas_long.empty:
                    summary = (
                        res.expiry_betas_long.groupby("symbol")["beta_bn_points_per_rs1"]
                        .agg(["median", "mean", "std", "count"])
                        .sort_values("median", ascending=False)
                        .reset_index()
                    )
                    st.subheader("Impact summary (across expiries)")
                    st.dataframe(summary, use_container_width=True)
                    st.download_button(
                        "Download summary CSV",
                        summary.to_csv(index=False),
                        file_name="impact_summary.csv",
                    )
            except Exception as e:
                st.error(str(e))
