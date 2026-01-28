from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import quote

from fyers_apiv3 import fyersModel

@dataclass
class AuthURLs:
    auth_code_url: str

def build_auth_code_url(client_id: str, redirect_uri: str, state: str = "state") -> AuthURLs:
    base = "https://api-t1.fyers.in/api/v3/generate-authcode"
    url = (
        f"{base}?client_id={quote(client_id)}"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
        f"&response_type=code&state={quote(state)}"
    )
    return AuthURLs(auth_code_url=url)

def exchange_auth_code_for_token(client_id: str, secret_key: str, redirect_uri: str, auth_code: str) -> str:
    session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code",
    )
    session.set_token(auth_code)
    resp = session.generate_token()
    if not isinstance(resp, dict) or resp.get("s") != "ok":
        raise RuntimeError(f"Token generation failed: {resp}")
    token = resp.get("access_token") or resp.get("accessToken") or resp.get("token")
    if not token:
        raise RuntimeError(f"Token missing in response: {resp}")
    return str(token)
