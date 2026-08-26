"""board/listing.py — Thread/reply rendering: MessageHeader and the
listing/full-thread/quote-preamble formatters -- carried over unchanged
from the old top-level board.py (see board/__init__.py's module
docstring for why this got split into a package). Doesn't touch
board_id at all -- these all operate on already-loaded thread/reply
dicts handed to them by the caller (commands/board/*.py), which is
responsible for deciding *which* board's threads to pass in.

'anonymous' keeps the *real* author name in storage always (never a
mangled '?'-prefixed name) -- display_author() resolves it to
"Anonymous" for ordinary viewers and "Anonymous (name)" for admins/
Dungeon Masters.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

from formatting import deserialize_lines, render_lines, titled_box
from .threads import new_status


def display_author(entry: dict, viewer_is_privileged: bool) -> str:
    """Resolve a thread or reply's real 'author'/'anonymous' fields into
    what a viewer should see: the real name normally, "Anonymous" for a
    non-privileged viewer of an anonymous post, or "Anonymous (name)" for
    an admin/Dungeon Master."""
    name = entry.get('author', '???')
    if not entry.get('anonymous'):
        return name
    if viewer_is_privileged:
        return f'Anonymous ({name})'
    return 'Anonymous'


# Colors by position, not by field -- 1st header line cyan, 2nd
# light_green, every line after that yellow (Ryan's call, going for a
# pastel-ish scheme rather than a distinct color per field).
_HEADER_COLORS_BY_POSITION = ('cyan', 'light_green')
_HEADER_FALLBACK_COLOR = 'yellow'


@dataclass
class MessageHeader:
    """A post/reply's Number/From/Date/Title(/Replies) block -- one
    colorized line each (see _HEADER_COLORS_BY_POSITION/
    _HEADER_FALLBACK_COLOR above), labels right-justified to a common
    ': ' column. Shared by format_thread() (the flat, whole-thread dump)
    and commands/board/reply.py's one-message-at-a-time interactive
    reader, which used to each build this same block by hand."""
    title: str
    author: str
    date: str  # already truncated to YYYY-MM-DD
    reply_count: int = 0    # thread root only -- a reply has no replies of its own
    thread_number: int = 0  # feeds the "Number: x of y" line -- meaning is
    total_threads: int = 0  # caller-defined (format_thread() uses this
                             # thread's own id vs. every thread on the
                             # board; commands/board/reply.py's interactive
                             # reader uses this message's position within
                             # *this* thread instead). Omitted if either
                             # is falsy -- both thread root only.

    def display(self) -> list[str]:
        fields = []
        if self.thread_number and self.total_threads:
            fields.append(('Number', f'{self.thread_number} of {self.total_threads}'))
        fields += [
            ('From', self.author),
            ('Date', self.date),
            ('Title', self.title),
        ]
        if self.reply_count:
            fields.append(('Replies', str(self.reply_count)))
        width = max(len(label) for label, _ in fields)
        lines = []
        for i, (label, value) in enumerate(fields):
            color = (_HEADER_COLORS_BY_POSITION[i] if i < len(_HEADER_COLORS_BY_POSITION)
                     else _HEADER_FALLBACK_COLOR)
            lines.append(f'|{color}|{label.rjust(width)}: {value}|reset|')
        return lines

    @classmethod
    def for_entry(cls, entry: dict, title: str, viewer_is_privileged: bool,
                  reply_count: int = 0, thread_number: int = 0,
                  total_threads: int = 0) -> 'MessageHeader':
        """Build from a thread/reply dict -- resolves author display
        (anonymous/privileged-reveal rule) and truncates posted_at."""
        return cls(
            title=title,
            author=display_author(entry, viewer_is_privileged),
            date=entry.get('posted_at', '')[:10],
            reply_count=reply_count,
            thread_number=thread_number,
            total_threads=total_threads,
        )


def format_thread_summary(thread: dict, viewer_is_privileged: bool) -> str:
    """One-line summary for the thread listing: id, title, author, reply
    count."""
    author = display_author(thread, viewer_is_privileged)
    count = len(thread.get('replies', []))
    replies = f'{count} repl{"y" if count == 1 else "ies"}'
    return f"{thread['id']:>3}. {thread.get('title', '(untitled)')}  -- {author}, {replies}"


_STAT_WIDTH = len('*NEW*')  # every code (*NEW*/*NRB*/*FZN*) is this width


def _stat_code(thread: dict, since: Optional[datetime.date]) -> str:
    """ImageBBS's own listing-stat precedence: a frozen bulletin shows
    '*FZN*' regardless of new/old status (frozen takes priority -- a
    SIGop froze it for a reason, that's the thing worth flagging first);
    otherwise '*NEW*' (the root post itself is new) beats '*NRB*' ("new
    response to bulletin", i.e. only a reply is new); '' if neither."""
    if thread.get('frozen'):
        return '*FZN*'
    status = new_status(thread, since)
    return f'*{status}*' if status else ''


def format_thread_listing(threads: list[dict], width: int, is_petscii: bool = False,
                           since: Optional[datetime.date] = None) -> list[str]:
    """Render the thread listing as four columns -- '##', 'Stat'
    ('*NEW*'/'*NRB*'/'*FZN*', see _stat_code()), 'Resp' (reply count),
    and 'Title' (elided if it doesn't fit the column -- a real ellipsis
    character on ANSI/plain, or '...' on PETSCII, since real Commodore
    font ROMs don't have one) -- sized to *width*. Mirrors
    commands/whereat.py's plain ljust/rjust column style rather than
    table.py's bordered Table, since a long title should be elided to
    one line here, not word-wrapped across several."""
    id_w = max(len('##'), *(len(str(t.get('id', 0))) for t in threads))
    reply_counts = [len(t.get('replies', [])) for t in threads]
    replies_w = max(len('Resp'), *(len(str(c)) for c in reply_counts))
    title_w = max(width - id_w - _STAT_WIDTH - replies_w - 6, 10)
    ellipsis = '...' if is_petscii else '…'
    ellipsis_w = len(ellipsis)

    def _elide(text: str) -> str:
        if len(text) <= title_w:
            return text
        if title_w <= ellipsis_w:
            return text[:title_w]
        return text[:title_w - ellipsis_w] + ellipsis

    lines = [f"{'##'.rjust(id_w)}  {'Stat'.ljust(_STAT_WIDTH)}  "
             f"{'Resp'.rjust(replies_w)}  Title"]
    for t, count in zip(threads, reply_counts):
        title = _elide(t.get('title', '(untitled)'))
        stat = _stat_code(t, since)
        lines.append(f"{str(t.get('id', 0)).rjust(id_w)}  {stat.ljust(_STAT_WIDTH)}  "
                      f"{str(count).rjust(replies_w)}  {title}")
    return lines


def render_message_lines(entry: dict, ctx, width: int) -> list[str]:
    """Render just one post/reply's own body -- no title/header wrapper --
    re-rendering its Justification/Border for *this* viewer's screen
    width/terminal type. Shared by format_thread() (the flat, whole-thread
    dump) and commands/board/reply.py's one-message-at-a-time interactive
    reader."""
    return render_lines(deserialize_lines(entry.get('body', [])), ctx, width)


def format_thread(thread: dict, ctx, viewer_is_privileged: bool, total_threads: int = 0) -> list[str]:
    """Render one thread in full -- title, root post, and every reply --
    re-rendering each body's Justification/Border for *this* viewer's
    screen width/terminal type. *total_threads* (this board's own count,
    from the caller's own already-loaded/filtered list) feeds the
    header's "Number: <id> of <total_threads>" line -- omitted if not
    given."""
    width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)

    reply_count = len(thread.get('replies', []))
    lines = MessageHeader.for_entry(
        thread, thread.get('title', '(untitled)'), viewer_is_privileged,
        reply_count=reply_count, thread_number=thread.get('id', 0),
        total_threads=total_threads).display()
    lines.append('')
    lines += render_message_lines(thread, ctx, width)

    for i, reply in enumerate(thread.get('replies', []), start=1):
        lines.append('')
        lines += MessageHeader.for_entry(
            reply, reply.get('title') or f'Reply #{i}', viewer_is_privileged).display()
        lines.append('')
        lines += render_message_lines(reply, ctx, width)

    return lines


def build_quote_preamble(ctx, thread: dict, viewer_is_privileged: bool) -> list[str]:
    """A titled "Quoting <author>" box (formatting.titled_box()) holding
    the thread root's rendered body -- shown via ctx.send() right before
    a reply's editor session opens, so the replier can see what they're
    responding to without it being baked into their own composed text."""
    width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
    author = display_author(thread, viewer_is_privileged)
    quoted_lines = render_message_lines(thread, ctx, width)
    return titled_box(ctx, f'Quoting {author}', quoted_lines)
