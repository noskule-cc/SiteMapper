"""Authentication against the GG+connect BFF.

Real login - no hand-copied bearer tokens. Mirrors the flow the Angular app uses
(POST /user/api/v1/auth) and the credential handling from the CacheUpdater project:

    accessToken still valid   -> use it
    refreshToken still valid  -> grantType: refresh_token
    otherwise                 -> grantType: password  (credentials from the OS
                                 keyring, else env vars, else an interactive prompt)

Credentials and tokens live in the OS keyring (Windows Credential Manager), never
in the repo and never in a file. The first run prompts once; after that it is
silent until the refresh token expires.
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
import time
from dataclasses import dataclass
from getpass import getpass

import keyring
import keyring.errors
import requests

ENV_BASE_URLS = {
    "prod": "https://bff.ggplus.ch",
    "dev": "https://bff-dev.ggplus.ch",
}

KEYRING_SERVICE = "SiteMapper"
TOKEN_SKEW_SECONDS = 300
DEFAULT_TIMEOUT = 60.0


def base_url(env: str = "prod") -> str:
    return ENV_BASE_URLS[env]


def auth_url(env: str) -> str:
    return f"{ENV_BASE_URLS[env]}/user/api/v1/auth"


@dataclass
class EnvAuth:
    user: str = ""
    password: str = ""
    accessToken: str = ""
    expiration: int = 0
    refreshToken: str = ""
    refreshTokenExpiration: int = 0


def _keyring_load(env: str) -> EnvAuth:
    try:
        raw = keyring.get_password(KEYRING_SERVICE, env)
    except keyring.errors.KeyringError:
        return EnvAuth()
    if not raw:
        return EnvAuth()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return EnvAuth()
    return EnvAuth(
        user=str(data.get("user", "") or ""),
        password=str(data.get("password", "") or ""),
        accessToken=str(data.get("accessToken", "") or ""),
        expiration=int(data.get("expiration", 0) or 0),
        refreshToken=str(data.get("refreshToken", "") or ""),
        refreshTokenExpiration=int(data.get("refreshTokenExpiration", 0) or 0),
    )


def _keyring_save(env: str, auth: EnvAuth) -> None:
    try:
        keyring.set_password(KEYRING_SERVICE, env, json.dumps(dataclasses.asdict(auth)))
    except keyring.errors.KeyringError as e:
        print(f"warning: could not save credentials to keyring: {e}", file=sys.stderr)


def keyring_clear(env: str = "prod") -> None:
    """Forget the stored login for `env` (use after a password change)."""
    try:
        keyring.delete_password(KEYRING_SERVICE, env)
    except keyring.errors.PasswordDeleteError:
        pass
    except keyring.errors.KeyringError as e:
        print(f"warning: could not clear keyring: {e}", file=sys.stderr)


def _login_password(env: str, user: str, password: str, timeout: float) -> dict:
    r = requests.post(
        auth_url(env),
        json={"username": user, "password": password, "grantType": "password"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def _login_refresh(env: str, refresh_token: str, timeout: float) -> dict:
    r = requests.post(
        auth_url(env),
        json={"refreshToken": refresh_token, "grantType": "refresh_token"},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()


def _store(env: str, data: dict, user: str, password: str) -> EnvAuth:
    auth = EnvAuth(
        user=user,
        password=password,
        accessToken=data.get("accessToken", ""),
        expiration=int(data.get("expiration", 0) or 0),
        refreshToken=data.get("refreshToken", ""),
        refreshTokenExpiration=int(data.get("refreshTokenExpiration", 0) or 0),
    )
    _keyring_save(env, auth)
    return auth


def get_bearer(env: str = "prod", timeout: float = DEFAULT_TIMEOUT) -> str:
    """Return a valid access token, logging in or refreshing as needed.

    Raises RuntimeError if no credentials are available and we cannot prompt
    (e.g. running headless in CI without GGPLUS_USER_* / GGPLUS_PASS_*).
    """
    auth = _keyring_load(env)
    now = int(time.time())

    if auth.accessToken and auth.expiration > now + TOKEN_SKEW_SECONDS:
        return auth.accessToken

    if auth.refreshToken and auth.refreshTokenExpiration > now + 60:
        try:
            data = _login_refresh(env, auth.refreshToken, timeout)
            auth.accessToken = data.get("accessToken", "")
            auth.expiration = int(data.get("expiration", 0) or 0)
            auth.refreshToken = data.get("refreshToken", auth.refreshToken)
            auth.refreshTokenExpiration = int(
                data.get("refreshTokenExpiration", auth.refreshTokenExpiration) or 0
            )
            _keyring_save(env, auth)
            return auth.accessToken
        except requests.RequestException:
            pass  # refresh rejected - fall through to a password login

    user = auth.user or os.getenv(f"GGPLUS_USER_{env.upper()}") or ""
    password = auth.password or os.getenv(f"GGPLUS_PASS_{env.upper()}") or ""

    if not (user and password):
        # A pipe/agent shell can claim to be a TTY and still have no stdin to read,
        # so catch the EOF rather than trusting isatty() alone — otherwise this dies
        # with a bare EOFError traceback that says nothing useful.
        try:
            if not sys.stdin.isatty():
                raise EOFError
            print(f"\nLogin to GG+connect ({env}) — stored in the OS keyring "
                  f"(service '{KEYRING_SERVICE}'), never in the repo.")
            user = input("  Username: ").strip()
            password = getpass("  Password: ")
        except (EOFError, KeyboardInterrupt):
            raise RuntimeError(
                f"No stored login for {env} and no interactive terminal to ask for one.\n"
                f"Run this once in a real terminal window (not through an agent/pipe):\n"
                f"    python ggplus_auth.py {env}\n"
                f"It stores the login in the Windows Credential Manager under service "
                f"'{KEYRING_SERVICE}'.\n"
                f"For unattended runs set GGPLUS_USER_{env.upper()} / GGPLUS_PASS_{env.upper()} instead."
            ) from None
        if not (user and password):
            raise RuntimeError("login aborted — no username or password entered")

    try:
        data = _login_password(env, user, password, timeout)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        if status == 401:
            raise RuntimeError("login failed: 401 unauthorized (check username/password)") from e
        raise RuntimeError(f"login failed: {e}") from e

    return _store(env, data, user, password).accessToken


def session(env: str = "prod", timeout: float = DEFAULT_TIMEOUT) -> requests.Session:
    """A requests.Session with the Authorization header already set."""
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {get_bearer(env, timeout)}"
    s.headers["Accept"] = "application/json"
    return s


if __name__ == "__main__":
    # `python ggplus_auth.py [env]` - log in / refresh and confirm it works.
    env = sys.argv[1] if len(sys.argv) > 1 else "prod"
    if "--clear" in sys.argv:
        keyring_clear(env)
        print(f"cleared stored login for {env}")
    else:
        token = get_bearer(env)
        print(f"ok - got an access token for {env} ({len(token)} chars)")
