"""commands/board/reply.py — Interactive, one-message-at-a-time reader
for the threaded message board, gated behind PlayerFlags.PROMPT_MODE.

commands/board/board.py's `board <id>` normally dumps a whole thread flat
(board.format_thread()) and returns straight to the listing. When a
player has PROMPT_MODE on, `_read_one()` delegates here instead: each
post (the thread root, then each reply in order) is shown one at a
time, followed by an "End of bulletin option>" prompt with this menu:

    [R]eply             — reply to *this* message (see below)
    [M]ail poster        — page/mail this message's author directly
                            (delegates to commands/page.py's own
                            live-or-offline delivery, not reimplemented)
    [L]ist               — numbered index of every message in the
                            thread (same numbering <#> jump accepts)
    <#>                  — jump straight to reply #<#>
    {return_key}          — advance to the next message
    'pm'                 — toggle Prompt Mode (see commands/prompt_mode.py)
    [Q]uit                — back to the board listing, without reading the rest
    '?'                  — redisplay this option list

The full option list is shown as the prompt's own preamble every time
for non-expert players (PlayerFlags.EXPERT_MODE off); experts just get
the bare "End of bulletin option>" prompt and can type '?' to recall
the list on demand -- same show/hide-by-expertise convention as
commands/mail.py's login-time hint text.

[R]eply asks whether (and how much of) the message just read should be
quoted -- a line range (reusing text_editor.py's own ed-style range
parser), 'all', or no quote at all -- shows a preview box
(formatting.titled_box(), same as board.py's build_quote_preamble())
and asks for Y/N confirmation before opening the reply editor, rather
than assuming the whole message (board.py's simpler `board reply <id>`
command still does that -- this is the richer, opt-in experience).

Split into its own module (Ryan's call) rather than folded into
commands/board/board.py, since the interactive reader/quote-preview/mail
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


def _menu_options_lines(ctx) -> list[str]:
    """The full end-of-message option list -- shown as ctx.prompt()'s
    preamble to non-expert players every time, and to anyone who types
    '?' to recall it. Borderless two-column table, same convention as
    _quote_option_lines()."""
    from table import Table
    t = Table(headers=['', ''], show_header=False, border=False)
    t.add_row(['[R]eply', 'reply to this message'])
    t.add_row(['[M]ail poster', 'send the author a private mail'])
    t.add_row(['[L]ist', 'list every message in this thread'])
    t.add_row(['<#>', 'jump straight to reply #'])
    t.add_row([ctx.player.return_key, 'read the next message'])
    t.add_row(["'pm'", 'toggle Prompt Mode'])
    t.add_row(['[Q]uit', 'back to the board listing'])
    t.add_row(["'?'", 'show this list again'])
    return [''] + t.render(width=_screen_width(ctx))


def _numbered_lines(lines: list[str]) -> list[str]:
    """'1: text', '2: text', ... -- matches text_editor.py's own
    LINE_NUMBERS display convention. Shared by the quote-range picker's
    own [L]ist option (see _reply_with_quote()) so a player can see what
    range to type before answering."""
    return ['', *[f'{i}: {t}' for i, t in enumerate(lines, 1)], '']


def _quote_option_lines(ctx) -> list[str]:
    """Borderless two-column table explaining the quote-range prompt's
    three answers -- shown as a preamble (not baked into the prompt text
    itself, which becomes a client's single-line input prefix with
    nowhere to wrap a long line on an 80-column terminal). Hidden for
    Expert Mode players, same show/hide-by-expertise convention as
    _menu_options_lines()."""
    from table import Table
    t = Table(headers=['', ''], show_header=False, border=False)
    t.add_row(['[L]ist lines', 'line ranges accepted'])
    t.add_row(['Line range', 'e.g., 3-, 1-3, -6, 6-+6'])
    t.add_row([ctx.player.return_key, 'no quote'])
    return t.render(width=_screen_width(ctx))


async def _list_thread_messages(ctx, thread: dict, privileged: bool) -> None:
    """[L]ist: a numbered index of every message in the thread, matching
    the same numbering <#> jump already accepts (root is unnumbered --
    it's always where reading started, not a jump target)."""
    lines = ['', f"|yellow|--- {thread.get('title', '(untitled)')}|reset|",
             f'   Root: {board_store.display_author(thread, privileged)}']
    for i, reply in enumerate(thread.get('replies', []), 1):
        title = reply.get('title') or f'Reply #{i}'
        lines.append(f'   {i}. {title}  -- {board_store.display_author(reply, privileged)}')
    lines.append('')
    await ctx.send(lines)


