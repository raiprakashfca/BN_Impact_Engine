# BANKNIFTY Expiry Impact (FYERS + Streamlit)

Two-tab Streamlit app:
1) **Expiry Live Impact**: on expiry day (last 30 mins), estimate **BANKNIFTY points per ₹1 move** for each constituent.
2) **Expiry Backtest**: one-time backtest across as many expiries as possible within FYERS History API limits.

## FYERS constraints (from public notes)
- Intraday (1–240 min) history requests are limited to **100 days per request**; daily to ~366 days per request.
- FYERS History API calls count toward rate limits; cache + batch.

## Quickstart (local)
1. Create venv, install deps:
```bash
pip install -r requirements.txt
```
2. Create `.streamlit/secrets.toml`:
```toml
FYERS_CLIENT_ID="xxxx-100"
FYERS_SECRET_KEY="xxxx"
FYERS_REDIRECT_URI="https://localhost"
FYERS_APP_ID="xxxx-100"
FYERS_INDEX_SYMBOL="NSE:NIFTYBANK-INDEX"
FYERS_CONSTITUENTS='["NSE:HDFCBANK-EQ","NSE:ICICIBANK-EQ","NSE:SBIN-EQ"]'
CACHE_DIR="data_cache"
```
3. Run:
```bash
streamlit run app.py
```

## Deploy (Streamlit Community Cloud)
- Push repo to GitHub
- Create a new Streamlit app from the repo
- Add the same keys in Streamlit Cloud → App → Settings → Secrets

## Expiry detection (dynamic)
Backtest tab detects weekly expiries **data-driven** per week:
Among Mon–Thu that have valid 15:00–15:30 data, the *latest* day is treated as expiry (handles Thu→Wed→Tue shifts and common holiday shifts).
