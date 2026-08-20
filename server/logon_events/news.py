"""logon_events/news.py — login-time news display.

Split out of commands/connect.py the same way logon_events/birthday.py,
unconscious_wake.py, and ally_greeting.py are -- connect.py just calls
news_lines() and sends whatever it returns.

Reuses news.py's helpers directly rather than commands/news.py's
NewsCommand, since this runs before the player has a live prompt loop.
"""
from __future__ import annotations

import datetime

from network_context import GuestPlayer


def news_lines(ctx, player) -> list[str]:
    """Build the login-time news display for *player*, honoring their
    command_settings.news.show_all preference (full directory every login
    vs. just what's new since command_settings.news.last_read). Marks
    'once' items as seen and persists that back to news.json.

    command_settings.news.last_read (not player.last_connection) is the
    'since' cursor for permanent/range items -- last_connection is a
    general-purpose timestamp other login-sequence code also reads/writes,
    so a bug there could desync news display too. Once this function
    computes the new cursor value it force-saves the player immediately
    (like seen_by's own synchronous news.json write below), rather than
    leaving it to whatever eventually calls Player.save() -- otherwise an
    abnormal disconnect right after login leaves the cursor stuck at its
    old value and every future login re-shows the growing backlog of
    permanent/range items forever.

    *ctx* is only needed to pass through to news_store.format_item(),
    which re-renders each item's body at this viewer's own screen width/
    terminal type (see news.py's module docstring).
    """
    import news as news_store

    now = datetime.datetime.now()
    news_settings = player.command_settings.news
    since_str = getattr(news_settings, 'last_read', None)
    try:
        since = datetime.datetime.fromisoformat(since_str) if since_str else None
    except ValueError:
        since = None
    last_played = since.date() if since else None
    news_settings.last_read = now.isoformat()
    player.unsaved_changes = True
    if not isinstance(player, GuestPlayer):
        player.save(force=True)

    items = news_store.load_news()
    if not items:
        return []

    today    = datetime.date.today()
    show_all = getattr(news_settings, 'show_all', False)

    visible = [it for it in items
               if news_store.is_visible(it, player.name, today, last_played=last_played)]
    if show_all:
        to_show = visible
    else:
        to_show = [it for it in visible if news_store.is_new_since(it, since)]

    if not to_show:
        return []

    lines = ['', '|yellow|--- News ---|reset|']
    for it in to_show:
        lines += news_store.format_item(it, ctx)
        lines.append('')
        if it.get('lifetime') == 'once':
            news_store.mark_seen(it, player.name)

    news_store.save_news(items)
    return lines
