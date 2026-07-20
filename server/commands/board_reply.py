"""commands/board_reply.py — Interactive, one-message-at-a-time reader
for the threaded message board, gated behind PlayerFlags.PROMPT_MODE.

commands/board.py's `board <id>` normally dumps a whole thread flat
(board.format_thread()) and returns straight to the listing. When a
player has PROMPT_MODE on, `_read_one()` delegates here instead: each
post (the thread root, then each reply in order) is shown one at a
time, followed by a menu:

    [R]eply             — reply to *this* message (see below)
    [M]ail poster        — page/mail this message's author directly
                            (delegates to commands/page.py's own
                            live-or-offline delivery, not reimplemented)
    <#>                  — jump straight to reply #<#>
    {return_key}          — advance to the next message

[R]eply asks whether (and how much of) the message just read should be
quoted -- a line range (reusing text_editor.py's own ed-style range
parser), 'all', or no quote at all -- shows a preview box
(formatting.titled_box(), same as board.py's build_quote_preamble())
and asks for Y/N confirmation before opening the reply editor, rather
than assuming the whole message (board.py's simpler `board reply <id>`
command still does that -- this is the richer, opt-in experience).

Split into its own module (Ryan's call) rather than folded into
commands/board.py, since the interactive reader/quote-preview/mail
flow is a distinct, sizable piece of UI logic from board.py's listing/
post/admin surface.
"""
from __future__ import annotations

import datetime
import logging

import board as board_store
from flags import PlayerFlags
from formatting import titled_box

log = logging.getLogger(__name__)


def _is_privileged(player) -> bool:
    return bool(player.query_flag(PlayerFlags.ADMIN) or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def _screen_width(ctx) -> int:
    return getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)


async def read_thread_interactive(ctx, thread: dict) -> None:
    """Walk *thread* one message at a time (root, then each reply in
    posted order). Only called when PlayerFlags.PROMPT_MODE is on --
    commands/board.py's _read_one() gates on that; this assumes it."""
    privileged = _is_privileged(ctx.player)
    width = _screen_width(ctx)

    messages = [thread] + list(thread.get('replies', []))
    idx = 0
    while idx < len(messages):
        entry = messages[idx]
        is_root = (idx == 0)

        header = (
            [f"|yellow|--- {thread.get('title', '(untitled)')}|reset|"] if is_root
            else [f"|cyan|--- Reply #{idx}|reset|"]
        )
        header.append(f"From: {board_store.display_author(entry, privileged)}"
                      f"  ({entry.get('posted_at', '')[:10]})")
        header.append('')
        await ctx.send([''] + header + board_store.render_message_lines(entry, ctx, width) + [''])

        reply_count = len(thread.get('replies', []))
        raw = await ctx.prompt(
            f'[R]eply, [M]ail poster, <#> jump to reply, or {ctx.player.return_key} for next',
        )
        if raw is None:
            return  # disconnected mid-read
        choice = raw.strip()

        if not choice:
            idx += 1
            continue

        low = choice.lower()
        if low == 'r':
            await _reply_with_quote(ctx, thread, entry, privileged)
            idx += 1
        elif low == 'm':
            await _mail_poster(ctx, entry, privileged)
            # deliberately doesn't advance -- they may still want to
            # reply to or keep reading the same message.
        elif choice.isdigit():
            target = int(choice)
            if 1 <= target <= reply_count:
                idx = target
            else:
                await ctx.send(f'No reply #{target}.')
        else:
            await ctx.send(f"Unrecognized choice '{choice}'.")


