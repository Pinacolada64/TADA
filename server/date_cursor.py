"""date_cursor.py — shared "read-new-since" date threshold prompt/parser.

Both BOARD's 'ld' (command_settings.board.last_date) and editplayer's
News Last Read editor (command_settings.news.last_read) are the same
shape of thing: a per-player "everything posted after this date counts
as new" cursor that a player (or an admin editing someone else's
settings via editplayer.py) can move forward/back. This module is the
one place that prompt/parse logic lives, so both stay in sync instead
of drifting into two hand-rolled versions.

Accepted input, tried in this order:
  1. 'clear' / 'none' / 'unset' -> cursor unset (None) -- "everything
     currently visible counts as new", matching is_new_since()'s own
     None handling in both news.py and board.py.
  2. A signed day offset relative to the *current* value (or today, if
     there is no current value yet): '+7', '-3'.
  3. A relative shortcut (parse_date.py's parse_relative_date): 'week',
     '2 months', '3 days ago', ... -- board.py's 'ld' supported this
     before date_cursor.py existed; kept for backward compatibility.
  4. An absolute date, first tried against the viewer's own PREFS
     date-format preference (formatting.format_player_datetime's
     client_settings.date_format), then parse_date.py's generic
     dateutil-backed fallback formats.
Blank cancels, leaving the current value untouched.
"""
from __future__ import annotations

import datetime
import re
from typing import Optional

from parse_date import DATE_HELP, RELATIVE_DATE_HELP, parse_date, parse_relative_date

_OFFSET_RE = re.compile(r'^([+-])\s*(\d+)$')

OFFSET_HELP: str = """\
Or a signed day offset from the current value (today, if unset):
  +7            7 days later
  -3            3 days earlier\
"""

# Sentinels, both distinct from None (which means "parsed to an explicit
# clear/unset"): UNCHANGED is a blank prompt -- deliberate no-op. INVALID
# is text that didn't parse at all -- also a no-op, but callers that want
# to report it as an error (e.g. board.py's CommandResult.fail) instead
# of a plain "unchanged" need to tell the two apart.
UNCHANGED = object()
INVALID = object()


def parse_date_offset(text: str) -> Optional[int]:
    """Parse '+7' / '-3' as a signed day count. None if *text* isn't in
    that exact shape -- caller falls back to the other parse strategies.
    """
    match = _OFFSET_RE.match((text or '').strip())
    if not match:
        return None
    sign, digits = match.groups()
    n = int(digits)
    return -n if sign == '-' else n


def resolve_date_cursor(
    text: str, player, current: Optional[datetime.date],
) -> tuple[bool, Optional[datetime.date]]:
    """Parse *text* into a new cursor value.

    Returns (ok, value). ok=False means *text* couldn't be parsed at all
    (caller should report an error and leave the cursor untouched).
    ok=True, value=None means an explicit clear/unset. ok=True with a
    date means the new cursor value.
    """
    text = (text or '').strip()
    if not text:
        return False, None
    if text.lower() in ('clear', 'none', 'unset'):
        return True, None

    offset = parse_date_offset(text)
    if offset is not None:
        base = current or datetime.date.today()
        return True, base + datetime.timedelta(days=offset)

    relative = parse_relative_date(text)
    if relative is not None:
        return True, relative

    date_format = getattr(getattr(player, 'client_settings', None), 'date_format', '') \
        or '%B %d, %Y'
    try:
        return True, datetime.datetime.strptime(text, date_format).date()
    except (ValueError, TypeError):
        pass

    absolute = parse_date(text)
    if absolute is not None:
        return True, absolute

    return False, None


async def prompt_date_cursor(
    ctx, player, current: Optional[datetime.date], *, label: str, note: str = '',
):
    """Prompt for and parse a new value for a date-cursor field named
    *label* (used in prompt/status text, e.g. 'news threshold'). *note*,
    if given, is appended to the "set to ..." / "cleared" confirmation
    (e.g. what the new threshold actually affects).

    Returns the new date, None if explicitly cleared, the module-level
    UNCHANGED sentinel if the player left the prompt blank, or the
    module-level INVALID sentinel if they entered something unparseable
    (both already reported to them) -- callers should leave the
    underlying field untouched for either sentinel, but may want to
    treat them differently (e.g. INVALID as a command failure).
    """
    from formatting import format_player_datetime

    def _display(d: datetime.date) -> str:
        return format_player_datetime(datetime.datetime.combine(d, datetime.time.min), player)

    cur_str = _display(current) if current else '(not set -- everything currently counts as new)'
    raw = await ctx.prompt(
        f'New {label}',
        preamble_lines=['', f'Current: {cur_str}', '', OFFSET_HELP, '',
                        RELATIVE_DATE_HELP, '', DATE_HELP, '',
                        "'clear' to unset, blank to cancel:"],
    )
    if raw is None or not raw.strip():
        await ctx.send('Unchanged.')
        return UNCHANGED

    ok, value = resolve_date_cursor(raw, player, current)
    if not ok:
        await ctx.send("Didn't understand that date.")
        return INVALID

    suffix = f' {note}' if note else ''
    if value is None:
        await ctx.send(f'{label.capitalize()} cleared.{suffix}')
        return None

    await ctx.send(f'{label.capitalize()} set to {_display(value)}.{suffix}')
    return value
