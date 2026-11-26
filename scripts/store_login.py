"""Store a persona's login in the OS keyring, asking with the right labels.

    python scripts/store_login.py <site> <persona> [--root PATH]

`keyring set` asks "Password for ..." for every entry, the username too. This reads
the persona's `credential_ref`, asks for the username in the clear and the password
hidden, and writes each `keyring:` entry. It never prints a value.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

import run

PROMPTS = {"username": "Username: ", "password": "Password (hidden): "}


def keyring_entries(persona: dict) -> list[tuple[str, str, str]]:
    """(field, service, name) for each keyring reference, username first."""
    refs = persona.get("credential_ref") or {}
    entries = []
    for field in PROMPTS:
        ref = refs.get(field) or ""
        if not ref.startswith("keyring:"):
            continue
        service, _, name = ref[len("keyring:"):].partition("/")
        if not service or not name:
            raise run.RunError(f"credential_ref.{field} '{ref}' must read "
                               "keyring:<service>/<name>", "input")
        entries.append((field, service, name))
    return entries


def ask(field: str) -> str:
    value = input(PROMPTS[field]) if field == "username" else getpass.getpass(PROMPTS[field])
    if not value:
        raise run.RunError(f"no {field} entered, nothing stored", "input")
    return value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("site")
    ap.add_argument("persona")
    ap.add_argument("--root", default=None, help="map repository (default: this repo)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve() if args.root else run.FRAMEWORK_ROOT
    try:
        persona = run.load_persona(root, args.site, args.persona)
        entries = keyring_entries(persona)
        if not entries:
            print(f"persona '{args.persona}' has no keyring: credential_ref, nothing to store")
            return 1
        import keyring
        for field, service, name in entries:
            keyring.set_password(service, name, ask(field))
            print(f"stored {field} as keyring:{service}/{name}")
    except run.RunError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