async def _reply_with_quote(ctx, thread: dict, quoted_entry: dict, privileged: bool) -> None:
    """[R]eply: pick how much (if any) of *quoted_entry* to quote, preview
    it, confirm, then open the line editor for the reply body."""
    from text_editor import Buffer, DefaultLineRange, Line, LineFlag, process_line_range_string, run_editor

    width = _screen_width(ctx)
    quoted_lines = board_store.render_message_lines(quoted_entry, ctx, width)
    author_display = board_store.display_author(quoted_entry, privileged)
    buffer = Buffer(lines=[Line(text=t) for t in quoted_lines])

    quote_lines: list[str] | None = None
    while True:
        raw = await ctx.prompt("Quote which lines? (e.g. '1-3', 'all', or N for no quote)")
        if raw is None:
            return  # disconnected
        ans = raw.strip()
        if not ans or ans.lower() == 'n':
            break

        range_str = '' if ans.lower() == 'all' else ans
        line_range = process_line_range_string(range_str, buffer, DefaultLineRange.ALL_LINES)
        selected = [buffer.lines[i].text for i in buffer.line_slice(line_range)]
        if not selected:
            await ctx.send('Nothing in that range.')
            continue

        await ctx.send(titled_box(ctx, f'Quoting {author_display}', selected))
        confirm = await ctx.prompt('Use this quote? (y/N)')
        if confirm and confirm.strip().lower().startswith('y'):
            quote_lines = selected
            break
        # anything else -- loop back and ask for a range again, rather
        # than silently posting with no quote at all.

    anonymous_raw = await ctx.prompt('Post anonymously? (y/N)')
    if anonymous_raw is None:
        await ctx.send('Cancelled.')
        return
    anonymous = anonymous_raw.strip().lower().startswith('y')

    initial_lines = None
    if quote_lines is not None:
        # Seeded as real buffer content (Ryan's call), tagged
        # LineFlag.QUOTE -- not plain/editable -- so the quote can't be
        # altered while composing the reply. Without that, a player
        # could edit the quoted text into something the original poster
        # never actually said. text_editor.py treats QUOTE the same as
        # IMMUTABLE in its own .E/.D/.K/.J/.E m/c skip-checks (see that
        # module's docstring); typing a new line still just appends
        # after them normally.
        initial_lines = [
            Line(text=f'{author_display} wrote:', line_flag=LineFlag.QUOTE),
        ] + [Line(text=t, line_flag=LineFlag.QUOTE) for t in quote_lines]
    await ctx.send('Enter your reply.')
    body = await run_editor(ctx, initial_lines=initial_lines)
    if body is None:
        await ctx.send('Cancelled.')
        return

    reply = {
        'author':    ctx.player.name,
        'anonymous': anonymous,
        'posted_at': datetime.datetime.now().isoformat(),
        'body':      body,
    }
    # Reload fresh rather than reuse the 'thread'/'threads' this reader
    # started with -- quote-picking and composing the reply body can take
    # a while, during which another player could have posted or an admin
    # could have deleted this very thread.
    threads = board_store.load_board()
    fresh_thread = next((t for t in threads if t.get('id') == thread.get('id')), None)
    if fresh_thread is None:
        await ctx.send('That thread no longer exists.')
        return
    fresh_thread.setdefault('replies', []).append(reply)
    board_store.save_board(threads)
    await ctx.send(f"Reply posted to thread #{fresh_thread['id']}.")
    log.info('BOARD REPLY: %s replied to thread #%s', ctx.player.name, fresh_thread['id'])


async def _mail_poster(ctx, entry: dict, privileged: bool) -> None:
    """[M]ail poster: delegates straight to commands/page.py's PageCommand
    (live delivery if the author's online, its own offline-mail fallback
    otherwise, ignore-list/haven checks, etc.) rather than reimplementing
    any of that here."""
    if entry.get('anonymous') and not privileged:
        await ctx.send('This post is anonymous -- you cannot mail its author.')
        return

    author = entry.get('author', '')
    if not author:
        await ctx.send('Unknown author.')
        return

    message = await ctx.prompt(f'Message for {author}')
    if not message or not message.strip():
        await ctx.send('Cancelled.')
        return

    from commands.page import PageCommand
    await PageCommand().execute(ctx, f'{author}={message.strip()}')
