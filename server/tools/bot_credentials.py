#!/usr/bin/env python3
"""bot_credentials.py — Shared, gitignored credential storage for tools/
bot scripts.

Every bot_*.py script here connects to a throwaway test account (botdummy,
botlasso, botdruid, ...) -- these aren't real user credentials, but they'd
still been hardcoded in plain text across ~50 scripts (several already
pushed to GitHub before this file existed). New scripts should call
load_password() instead of hardcoding a password string; setup_bot_accounts.py
writes this file when it creates/refreshes an account.

tools/.bot_credentials.json (gitignored, see server/.gitignore) format:

    {
      "default": "puppy123",
      "botdummy": "puppy123",
      "botlasso": "puppy123"
    }

"default" is used for any username with no specific entry -- in practice
every account setup_bot_accounts.py creates shares one password, so a
per-user override is rarely needed, but the option's there (e.g. after
manually changing one account's password via PREFS/admin tools without
touching the others).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

CREDENTIALS_FILE = Path(__file__).resolve().parent / '.bot_credentials.json'

# Falls back to this if the file doesn't exist yet (e.g. a fresh checkout
# that hasn't run setup_bot_accounts.py) -- matches every bot script's
# previous hardcoded default, so nothing breaks before the file is created.
DEFAULT_PASSWORD = 'puppy123'


def load_credentials(path: Optional[Path] = None) -> dict:
    """Return the full credentials dict. {} if the file is missing/unreadable."""
    path = path or CREDENTIALS_FILE
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}


def save_credentials(creds: dict, path: Optional[Path] = None) -> None:
    path = path or CREDENTIALS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(creds, indent=2))


def load_password(username: Optional[str] = None, path: Optional[Path] = None) -> str:
    """Return the password for *username*, falling back to the file's
    "default" entry, then DEFAULT_PASSWORD if the file/key is missing."""
    creds = load_credentials(path)
    if username and username in creds:
        return creds[username]
    return creds.get('default', DEFAULT_PASSWORD)


def set_password(username: str, password: str, path: Optional[Path] = None) -> None:
    """Record *username*'s password (used by setup_bot_accounts.py after
    creating/refreshing an account)."""
    creds = load_credentials(path)
    creds[username] = password
    save_credentials(creds, path)
