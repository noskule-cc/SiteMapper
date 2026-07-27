"""Authentication against the BRITA iQ portal API (Azure AD B2C).

iq.brita.net is a SPA that signs in via Azure AD B2C (MSAL.js) and calls its
same-origin REST API (/api/...) with a Bearer access token. There is no cookie
session and the default B2C policy exposes no password/ROPC grant, so the only
viable headless auth is the **refresh-token grant**:

    access token still valid   -> use it
    otherwise                  -> grant_type=refresh_token against the B2C token
                                  endpoint, which returns a new access token AND a
                                  rotated refresh token (we persist the new one).

Because each refresh rotates the token, a job that runs at least once inside the
refresh-token inactivity window (a daily readout) keeps itself alive indefinitely.

SEEDING (one time): the refresh token must come from a real interactive browser
login — B2C will not issue one non-interactively. Seed it once with
`python brita_auth.py --seed` (see sites/iq-brita-net/scripts/README.md for the
exact steps). All secrets live in the OS keyring (service "SiteMapper", key
"brita") — never in the repo or a file. Public client details (client_id,
authority) are NOT secret; they are embedded in the SPA and kept here for reference.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, asdict
from getpass import getpass

import keyring
import keyring.errors
import requests

# --- Public (non-secret) B2C configuration, as used by the iq.brita.net SPA -----
TOKEN_URL = (
    "https://britaiotprd.b2clogin.com/britaiotprd.onmicrosoft.com/"
    "b2c_1_default/oauth2/v2.0/token"
)
CLIENT_ID = "7e0154d7-61d7-4aa5-9c0a-46ee5a4b9a17"
# The custom API scope the portal requests; offline_access is what yields a
# refresh token, openid a fresh id token.
SCOPE = (
    "https://britaiotprd.onmicrosoft.com/customer-api/use_api "
    "offline_access openid"
)

KEYRING_SERVICE = "SiteMapper"
KEYRING_KEY = "brita"
TOKEN_SKEW_SECONDS = 300
DEFAULT_TIMEOUT = 60.0


@dataclass
class BritaAuth:
    refreshToken: str = ""
    accessToken: str = ""
    expiration: int = 0          # epoch seconds when the access token expires


def _load() -> BritaAuth:
    try:
        raw = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY)
    except keyring.errors.KeyringError:
        return BritaAuth()
    if not raw:
        return BritaAuth()
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return BritaAuth()
    return BritaAuth(
        refreshToken=str(d.get("refreshToken", "") or ""),
        accessToken=str(d.get("accessToken", "") or ""),
        expiration=int(d.get("expiration", 0) or 0),
    )


def _save(auth: BritaAuth) -> None:
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_KEY, json.dumps(asdict(auth)))
    except keyring.errors.KeyringError as e:
        print(f"warning: could not save to keyring: {e}", file=sys.stderr)


def clear() -> None:
    """Forget the stored BRITA login (use after a manual re-seed)."""
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_KEY)
    except keyring.errors.PasswordDeleteError:
        pass
    except keyring.errors.KeyringError as e:
        print(f"warning: could not clear keyring: {e}", file=sys.stderr)


def seed(refresh_token: str) -> None:
    """Store an interactively-obtained refresh token (see README)."""
    refresh_token = refresh_token.strip()
    if not refresh_token:
        raise RuntimeError("empty refresh token — nothing seeded")
    _save(BritaAuth(refreshToken=refresh_token))


def _refresh(refresh_token: str, timeout: float) -> dict:
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token,
            "scope": SCOPE,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def get_bearer(timeout: float = DEFAULT_TIMEOUT) -> str:
    """Return a valid access token, refreshing (and rotating the RT) as needed.

    Raises RuntimeError if nothing is seeded or the refresh token has expired
    (re-seed via `python brita_auth.py --seed`).
    """
    auth = _load()
    now = int(time.time())

    if auth.accessToken and auth.expiration > now + TOKEN_SKEW_SECONDS:
        return auth.accessToken

    if not auth.refreshToken:
        raise RuntimeError(
            "No BRITA refresh token stored. Seed one from a browser login:\n"
            "    python brita_auth.py --seed\n"
            "(see README.md for how to obtain it)."
        )

    try:
        data = _refresh(auth.refreshToken, timeout)
    except requests.HTTPError as e:
        body = e.response.text[:300] if e.response is not None else ""
        raise RuntimeError(
            "BRITA token refresh failed — the refresh token is likely expired or "
            "revoked. Re-seed via `python brita_auth.py --seed`.\n"
            f"Server said: {body}"
        ) from e

    auth.accessToken = data.get("access_token", "")
    # B2C rotates the refresh token on every redemption — persist the new one.
    auth.refreshToken = data.get("refresh_token", auth.refreshToken)
    expires_in = int(data.get("expires_in", 3600) or 3600)
    auth.expiration = now + expires_in
    _save(auth)

    if not auth.accessToken:
        raise RuntimeError(f"refresh returned no access_token: {json.dumps(data)[:300]}")
    return auth.accessToken


def session(timeout: float = DEFAULT_TIMEOUT) -> requests.Session:
    """A requests.Session with the Bearer header already set for the BRITA API."""
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {get_bearer(timeout)}"
    s.headers["Accept"] = "application/json"
    return s


if __name__ == "__main__":
    if "--clear" in sys.argv:
        clear()
        print("cleared stored BRITA login")
    elif "--seed" in sys.argv:
        print("Paste the refresh token from the iq.brita.net login (input hidden):")
        rt = getpass("  refresh_token: ")
        seed(rt)
        print("seeded — verifying by fetching an access token…")
        tok = get_bearer()
        print(f"ok — got an access token ({len(tok)} chars)")
    else:
        tok = get_bearer()
        print(f"ok — got an access token ({len(tok)} chars)")