async def read_thread_interactive(ctx, thread: dict) -> None:
    """Walk *thread* one message at a time (root, then each reply in
    posted order). Only called when PlayerFlags.PROMPT_MODE is on --
    commands/board/board.py's _read_one() gates on that; this assumes it.
    The root header's own "Number: x of y" line shows this message's
    position within *this* thread (1 of however many messages it has),
    not this thread's place among every thread on the board -- Ryan's
    call, so it reads as "which message you're on," matching the
    [Reply x of y] preamble replies get below."""
    privileged = _is_privileged(ctx.player)
    width = _screen_width(ctx)

    messages = [thread] + list(thread.get('replies', []))
    idx = 0
    while idx < len(messages):
        entry = messages[idx]
        is_root = (idx == 0)

        reply_count = len(thread.get('replies', []))
        title = thread.get('title', '(untitled)') if is_root else (entry.get('title') or f'Reply #{idx}')
        header = board_store.MessageHeader.for_entry(
            entry, title, privileged, reply_count=reply_count if is_root else 0,
            thread_number=1 if is_root else 0,
            total_threads=len(messages) if is_root else 0).display()
        header.append('')
        await ctx.send([''] + header + board_store.render_message_lines(entry, ctx, width) + [''])

        # "[Reply x of y]" -- distinct from the root header's own
        # "Number: x of y" (that one's the thread's place on the whole
        # board; this is the reply's place within *this* thread), shown
        # regardless of Expert Mode since it's a short position hint,
        # not the full option list.
        preamble = []
        if not is_root and ctx.player.query_flag(PlayerFlags.PROMPT_MODE):
            preamble.append(f'[Reply {idx} of {reply_count}]')
        if not ctx.player.is_expert:
            preamble += _menu_options_lines(ctx)
        raw = await ctx.prompt('End of bulletin option', preamble_lines=preamble or None)
        if raw is None:
            return  # disconnected mid-read
        choice = raw.strip()

        if not choice:
            idx += 1
            continue

        low = choice.lower()
        if choice == '?':
            await ctx.send(_menu_options_lines(ctx))
        elif low == 'r':
            await _reply_with_quote(ctx, thread, entry, privileged)
            idx += 1
        elif low == 'm':
            await _mail_poster(ctx, entry, privileged)
            # deliberately doesn't advance -- they may still want to
            # reply to or keep reading the same message.
        elif low == 'l':
            await _list_thread_messages(ctx, thread, privileged)
        elif low in ('pm', 'promptmode'):
            from commands.board.board import toggle_prompt_mode
            await toggle_prompt_mode(ctx)
            # deliberately doesn't advance -- same as [M]ail poster above.
        elif low == 'q':
            return  # back to the board listing, without reading the rest
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
    from text_editor import (
        Border, BorderRole, Buffer, DefaultLineRange, Line, LineFlag,
        process_line_range_string, run_editor,
    )

    width = _screen_width(ctx)
    quoted_lines = board_store.render_message_lines(quoted_entry, ctx, width)
    author_display = board_store.display_author(quoted_entry, privileged)
    buffer = Buffer(lines=[Line(text=t) for t in quoted_lines])

    quote_lines: list[str] | None = None
    while True:
        # The explanation is a preamble line (shown above the input area),
        # not baked into the prompt text itself -- ctx.prompt()'s prompt
        # string becomes a client's single-line input prefix (see
        # tada_client.py's input_window), which has nowhere to wrap a
        # long line on an 80-column terminal.
        preamble = None if ctx.player.is_expert else _quote_option_lines(ctx)
        raw = await ctx.prompt('Quote which lines?', preamble_lines=preamble)
        if raw is None:
            return  # disconnected
        ans = raw.strip()
        if not ans or ans.lower() == 'n':
            break
        if ans.lower() == 'l':
            await ctx.send(_numbered_lines(quoted_lines))
            continue

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

    from commands.board.board import resolve_anonymous, prompt_reply_title
    anonymous = await resolve_anonymous(ctx)
    if anonymous is None:
        await ctx.send('Cancelled.')
        return

    default_title = quoted_entry.get('title') or thread.get('title', '(untitled)')
    title = await prompt_reply_title(ctx, default_title)
    if title is None:
        await ctx.send('Cancelled.')
        return

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
        #
        # Also boxed via the same Border/BorderRole mechanism .B Border
        # uses -- Line/LineFlag and Line/Border are independent fields,
        # so a line can be protected *and* boxed at once. Since that
        # box is stored (not baked into .text), it stays boxed later
        # too, whenever this reply is displayed to a reader, not just
        # while composing -- render_lines() batches the TOP/CONTENT.../
        # BOTTOM run into one real, terminal-aware box either way.
        initial_lines = [
            Line(text=f'{author_display} wrote:', line_flag=LineFlag.QUOTE),
            Line(line_flag=LineFlag.QUOTE, border=Border(role=BorderRole.TOP)),
        ] + [
            Line(text=t, line_flag=LineFlag.QUOTE, border=Border(role=BorderRole.CONTENT))
            for t in quote_lines
        ] + [
            Line(line_flag=LineFlag.QUOTE, border=Border(role=BorderRole.BOTTOM)),
        ]
    await ctx.send('Enter your reply.')
    body = await run_editor(ctx, initial_lines=initial_lines,
                             activity_id=f'board_reply:{thread.get("id", "")}',
                             activity_label=f'replying to board thread #{thread.get("id", "")}')
    if body is None:
        await ctx.send('Cancelled.')
        return

    reply = {
        'author':    ctx.player.name,
        'title':     title,
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
    fresh_replies = fresh_thread.setdefault('replies', [])
    fresh_replies.append(reply)
    reply_number = len(fresh_replies)
    board_store.save_board(threads)
    await ctx.send(f'Reply {reply_number} posted to "{fresh_thread.get("title", "(untitled)")}".')
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
