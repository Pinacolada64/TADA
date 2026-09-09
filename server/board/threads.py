"""board/threads.py — Thread storage for the message board.

Same shape/conventions as the old top-level board.py's own load_board()/
save_board(): one flat JSON file (run/server/board_threads.json, was
board.json), loaded/saved fresh on every call rather than cached, so one
player's post is immediately visible to everyone else -- see board/
__init__.py's module docstring for why this got split into a package.

Threads now carry a 'board_id' key (which board they belong to, since
one file can hold every board's threads -- see the sig-editor project
plan) alongside the shape the old board.json already had:

    {
      "id": 1,
      "board_id": 1,
      "title": "...",
      "author": "<real player name, always -- see 'anonymous' below>",
      "anonymous": false,
      "posted_at": "<ISO datetime>",
      "body": [{"text": "line", ...}, ...],
      "replies": [ ... same shape as before, no board_id -- replies
                   belong to their thread implicitly ... ]
    }

next_id() is still computed over the *whole* file (every board's
threads), not scoped per-board, so ids stay globally unique across
every board -- callers that need one board's threads only should filter
the list *before* deciding what to display, but pass the full,
unfiltered list into next_id()/save_board() so other boards' threads
in the same file are never dropped.
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BOARD_FILE = Path('run') / 'server' / 'board_threads.json'


def load_board(path: Optional[Path] = None) -> list[dict]:
    """Return the list of threads (every board's, oldest-posted first).
    [] if missing.

    path defaults to the module-level BOARD_FILE, looked up at call time
    (not bound at import) so tests can patch threads.BOARD_FILE directly.
    """
    path = path or BOARD_FILE
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        log.exception('Failed to load board threads file %s', path)
    return []


def save_board(threads: list[dict], path: Optional[Path] = None) -> None:
    path = path or BOARD_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(threads, indent=2))


def next_id(threads: list[dict]) -> int:
    return max((t.get('id', 0) for t in threads), default=0) + 1


def _posted_after(posted_at: str, since: datetime.date) -> bool:
    try:
        return datetime.datetime.fromisoformat(posted_at).date() > since
    except (ValueError, TypeError):
        return False


def is_new_since(thread: dict, since: Optional[datetime.date]) -> bool:
    """Whether *thread* has any activity (its own root post, or any
    reply) posted after *since* -- the player's own command_settings.
    board_last_date threshold (commands/board/board.py's 'board ld'),
    not tied to login time the way news.py's is_new_since() is.
    since=None (the threshold has never been set) counts everything as
    new, matching news.py's own None-since convention.

    Deliberately doesn't distinguish *which* replies are new vs. the
    thread as a whole -- 'board rn' just filters which threads show up;
    reading one via 'board <id>' still shows the full thread, same
    simplicity news.py's own is_new_since() settles for."""
    return new_status(thread, since) is not None


def new_status(thread: dict, since: Optional[datetime.date]) -> Optional[str]:
    """'NEW' if *thread*'s own root post is new since *since*, 'NRB'
    ("new response to bulletin", ImageBBS's own term) if only a reply
    is, None if nothing about it is new. Root takes priority over a
    reply, matching ImageBBS's own listing-stat precedence (see
    board/listing.py's _stat_code(), which layers '*FZN*' frozen-status
    on top of this). since=None counts the root as new, same convention
    as is_new_since()."""
    if since is None:
        return 'NEW'
    if _posted_after(thread.get('posted_at', ''), since):
        return 'NEW'
    if any(_posted_after(r.get('posted_at', ''), since) for r in thread.get('replies', [])):
        return 'NRB'
    return None
