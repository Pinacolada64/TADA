"""news.py — News/bulletin board storage and visibility rules.

Design taken from MECHANICS.md's "News & Mail" > "News / Bulletin Board"
section. Posts are stored as JSON (run/server/news.json); each record:

    {
      "id": 1,
      "title": "...",
      "body": [{"text": "line", ...}, ...],
      "author": "<player name>",
      "posted_at": "<ISO datetime>",
      "lifetime": "once" | "permanent" | "range",
      "start_date": "YYYY-MM-DD",   # only for "range"
      "end_date":   "YYYY-MM-DD",   # only for "range"
      "seen_by": ["<player name>", ...]   # only meaningful for "once"
    }

'body' is a list of formatting.serialize_lines()'s output -- text_editor.py's
run_editor() returns this directly on .S Save. It's stored structurally
(Justification/Border as metadata, not baked-in padding/box-drawing
characters) rather than as pre-rendered strings, so format_item() can
re-render it per-viewer via formatting.render_lines() at whatever screen
width/terminal type *that* player has, instead of a bordered/centered post
being frozen at the author's own screen width forever. Items posted before
this change have plain-string bodies (["line", "line", ...]) --
formatting.deserialize_lines() accepts those too, treating each string as
an unformatted Line, so old posts keep displaying exactly as before.

Loaded/saved fresh on every call (like commands/ban.py's load_bans()/
save_bans()) rather than cached on the server object, so admin edits made
by one connection are immediately visible to others.
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Optional

from formatting import deserialize_lines, render_lines

log = logging.getLogger(__name__)

NEWS_FILE = Path('run') / 'server' / 'news.json'

LIFETIMES = ('once', 'permanent', 'range')


def load_news(path: Optional[Path] = None) -> list[dict]:
    """Return the list of news records, oldest-posted first. [] if missing.

    path defaults to the module-level NEWS_FILE, looked up at call time
    (not bound at import) so tests can patch news.NEWS_FILE directly.
    """
    path = path or NEWS_FILE
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        log.exception('Failed to load news file %s', path)
    return []


def save_news(items: list[dict], path: Optional[Path] = None) -> None:
    path = path or NEWS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2))


def next_id(items: list[dict]) -> int:
    return max((it.get('id', 0) for it in items), default=0) + 1


def _parse_iso_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def is_visible(item: dict, player_name: str, today: Optional[datetime.date] = None) -> bool:
    """Whether *item* should be considered active/eligible for *player_name*.

    permanent — always.
    range     — only within [start_date, end_date] (missing end = open-ended).
    once      — only until this player has already seen it once.
    """
    today = today or datetime.date.today()
    lifetime = item.get('lifetime', 'permanent')

    if lifetime == 'once':
        return player_name not in item.get('seen_by', [])

    if lifetime == 'range':
        start = _parse_iso_date(item.get('start_date'))
        end   = _parse_iso_date(item.get('end_date'))
        if start and today < start:
            return False
        if end and today > end:
            return False
        return True

    return True  # permanent


def is_new_since(item: dict, since: Optional[datetime.datetime]) -> bool:
    """Whether *item* was posted after *since* (the player's previous login).

    With since=None (e.g. a brand-new player with no prior login), everything
    currently visible counts as new.
    """
    if since is None:
        return True
    try:
        posted = datetime.datetime.fromisoformat(item.get('posted_at', ''))
    except (ValueError, TypeError):
        return True
    return posted > since


def mark_seen(item: dict, player_name: str) -> None:
    """Record that *player_name* has now seen a 'once' item."""
    seen = item.setdefault('seen_by', [])
    if player_name not in seen:
        seen.append(player_name)


def format_item(item: dict, ctx) -> list[str]:
    """Render one news item as display lines (title + body), re-rendering
    the body's Justification/Border for *this* viewer's screen width and
    terminal type -- see the module docstring for why 'body' is stored
    structurally rather than as pre-rendered strings."""
    lines = [f"|yellow|--- {item.get('title', '(untitled)')}|reset|"]
    width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
    lines += render_lines(deserialize_lines(item.get('body', [])), ctx, width)
    return lines
