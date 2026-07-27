# iq.brita.net API scripts — PARKED

> **Status: parked / not operational.** These scripts implement a headless read path
> for the BRITA iQ API, but the portal's auth cannot be driven headlessly today, so the
> chosen path for the daily readout is **browser-driven on a schedule** (see the
> `itest-daily-readout` workflow and issue noskule-cc/SiteMapper#5). The code is kept
> because the API + auth research is correct and reusable the moment proper access exists.

## Why parked — the auth wall (all confirmed 2026-07-27)

iq.brita.net signs in via **Azure AD B2C** (MSAL.js v4) and calls its same-origin REST
API with a Bearer token. Headless auth is blocked on three independent counts:

1. **No password/ROPC grant** — the default policy `b2c_1_default` only supports
   authorization_code + refresh_token, so a script cannot log in with username/password.
2. **No loopback redirect** — `http://localhost[:port]` returns `AADB2C90006` (redirect
   URI not registered); only `https://iq.brita.net/` is valid. So a local MSAL/PKCE
   helper cannot run its own auth-code flow — B2C rejects it.
3. **Encrypted token cache** — the refresh token exists only inside the authenticated
   browser, stored AES-GCM-encrypted (`{id, nonce, data}`, key in the `msal.cache.encryption`
   cookie). There is no plaintext token to copy.

**What would unblock it:** BRITA/app-admin registers a loopback redirect URI for a public
client (then a standard MSAL interactive/device-code seed works), or issues service/API
credentials. Track under issue #5.

## What the scripts do (for when it is unblocked)

| Script | Purpose |
|---|---|
| `brita_auth.py` | Azure AD B2C refresh-token grant, tokens in the OS keyring. Needs a seeded refresh token. |
| `brita_api.py` | Thin REST client (`get_resource`, `get_tenant`) for `iq.brita.net/api`. |
| `get_itest_readout.py` | Reads Werkstatt + Pausenraum capacity + last-activity. `--json` / `--raw`. |

Confirmed API (Bearer auth):
- `GET /api/tenants/{tenantId}/resources/{resourceId}` → one device
- `GET /api/tenants/{tenantId}` → tenant
- Devices: tenant `dae9a265-0efa-4616-b75b-58848d8f7b35`; Werkstatt
  `d3e78486-13c6-436c-abe8-8996aa49113e`, Pausenraum `6c9a40e6-76f8-47fd-a589-9b04b7bc4443`.

Confirmed auth (public, non-secret) — token endpoint
`https://britaiotprd.b2clogin.com/britaiotprd.onmicrosoft.com/b2c_1_default/oauth2/v2.0/token`,
client `7e0154d7-61d7-4aa5-9c0a-46ee5a4b9a17`, scope
`https://britaiotprd.onmicrosoft.com/customer-api/use_api offline_access openid`.

The JSON field names for capacity / last-activity are still unpinned (the API 401s without
a token); `get_itest_readout.py` extracts them heuristically and keeps `--raw` to confirm
on a first authenticated run.
