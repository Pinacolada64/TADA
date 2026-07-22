"""commands/board.py — The BOARD command: threaded message board.

Design per MECHANICS.md's "Threaded Message Boards" section, porting
the `threaded_messages.py` prototype into this codebase's real
architecture. See board.py (top-level) for storage/rendering; this
module is just the in-game command surface:

  board                 — list all threads (id, title, author, replies)
  board rn               — list only threads with activity since your
                            own "read new" threshold (see 'board ld')
  board ld                — set/move that threshold -- an absolute date,
                            or a relative shortcut ('week', '2 months', ...)
  board <id>             — read one thread in full (root post + replies)
  board post              — write a new thread
  board reply <id>        — reply to a thread; shows what you're replying
                            to in a "Quoting <author>" box first
  board delete <id>       — (admin) remove a thread
  board #edit              — (admin) board-wide settings menu, e.g. the
                            anonymous-posting default -- see
                            commands/board_edit.py

Post/reply authoring uses text_editor.run_editor() -- same as NEWS
(commands/news.py). Any logged-in player can post/reply (this isn't
admin-gated, unlike NEWS, since a message board is meant to be
conversational/multi-author -- see MECHANICS.md's "Convergence with
News & Mail" note); only 'board delete'/'board #edit' require
PlayerFlags.ADMIN.
"""
from __future__ import annotations

import datetime
import logging

import board as board_store
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from formatting import deserialize_lines, hrule_char, make_rule

log = logging.getLogger(__name__)

_DATE_COL_WIDTH = 13


def _is_privileged(player) -> bool:
    return bool(player.query_flag(PlayerFlags.ADMIN) or player.query_flag(PlayerFlags.DUNGEON_MASTER))


async def resolve_anonymous(ctx) -> bool | None:
    """Whether a post/reply should be anonymous, per the board-wide
    anonymous_mode admin setting (board.load_config(), changed via
    'board #edit') -- 'yes'/'no' skip the prompt entirely; 'ask' (the
    default) prompts as before. Returns None if the player disconnected
    mid-prompt. Shared by this module's own _post()/_reply() and
    commands/board_reply.py's interactive reply flow, so both paths
    honor the same admin setting instead of each hardcoding their own
    always-ask prompt."""
    mode = board_store.load_config().get('anonymous_mode', 'ask')
    if mode == 'yes':
        return True
    if mode == 'no':
        return False
    raw = await ctx.prompt('Post anonymously? (y/N)')
    if raw is None:
        return None
    return raw.strip().lower().startswith('y')


