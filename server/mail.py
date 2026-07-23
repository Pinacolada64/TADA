"""mail.py — Private player mail storage.

Design taken from MECHANICS.md's "News & Mail" > "Mail / Paging" section.
One mailbox file per player (run/server/mail/<name-lowercased>.json), a
flat JSON list of records, oldest first:

    {
      "from":      "<player name>",
      "timestamp": "<ISO datetime>",
      "body":      "<plain string>",
      "read":      false
    }

commands/page.py's offline-page fallback already writes this schema (it
was built first, before there was a way to read it back) -- this module
is the read side: commands/mail.py's MAIL command, and commands/
connect.py's login-time "you have N unread message(s)" notice.

Loaded/saved fresh on every call (like news.py's load_news()/save_news())
rather than cached on the server object, so a page delivered by one
connection is immediately visible if the recipient checks mail on another.
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

MAIL_DIR = Path('run') / 'server' / 'mail'


def _mail_path(player_name: str) -> Path:
    return MAIL_DIR / f'{player_name.lower()}.json'


def load_mailbox(player_name: str) -> list[dict]:
    """Return *player_name*'s mailbox, oldest first. [] if missing/empty."""
    path = _mail_path(player_name)
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        log.exception('Failed to load mailbox for %s', player_name)
    return []


def save_mailbox(player_name: str, inbox: list[dict]) -> None:
    """Persist *player_name*'s mailbox (overwrites the whole file)."""
    MAIL_DIR.mkdir(parents=True, exist_ok=True)
    _mail_path(player_name).write_text(json.dumps(inbox, indent=2))


def add_message(player_name: str, from_name: str, body: str) -> None:
    """Append one message to *player_name*'s mailbox. Shared by
    commands/page.py's offline fallback and MAIL's 'reply', so both write
    the exact same record shape."""
    inbox = load_mailbox(player_name)
    inbox.append({
        'from':      from_name,
        'timestamp': datetime.datetime.now().isoformat(),
        'body':      body,
        'read':      False,
    })
    save_mailbox(player_name, inbox)


def unread_count(player_name: str) -> int:
    """Unread, non-archived messages -- an archived message doesn't keep
    nagging the login notice or the mailbox listing (see mark_archived())."""
    return sum(1 for m in load_mailbox(player_name)
               if not m.get('read', False) and not m.get('archived', False))


def mark_read(player_name: str, index: int) -> Optional[dict]:
    """Mark message *index* (0-based) read and persist it. Returns the
    message dict, or None if *index* is out of range."""
    inbox = load_mailbox(player_name)
    if not (0 <= index < len(inbox)):
        return None
    inbox[index]['read'] = True
    save_mailbox(player_name, inbox)
    return inbox[index]


def mark_archived(player_name: str, index: int) -> Optional[dict]:
    """Mark message *index* (0-based) archived and persist it. Archived
    messages stay in the same mailbox file (not moved/deleted) but are
    excluded from the normal listing/unread count/`mail #read` walk --
    see commands/mail.py's `[A]rchive` option. Returns the message dict,
    or None if *index* is out of range."""
    inbox = load_mailbox(player_name)
    if not (0 <= index < len(inbox)):
        return None
    inbox[index]['archived'] = True
    save_mailbox(player_name, inbox)
    return inbox[index]


def delete_message(player_name: str, index: int) -> bool:
    """Remove message *index* (0-based). Returns False if out of range."""
    inbox = load_mailbox(player_name)
    if not (0 <= index < len(inbox)):
        return False
    inbox.pop(index)
    save_mailbox(player_name, inbox)
    return True
