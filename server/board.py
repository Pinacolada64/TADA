"""board.py — Threaded message board storage and rendering.

Ports the prototype in the old `threaded_messages.py` scratch script
(see MECHANICS.md's "Threaded Message Boards" section for the design
notes it was written against) into this codebase's real architecture:
async ctx.prompt()/ctx.send() instead of input()/print(), a proper data
directory instead of a hardcoded scratch path, and text_editor.py's
run_editor() for composing thread/reply bodies instead of an
END-terminated raw-line loop.

First-pass scope (Ryan's call): one single global board, not yet
room/guild-scoped -- the `bulletin_board` room-flag idea from
MECHANICS.md's "Design Ideas" section is left for later, since it needs
room-flag plumbing this pass doesn't touch. Stored as one JSON file
(run/server/board.json), like news.py, rather than the prototype's
one-file-per-thread layout -- simpler to keep consistent with news.py's
already-established load/save conventions, and thread counts here won't
be large enough for that to matter.

    {
      "id": 1,
      "title": "...",
      "author": "<real player name, always -- see 'anonymous' below>",
      "anonymous": false,
      "posted_at": "<ISO datetime>",
      "body": [{"text": "line", ...}, ...],
      "replies": [
        {
          "author": "...",
          "anonymous": false,
          "posted_at": "<ISO datetime>",
          "body": [{"text": "line", ...}, ...]
        }
      ]
    }

'body' (on both the thread root and each reply) is
formatting.serialize_lines()'s output -- same structural storage as
news.py's 'body', re-rendered per-viewer via formatting.render_lines()
rather than frozen at the author's own screen width. See news.py's own
module docstring for the full rationale; it applies identically here.

'anonymous' keeps the *real* author name in storage always (never a
mangled '?'-prefixed name, unlike the old prototype) -- display_author()
resolves it to "Anonymous" for ordinary viewers and "Anonymous (name)"
for admins/Dungeon Masters, matching the prototype's own reveal rule.

Loaded/saved fresh on every call (like news.py/ban.py) rather than
cached, so one admin's post is immediately visible to everyone else.
"""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Optional

from formatting import deserialize_lines, render_lines, titled_box

log = logging.getLogger(__name__)

BOARD_FILE = Path('run') / 'server' / 'board.json'


def load_board(path: Optional[Path] = None) -> list[dict]:
    """Return the list of threads, oldest-posted first. [] if missing.

    path defaults to the module-level BOARD_FILE, looked up at call time
    (not bound at import) so tests can patch board.BOARD_FILE directly.
    """
    path = path or BOARD_FILE
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        log.exception('Failed to load board file %s', path)
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
    board_last_date threshold (commands/board.py's 'board ld'), not tied
    to login time the way news.py's is_new_since() is. since=None (the
    threshold has never been set) counts everything as new, matching
    news.py's own None-since convention.

    Deliberately doesn't distinguish *which* replies are new vs. the
    thread as a whole -- 'board rn' just filters which threads show up;
    reading one via 'board <id>' still shows the full thread, same
    simplicity news.py's own is_new_since() settles for."""
    if since is None:
        return True
    if _posted_after(thread.get('posted_at', ''), since):
        return True
    return any(_posted_after(r.get('posted_at', ''), since) for r in thread.get('replies', []))


def display_author(entry: dict, viewer_is_privileged: bool) -> str:
    """Resolve a thread or reply's real 'author'/'anonymous' fields into
    what a viewer should see: the real name normally, "Anonymous" for a
    non-privileged viewer of an anonymous post, or "Anonymous (name)" for
    an admin/Dungeon Master -- same reveal rule as the old prototype's
    own `f"Anonymous ({msg['from'][1:]})"` formatting."""
    name = entry.get('author', '???')
    if not entry.get('anonymous'):
        return name
    if viewer_is_privileged:
        return f'Anonymous ({name})'
    return 'Anonymous'


def format_thread_summary(thread: dict, viewer_is_privileged: bool) -> str:
    """One-line summary for the thread listing: id, title, author, reply
    count."""
    author = display_author(thread, viewer_is_privileged)
    count = len(thread.get('replies', []))
    replies = f'{count} repl{"y" if count == 1 else "ies"}'
    return f"{thread['id']:>3}. {thread.get('title', '(untitled)')}  -- {author}, {replies}"


def render_message_lines(entry: dict, ctx, width: int) -> list[str]:
    """Render just one post/reply's own body -- no title/header wrapper --
    re-rendering its Justification/Border for *this* viewer's screen
    width/terminal type (see the module docstring). Shared by
    format_thread() (the flat, whole-thread dump) and
    commands/board_reply.py's one-message-at-a-time interactive reader."""
    return render_lines(deserialize_lines(entry.get('body', [])), ctx, width)


def format_thread(thread: dict, ctx, viewer_is_privileged: bool) -> list[str]:
    """Render one thread in full -- title, root post, and every reply --
    re-rendering each body's Justification/Border for *this* viewer's
    screen width/terminal type (see the module docstring)."""
    width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)

    lines = [f"|yellow|--- {thread.get('title', '(untitled)')}|reset|"]
    lines.append(f"From: {display_author(thread, viewer_is_privileged)}"
                 f"  ({thread.get('posted_at', '')[:10]})")
    lines.append('')
    lines += render_message_lines(thread, ctx, width)

    for i, reply in enumerate(thread.get('replies', []), start=1):
        lines.append('')
        lines.append(f"|cyan|--- Reply #{i}|reset|")
        lines.append(f"From: {display_author(reply, viewer_is_privileged)}"
                     f"  ({reply.get('posted_at', '')[:10]})")
        lines.append('')
        lines += render_message_lines(reply, ctx, width)

    return lines


def build_quote_preamble(ctx, thread: dict, viewer_is_privileged: bool) -> list[str]:
    """A titled "Quoting <author>" box (formatting.titled_box()) holding
    the thread root's rendered body -- shown via ctx.send() right before
    a reply's editor session opens, so the replier can see what they're
    responding to without it being baked into their own composed text
    (see text_editor.py's own module docstring for why quoting is
    handled at this layer, not inside the editor itself)."""
    width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
    author = display_author(thread, viewer_is_privileged)
    quoted_lines = render_message_lines(thread, ctx, width)
    return titled_box(ctx, f'Quoting {author}', quoted_lines)