class BoardCommand(Command):
    name    = 'board'
    aliases = ['bb']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Read and post to the threaded message board.',
        description = (
            'Lists every thread on the board. Pick one by number to read it '
            'in full, including replies. Anyone can start a thread or reply '
            "-- 'board delete' is admin-only."
        ),
        category = HelpCategory.COMMUNICATION,
        usage    = [
            ('board',             'List all threads.'),
            ('board rn',          "List only threads new since your last 'board ld'."),
            ('board ld',          'Set/move your "read new" threshold date.'),
            ('board <id>',        'Read one thread in full.'),
            ('board post',        'Start a new thread.'),
            ('board reply <id>',  'Reply to a thread.'),
            ('board delete <id>', '(Admin) Remove a thread.'),
            ('board #edit',       '(Admin) Board-wide settings menu.'),
        ],
        notes = [
            "Bare 'board' stays in the listing -- press Enter with no "
            "number to leave it.",
            "Whether you're asked to post anonymously, always post "
            "anonymously, or never do depends on the board's own "
            "anonymous-posting setting; admins and Dungeon Masters still "
            "see who really posted either way.",
            "With Prompt Mode on ('pm' to toggle), reading a thread shows "
            "one message at a time with a [R]eply/[M]ail poster/<#>/"
            "Enter menu after each.",
        ],
        admin_notes = [
            "Prompt Mode is PlayerFlags.PROMPT_MODE -- also toggleable "
            "(for any player, not just yourself) via EditPlayer's Flags "
            "-> Option Toggles menu. See commands/board_reply.py for the "
            "interactive reader itself.",
            "'board #edit' opens a small settings menu (currently just "
            "the anonymous-posting default: Ask/Yes/No) -- see "
            "commands/board_edit.py.",
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        positional, switches = self.parse_args(*args)

        if switches:
            switch = switches[0].lstrip('#').lower()
            if switch == 'edit':
                from commands.board_edit import edit_board_settings
                return await edit_board_settings(ctx)
            await ctx.send(f"Unknown option '{switches[0]}'.")
            return CommandResult.fail('Unknown option.', error='bad_args')

        sub = positional[0].lower() if positional else ''

        if sub == 'post':
            return await self._post(ctx)
        if sub == 'reply' and len(positional) > 1:
            return await self._reply(ctx, positional[1])
        if sub == 'delete' and len(positional) > 1:
            return await self._delete(ctx, positional[1])
        if sub == 'rn':
            return await self._list(ctx, new_only=True)
        if sub == 'ld':
            return await self._set_last_date(ctx)
        if positional and positional[0].isdigit():
            return await self._read_one(ctx, int(positional[0]))

        return await self._list(ctx)

    # ------------------------------------------------------------------
    # Player-facing
    # ------------------------------------------------------------------

    async def _list(self, ctx, new_only: bool = False) -> CommandResult:
        """Show the thread listing and stay in it -- reading a thread just
        redisplays the listing -- until the player presses Enter to leave.
        While active, the player's virtual location (commands/whereat.py)
        reads 'Reading board'. With new_only, filters to threads with
        activity since the player's own board_last_date threshold."""
        privileged = _is_privileged(ctx.player)
        since = self._last_date(ctx)

        previous_location = getattr(ctx.client, 'virtual_location', None)
        ctx.client.virtual_location = 'Reading board'
        try:
            while True:
                threads = board_store.load_board()
                if new_only:
                    threads = [t for t in threads if board_store.is_new_since(t, since)]
                if not threads:
                    await ctx.send('No new threads.' if new_only else 'No threads on the board yet.')
                    return CommandResult.ok('No threads.')

                rule_width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
                lines = [
                    '', '|yellow|Message Board|reset|', '',
                    make_rule(rule_width, hrule_char(ctx)),
                ]
                for t in threads:
                    lines.append(board_store.format_thread_summary(t, privileged))
                lines.append('')

                raw = await ctx.prompt(
                    f'Read which (# or {ctx.player.return_key} to exit)',
                    preamble_lines=lines,
                )
                if raw is None or not raw.strip():
                    return CommandResult.ok('Exited board.')

                choice = raw.strip()
                if choice.isdigit():
                    await self._read_one(ctx, int(choice))
                else:
                    await ctx.send(f"'{choice}' is not a valid thread id.")
        finally:
            ctx.client.virtual_location = previous_location

    async def _read_one(self, ctx, thread_id: int) -> CommandResult:
        threads = board_store.load_board()
        thread = next((t for t in threads if t.get('id') == thread_id), None)
        if thread is None:
            await ctx.send('No such thread.')
            return CommandResult.fail('Unknown thread.', error='not_found')

        if ctx.player.query_flag(PlayerFlags.PROMPT_MODE):
            # One message at a time with an end-of-message [R]eply/[M]ail/
            # <#>/Enter menu, quote-with-preview on reply -- see
            # commands/board_reply.py's own module docstring.
            from commands.board_reply import read_thread_interactive
            await read_thread_interactive(ctx, thread)
            return CommandResult.ok('Displayed thread.')

        privileged = _is_privileged(ctx.player)
        await ctx.send([''] + board_store.format_thread(thread, ctx, privileged) + [''])
        return CommandResult.ok('Displayed thread.')

    # ------------------------------------------------------------------
    # "Read new" threshold (board rn / board ld)
    # ------------------------------------------------------------------

    def _last_date(self, ctx) -> datetime.date | None:
        raw = ctx.player.command_settings.board.last_date
        if not raw:
            return None
        try:
            return datetime.date.fromisoformat(raw)
        except ValueError:
            return None

    async def _set_last_date(self, ctx) -> CommandResult:
        from parse_date import DATE_HELP, RELATIVE_DATE_HELP, parse_date, parse_relative_date

        settings = ctx.player.command_settings
        cur = settings.board.last_date
        cur_str = cur if cur else '(not set -- everything currently counts as new)'
        raw = await ctx.prompt(
            'New threshold',
            preamble_lines=['', f'Current: {cur_str}', '', RELATIVE_DATE_HELP, '', DATE_HELP,
                            '', 'Blank to cancel:'],
        )
        if raw is None or not raw.strip():
            await ctx.send('Unchanged.')
            return CommandResult.ok('Unchanged.')

        text = raw.strip()
        new_date = parse_relative_date(text) or parse_date(text)
        if new_date is None:
            await ctx.send("Didn't understand that date.")
            return CommandResult.fail('Bad date.', error='bad_args')

        settings.board.last_date = new_date.isoformat()
        ctx.player.unsaved_changes = True
        await ctx.send(
            f"Threshold set to {new_date.strftime('%B %d, %Y')}. "
            f"'board rn' will show anything posted after this date."
        )
        return CommandResult.ok('Threshold set.')

    # ------------------------------------------------------------------
    # Posting / replying (any logged-in player)
    # ------------------------------------------------------------------

    async def _post(self, ctx) -> CommandResult:
        from text_editor import run_editor

        title = await ctx.prompt('Title')
        if not title or not title.strip():
            await ctx.send('Cancelled — no title given.')
            return CommandResult.fail('No title.', error='missing_title')
        title = title.strip()

        anonymous = await resolve_anonymous(ctx)
        if anonymous is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        await ctx.send('Enter the thread body.')
        body = await run_editor(ctx)
        if body is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        threads = board_store.load_board()
        thread = {
            'id':        board_store.next_id(threads),
            'title':     title,
            'author':    ctx.player.name,
            'anonymous': anonymous,
            'posted_at': datetime.datetime.now().isoformat(),
            'body':      body,
            'replies':   [],
        }
        threads.append(thread)
        board_store.save_board(threads)
        await ctx.send(f"Thread #{thread['id']} posted.")
        log.info('BOARD POST: %s posted thread #%s %r', ctx.player.name, thread['id'], title)
        return CommandResult.ok('Posted thread.')

    async def _reply(self, ctx, id_str: str) -> CommandResult:
        from text_editor import run_editor

        if not id_str.isdigit():
            await ctx.send('Usage: board reply <id>')
            return CommandResult.fail('Bad id.', error='bad_args')

        threads = board_store.load_board()
        thread = next((t for t in threads if t.get('id') == int(id_str)), None)
        if thread is None:
            await ctx.send('No such thread.')
            return CommandResult.fail('Unknown thread.', error='not_found')

        anonymous = await resolve_anonymous(ctx)
        if anonymous is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        privileged = _is_privileged(ctx.player)
        await ctx.send(board_store.build_quote_preamble(ctx, thread, privileged))
        await ctx.send('Enter your reply.')
        body = await run_editor(ctx)
        if body is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        reply = {
            'author':    ctx.player.name,
            'anonymous': anonymous,
            'posted_at': datetime.datetime.now().isoformat(),
            'body':      body,
        }
        thread.setdefault('replies', []).append(reply)
        board_store.save_board(threads)
        await ctx.send(f"Reply posted to thread #{thread['id']}.")
        log.info('BOARD REPLY: %s replied to thread #%s', ctx.player.name, thread['id'])
        return CommandResult.ok('Posted reply.')

    # ------------------------------------------------------------------
    # Admin-only
    # ------------------------------------------------------------------

    async def _delete(self, ctx, id_str: str) -> CommandResult:
        if not ctx.player.query_flag(PlayerFlags.ADMIN):
            await ctx.send('You lack the authority to do that.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        if not id_str.isdigit():
            await ctx.send('Usage: board delete <id>')
            return CommandResult.fail('Bad id.', error='bad_args')

        threads = board_store.load_board()
        thread = next((t for t in threads if t.get('id') == int(id_str)), None)
        if thread is None:
            await ctx.send('No such thread.')
            return CommandResult.fail('Unknown thread.', error='not_found')

        threads.remove(thread)
        board_store.save_board(threads)
        await ctx.send(f"Thread #{thread['id']} deleted.")
        log.info('ADMIN BOARD DELETE: %s deleted thread #%s', ctx.player.name, thread['id'])
        return CommandResult.ok('Deleted thread.')
