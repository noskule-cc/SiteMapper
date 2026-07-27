"""Thin client for the BRITA iQ portal REST API (iq.brita.net/api).

Not a CLI — imported by the readout scripts. Auth (Bearer token, Azure AD B2C) is
handled by brita_auth.session(). Endpoints were observed from the live SPA:

    GET /api/tenants/{tenantId}                          -> tenant (organization)
    GET /api/tenants/{tenantId}/resources/{resourceId}   -> one device (filter/meter)
    GET /api/me/tenants/{tenantId}/resources/{resourceId}/permissions

A device ("resource") is reachable directly by its tenant+resource id, so the daily
readout does not need a list endpoint. The exact JSON field names are not pinned yet
(the API 401s without a token, and the token is only obtainable after seeding) — the
readout scripts therefore keep a --raw mode so the first authenticated response can
confirm the mapping.
"""

from __future__ import annotations

import brita_auth

BASE = "https://iq.brita.net"


def get_resource(tenant_id: str, resource_id: str, sess=None, timeout: float = 60.0) -> dict:
    """GET one device by tenant + resource id. Returns the raw JSON dict."""
    s = sess or brita_auth.session(timeout)
    r = s.get(f"{BASE}/api/tenants/{tenant_id}/resources/{resource_id}", timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_tenant(tenant_id: str, sess=None, timeout: float = 60.0) -> dict:
    """GET tenant (organization) metadata. Returns the raw JSON dict."""
    s = sess or brita_auth.session(timeout)
    r = s.get(f"{BASE}/api/tenants/{tenant_id}", timeout=timeout)
    r.raise_for_status()
    return r.json()
