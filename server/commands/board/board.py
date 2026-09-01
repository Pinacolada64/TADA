"""commands/board/board.py — The BOARD command: threaded message board.

Design per MECHANICS.md's "Threaded Message Boards" section. See
board/ (top-level package) for storage/rendering; this module is just
the in-game command surface:

  board                 — list all threads (id, title, author, replies)
  board rn               — list only threads with activity since your
                            own "read new" threshold (see 'board ld'),
                            on the current board only
  board ra                — Read All (new): full text of every new
                            thread across every SIG/board you can
                            access, not just the current one
  board sa                — Scan All (new): same scope as 'board ra',
                            headers only (no message bodies)
  board ld                — set/move that threshold -- an absolute date,
                            or a relative shortcut ('week', '2 months', ...)
  board <id>             — read one thread in full (root post + replies)
  board post              — write a new thread
  board reply <id>        — reply to a thread; shows what you're replying
                            to in a "Quoting <author>" box first
  board delete <id>       — (admin) remove a thread
  board #edit              — (admin) board-wide settings menu, e.g. the
                            anonymous-posting default -- see
                            commands/board/edit.py

Post/reply authoring uses text_editor.run_editor() -- same as NEWS
(commands/news.py). Any logged-in player can post/reply (this isn't
admin-gated, unlike NEWS, since a message board is meant to be
conversational/multi-author); only 'board delete'/'board #edit' require
PlayerFlags.ADMIN.

Phase 1 of the sig-editor project (see the approved plan): storage now
lives in the board/ package (SIG/board-aware), but there's still only
ever one board (_DEFAULT_BOARD_ID below) -- no SIG/board picker yet.
Every thread this command shows/creates is scoped to that one board id,
so player-facing behavior is unchanged from before this split. Phase 2
replaces the hardcoded id with real board selection.
"""
from __future__ import annotations

import datetime
import logging

import banner
import board as board_store
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from formatting import deserialize_lines, hrule_char, make_rule

log = logging.getLogger(__name__)

_DATE_COL_WIDTH = 13

# Phase 1: only one board exists -- see this module's own docstring.
_DEFAULT_BOARD_ID = board_store.meta.DEFAULT_BOARD_ID


def _is_privileged(player) -> bool:
    return bool(player.query_flag(PlayerFlags.ADMIN) or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def _can_access_board(ctx, board_id: int) -> bool:
    """Can ctx's player access board *board_id*? Wraps board/access.py's
    player_can_access() with a fresh meta_data load, for the direct-id
    call sites (_read_one()/_reply()/_delete(), reached via a globally-
    unique thread id and its own thread['board_id'] -- not through
    pick_board(), which already filters its pickers via
    accessible_board_ids()/visible_sigs())."""
    board = board_store.meta.get_board(board_store.meta.load_meta(), board_id)
    return board_store.player_can_access(ctx.player, board)


def _is_petscii(ctx) -> bool:
    """Whether ctx's player is on a real Commodore (PETSCII) connection --
    mirrors commands/help.py's _is_petscii_viewer(). Used to pick '...'
    over a real ellipsis character when eliding a too-long thread title
    in the listing, since Commodore font ROMs don't have one."""
    client_settings = getattr(getattr(ctx, 'player', None), 'client_settings', None)
    if client_settings is None:
        return False
    from formatting import codec_for_settings, PETSCIICodec
    return isinstance(codec_for_settings(client_settings), PETSCIICodec)


async def toggle_prompt_mode(ctx) -> None:
    """Flip PlayerFlags.PROMPT_MODE and report the new state -- same
    underlying toggle as the standalone 'pm' command (commands/
    prompt_mode.py), reachable here too so a player can turn Prompt Mode
    on/off without leaving the BOARD listing prompt or the interactive
    reader's end-of-bulletin prompt (commands/board/reply.py)."""
    new_state, _ = ctx.player.toggle_flag(PlayerFlags.PROMPT_MODE)
    ctx.player.unsaved_changes = True
    await ctx.send(f"Prompt Mode: {'On' if new_state else 'Off'}.")


async def resolve_anonymous(ctx, board_id: int = _DEFAULT_BOARD_ID) -> bool | None:
    """Whether a post/reply should be anonymous, per *board_id*'s own
    anonymous_mode setting (board.meta, changed per-board via
    'board #edit' since Phase 2) -- 'yes'/'no' skip the prompt entirely;
    'ask' (the default) prompts as before. Returns None if the player
    disconnected mid-prompt. Shared by this module's own _post()/_reply()
    and commands/board/reply.py's interactive reply flow, so both paths
    honor the same per-board setting instead of each hardcoding their
    own always-ask prompt."""
    board = board_store.meta.get_board(board_store.meta.load_meta(), board_id)
    mode = board.get('anonymous_mode', 'ask')
    if mode == 'yes':
        return True
    if mode == 'no':
        return False
    raw = await ctx.prompt('Post anonymously? (y/N)')
    if raw is None:
        return None
    return raw.strip().lower().startswith('y')


async def prompt_reply_title(ctx, default_title: str) -> str | None:
    """Ask for this reply's own title, defaulting to "Re: <default_title>"
    (the title of whatever's being replied to) on a bare Enter -- Ryan's
    call, so a reply can carry its own title instead of every reply in
    the [L]ist index/reader header just reading "Reply #3". Doesn't
    double up "Re: Re: ..." when replying to something already titled
    that way. Returns None if the player disconnected mid-prompt.
    Shared by this module's own _reply() and commands/board/reply.py's
    interactive reply flow."""
    raw = await ctx.prompt(
        'Reply title',
        preamble_lines=['', f'({ctx.player.return_key} keeps "{default_title}")', ''],
    )
    if raw is None:
        return None
    raw = raw.strip()
    if raw:
        return raw
    return default_title if default_title.startswith('Re: ') else f'Re: {default_title}'


def _threads_for_board(all_threads: list[dict], board_id: int) -> list[dict]:
    """Threads belonging to *board_id* -- missing 'board_id' (threads
    seeded/created before this split, or in tests that don't bother
    setting it) counts as the default board, so nothing pre-existing
    silently vanishes from the listing."""
    return [t for t in all_threads if t.get('board_id', _DEFAULT_BOARD_ID) == board_id]


def _title_taken(board_threads: list[dict], title: str) -> bool:
    """Case-insensitive check for an existing thread with this exact
    title on the same board -- Ryan's call, so 'board post' rejects an
    accidental duplicate up front rather than leaving two same-titled
    threads sitting side by side in the listing."""
    target = title.strip().lower()
    return any(t.get('title', '').strip().lower() == target for t in board_threads)


def _single_board_shortcut(sig_list: list[dict]) -> bool:
    """True when there's nothing to pick between: no SIGs at all (a
    fresh install that's never touched 'board #edit'), or exactly one
    SIG holding at most one board -- i.e. the state migration.py always
    produces. In either case, 'board'/'board post'/'board rn' go
    straight to _DEFAULT_BOARD_ID exactly like before Phase 2, instead
    of showing a picker with nothing to pick."""
    if not sig_list:
        return True
    return len(sig_list) == 1 and len(sig_list[0].get('board_ids', [])) <= 1


def _listing_menu_lines(ctx, width: int) -> list[str]:
    """'?' at the bare thread-listing prompt -- full key rundown, same
    borderless-two-column-table convention as commands/board/reply.py's
    own _menu_options_lines() for the end-of-bulletin prompt one level
    down. Not hidden for experts here (unlike that one) -- this listing
    doesn't show its own hint every time by default the way that reader
    does, so there's no separate "already visible" state to spare an
    expert from."""
    from table import Table
    t = Table(headers=['', ''], show_header=False, border=False)
    t.add_row(['[<#>]', 'read that thread'])
    t.add_row([f'[{ctx.player.return_key}]', 'read the next thread'])
    t.add_row(['[P]ost', 'start a new thread'])
    t.add_row(['[Q]uit', 'leave the message board'])
    t.add_row(["'>' / '<'", 'next / previous board in this SIG'])
    t.add_row(["'>>' / '<<'", 'next / previous SIG'])
    t.add_row(['[pm]', 'toggle Prompt Mode'])
    t.add_row(["'?'", 'show this list again'])
    return [''] + t.render(width=width) + ['']


# Sentinel returned by _pick_from_numbered_list() when the player types
# 'B' at a picker that offers one (distinct from None, which means they
# backed out of picking anything at all -- see pick_board()'s loop).
_BACK = object()


async def _pick_from_numbered_list(ctx, items: list[dict], *, noun: str,
                                    header: str | None = None,
                                    allow_back: bool = False) -> dict | object | None:
    """Show a 1-based numbered list of *items* (each needs a 'name' key)
    and prompt for a pick. *header*, if given, is a title line shown
    above the list (e.g. 'Special Interest Groups (SIGs)'). With
    allow_back=True, 'B' returns the _BACK sentinel instead of a pick --
    used by the board picker to step back up to the SIG list rather than
    cancelling out of 'board' entirely. None on a blank/disconnected
    answer (the player backed out) or an out-of-range/non-numeric one
    (reported and treated as backing out, rather than looping forever)."""
    lines = [''] + ([f'|yellow|{header}|reset|', ''] if header else [])
    lines += [f'  {i}. {item.get("name", "(unnamed)")}' for i, item in enumerate(items, 1)]
    if allow_back:
        lines.append('  B. Back to SIGs list')
    lines.append(f'({ctx.player.return_key} to cancel)')
    lines.append('')
    raw = await ctx.prompt(f'Which {noun}', preamble_lines=lines)
    if raw is None or not raw.strip():
        return None
    choice = raw.strip()
    if allow_back and choice.lower() == 'b':
        return _BACK
    if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
        await ctx.send(f"'{choice}' is not a valid {noun} number.")
        return None
    return items[int(choice) - 1]


def _welcome_lines(kind: str, name: str, admins: list[str]) -> list[str]:
    """Greeting shown on entering a SIG or a board (see pick_board()).
    *kind* is used verbatim -- 'SIG' (acronym stays capped) or 'board'.
    One named operator reads as "your <kind> administrator here"; several
    read as "<kind> operators here are ..." (Ryan's wording); none says
    the SIG/board is currently unadministered."""
    from tada_utilities import oxford_comma_list

    if not admins:
        who = f'This {kind} currently has no administrator.'
    elif len(admins) == 1:
        who = f'Your {kind} administrator here is {admins[0]}.'
    else:
        who = f'The {kind} operators here are {oxford_comma_list(admins)}.'
    return [f'Welcome to the {name} {kind}!', who]


async def _show_intro_screen(ctx, path) -> None:
    """Show *path*'s SIG/board intro screen, if one has been saved there
    (see board/intro.py) -- skipped entirely for PlayerFlags.EXPERT_MODE
    players (Ryan's call: this is an onboarding/flavor extra shown right
    after the plain-text _welcome_lines() greeting, not something an
    experienced player needs re-shown every time they switch SIGs/
    boards). A missing file is the expected common case (most SIGs/
    boards never get one) rather than a misconfiguration, so this checks
    existence itself instead of leaning on banner.load_banner()'s own
    "not found" warning log."""
    if ctx.player.is_expert or not path.exists():
        return
    lines = banner.load_banner(str(path))
    if lines:
        await ctx.send(lines)


async def _enter_sig(ctx, sig: dict) -> None:
    """Send a SIG's welcome greeting + intro screen -- shared by
    pick_board()'s picker path and _list()'s '>>' / '<<' next/previous-
    SIG navigation, so both show the same greeting on entry."""
    await ctx.send(_welcome_lines('SIG', sig.get('name', '(unnamed)'), sig.get('admins', [])))
    await _show_intro_screen(ctx, board_store.sig_intro_path(sig['id']))


async def _enter_board(ctx, meta_data: dict, board_id: int) -> None:
    """Send a board's welcome greeting + intro screen -- shared by
    pick_board()'s picker path and _list()'s '>' / '<' / '>>' / '<<'
    navigation, so both show the same greeting on entry."""
    board = board_store.meta.get_board(meta_data, board_id)
    await ctx.send(_welcome_lines('board', board.get('name', '(unnamed)'), board.get('admins', [])))
    await _show_intro_screen(ctx, board_store.board_intro_path(board_id))


async def _resolve_board_in_sig(ctx, chosen_sig: dict, meta_data: dict, *, multi_sig: bool):
    """Given a SIG the player just entered, resolve which of its boards
    to land on -- straight to the only one, or via a numbered picker
    (offering 'B. Back to SIGs list' when allow_back). Sends both the
    SIG's and the resolved board's welcome+intro. Returns the board id,
    the _BACK sentinel (only reachable when multi_sig), or None if the
    SIG has no boards -- or none the player can access, same message
    either way (Ryan's call: don't hint that gated boards exist here) --
    or the player backed fully out of the picker."""
    await _enter_sig(ctx, chosen_sig)

    board_ids = board_store.accessible_board_ids(ctx.player, meta_data, chosen_sig.get('board_ids', []))
    if not board_ids:
        await ctx.send(f"{chosen_sig.get('name', '(unnamed)')} has no boards yet.")
        return None

    if len(board_ids) == 1:
        board_id = board_ids[0]
    else:
        boards = [board_store.meta.get_board(meta_data, bid) for bid in board_ids]
        picked = await _pick_from_numbered_list(ctx, boards, noun='board', allow_back=multi_sig)
        if picked is _BACK:
            return _BACK
        if picked is None:
            return None
        board_id = picked['id']
    await _enter_board(ctx, meta_data, board_id)
    return board_id


async def pick_board(ctx) -> tuple[int, int | None] | None:
    """Which (board_id, sig_id) a bare 'board'/'board post'/'board rn'
    should act on: (_DEFAULT_BOARD_ID, sig_id or None) with no picker
    shown at all when there's only one board to choose from (see
    _single_board_shortcut -- keeps today's single-board UX exactly
    unchanged for every install that hasn't touched 'board #edit' yet),
    otherwise a two-level SIG-then-board numbered picker (decision 8 in
    the sig-editor plan: menu-driven navigation only, no 'board 2.3'
    shorthand). sig_id is returned alongside board_id so _list() can
    offer '>'/'<'/'>>'/'<<' same-SIG/next-SIG navigation without
    re-deriving which SIG a (possibly shared) board came from. Threads
    themselves (board <id>/reply <id>/delete <id>) are found by their
    own globally-unique id regardless of board, so they never need this.
    None if the player backs out of the SIG level, of the board level
    with only one visible SIG to offer 'back' to, or has access to no
    board at all. With more than one visible SIG, 'B' at the board
    level loops back to the SIG picker instead of cancelling out of
    'board' entirely. A SIG/board the player's access gate excludes
    never appears in either picker -- see board/access.py's
    visible_sigs()/accessible_board_ids()."""
    sig_data = board_store.sigs.load_sigs()
    sig_list = sig_data.get('sigs', [])
    meta_data = board_store.meta.load_meta()

    if _single_board_shortcut(sig_list):
        if not board_store.player_can_access(ctx.player, board_store.meta.get_board(meta_data, _DEFAULT_BOARD_ID)):
            await ctx.send("You don't have access to any boards yet.")
            return None
        return _DEFAULT_BOARD_ID, (sig_list[0]['id'] if sig_list else None)

    visible = board_store.visible_sigs(ctx.player, sig_list, meta_data)
    if not visible:
        await ctx.send("You don't have access to any boards yet.")
        return None

    multi_sig = len(visible) > 1
    while True:
        if len(visible) == 1:
            chosen_sig = visible[0]
        else:
            chosen_sig = await _pick_from_numbered_list(
                ctx, visible, noun='SIG', header='Special Interest Groups (SIGs)')
            if chosen_sig is None:
                return None
        result = await _resolve_board_in_sig(ctx, chosen_sig, meta_data, multi_sig=multi_sig)
        if result is _BACK:
            continue
        if result is None:
            return None
        return result, chosen_sig['id']


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
            ('board rn',          "List only threads new since your last 'board ld', on this board."),
            ('board ra',          'Read All new threads (full text) across every SIG/board you can access.'),
            ('board sa',          'Scan All new threads (headers only) across every SIG/board you can access.'),
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
            "one message at a time with a [R]eply/[M]ail poster/[L]ist/<#>/"
            "Enter menu after each.",
        ],
        admin_notes = [
            "Prompt Mode is PlayerFlags.PROMPT_MODE -- also toggleable "
            "(for any player, not just yourself) via EditPlayer's Flags "
            "-> Option Toggles menu. See commands/board/reply.py for the "
            "interactive reader itself.",
            "'board #edit' opens a small settings menu (currently just "
            "the anonymous-posting default: Ask/Yes/No) -- see "
            "commands/board/edit.py.",
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        positional, switches = self.parse_args(*args)

        if switches:
            switch = switches[0].lstrip('#').lower()
            if switch == 'edit':
                from commands.board.edit import edit_board_settings
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
        if sub == 'ra':
            return await self._read_all_new(ctx)
        if sub == 'sa':
            return await self._scan_all_new(ctx)
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
        activity since the player's own board_last_date threshold.

        Picks which board via pick_board() -- a no-op picker (returns
        _DEFAULT_BOARD_ID straight away) until more than one board
        exists. None means the player backed out of the SIG/board
        picker without choosing anything. sig_id (alongside board_id)
        is what '>'/'<'/'>>'/'<<' below navigate relative to."""
        picked = await pick_board(ctx)
        if picked is None:
            return CommandResult.ok('Cancelled.')
        board_id, sig_id = picked

        since = self._last_date(ctx)
        position = -1  # index into this pass's 'threads' of the last-read one; -1 = none read yet

        previous_location = getattr(ctx.client, 'virtual_location', None)
        ctx.client.virtual_location = 'Reading board'
        try:
            while True:
                threads = _threads_for_board(board_store.load_board(), board_id)
                if new_only:
                    threads = [t for t in threads if board_store.is_new_since(t, since)]
                if not threads:
                    if new_only:
                        await ctx.send('No new threads.')
                        return CommandResult.ok('No threads.')
                    # Empty board (not just "nothing new") -- Ryan's call:
                    # let the player start the first thread right here
                    # instead of just bouncing them back out, same spirit
                    # as the bare listing's own [P]ost shortcut.
                    raw = await ctx.prompt('No threads on this board yet -- [P]ost one, or [Q]uit',
                                           preamble_lines=[''])
                    if raw is not None and raw.strip().lower() == 'p':
                        await self._post(ctx, board_id=board_id)
                        continue
                    return CommandResult.ok('Exited board.')

                rule_width = getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)
                lines = [
                    '', '|yellow|Message Board|reset|', '',
                    make_rule(rule_width, hrule_char(ctx)),
                ]
                lines += board_store.format_thread_listing(threads, rule_width, _is_petscii(ctx), since=since)
                lines.append(f"([<#>] read, [{ctx.player.return_key}] next, [P]ost, [Q]uit, '?' for help)")
                lines.append('')

                raw = await ctx.prompt('Read which', preamble_lines=lines)
                if raw is None:
                    return CommandResult.ok('Exited board.')  # disconnected mid-prompt

                choice = raw.strip()
                low = choice.lower()

                if not choice:
                    # Advance to the next thread in this same listing --
                    # Ryan's call, replacing the old "blank = leave"
                    # behavior (that's 'Q' now) so a player can walk the
                    # whole board with bare Enter, same shape as the
                    # end-of-bulletin reader's own Enter-advances feel
                    # (commands/board/reply.py), just one level up.
                    position += 1
                    if position >= len(threads):
                        # Wrap to the first thread rather than dead-ending
                        # on a repeated "No more threads." -- bare Enter
                        # should always do something, never just sit
                        # there re-printing the same notice.
                        position = 0
                        await ctx.send('Back to the first thread.')
                    await self._read_one(ctx, threads[position].get('id'))
                elif low == 'q':
                    return CommandResult.ok('Exited board.')
                elif low == 'p':
                    await self._post(ctx, board_id=board_id)
                elif choice in ('>', '<', '>>', '<<'):
                    nav = await self._navigate(ctx, choice, board_id=board_id, sig_id=sig_id)
                    if nav is not None:
                        board_id, sig_id = nav
                        position = -1
                elif choice == '?':
                    await ctx.send(_listing_menu_lines(ctx, rule_width))
                elif low in ('pm', 'promptmode'):
                    await toggle_prompt_mode(ctx)
                elif choice.isdigit():
                    target = int(choice)
                    # Keep 'next' in sync with whichever thread was just
                    # read by number, so a bare Enter afterward continues
                    # from there instead of restarting at the top.
                    idx = next((i for i, t in enumerate(threads) if t.get('id') == target), None)
                    if idx is not None:
                        position = idx
                    await self._read_one(ctx, target)
                else:
                    await ctx.send(f"'{choice}' is not a valid thread id.")
        finally:
            ctx.client.virtual_location = previous_location

    async def _navigate(self, ctx, choice: str, *, board_id: int,
                         sig_id: int | None) -> tuple[int, int | None] | None:
        """'>' / '<' step to the next/previous board within *sig_id*
        (by position in its board_ids list); '>>' / '<<' step to the
        next/previous SIG entirely, landing on that SIG's *first* board
        with no picker of its own -- Ryan's call, keeping this a single
        keystroke rather than nesting another board picker mid-listing.
        Reports and returns None (no navigation happened) at either end
        of a list, if *board_id*/*sig_id* aren't part of a SIG at all
        (the single-board-shortcut install with no SIGs configured), or
        a step would land somewhere the player's access gate excludes
        (skipped over entirely, same as such boards/SIGs never showing
        up in pick_board()'s own pickers -- see board/access.py's
        accessible_board_ids()/visible_sigs())."""
        sig_list = board_store.sigs.load_sigs().get('sigs', [])
        sig = next((s for s in sig_list if s.get('id') == sig_id), None)
        if sig is None:
            await ctx.send("This board isn't part of a SIG -- nothing to navigate to.")
            return None
        meta_data = board_store.meta.load_meta()

        if choice in ('>', '<'):
            board_ids = board_store.accessible_board_ids(ctx.player, meta_data, sig.get('board_ids', []))
            idx = board_ids.index(board_id) if board_id in board_ids else None
            if idx is None:
                await ctx.send("Can't find this board's position in its SIG.")
                return None
            new_idx = idx + 1 if choice == '>' else idx - 1
            if not (0 <= new_idx < len(board_ids)):
                await ctx.send('Already at the last board in this SIG.' if choice == '>'
                                else 'Already at the first board in this SIG.')
                return None
            new_board_id = board_ids[new_idx]
            await _enter_board(ctx, meta_data, new_board_id)
            return new_board_id, sig_id

        # '>>' / '<<' -- next/previous SIG.
        visible = board_store.visible_sigs(ctx.player, sig_list, meta_data)
        if len(visible) <= 1:
            await ctx.send("There's only one SIG.")
            return None
        idx = next((i for i, s in enumerate(visible) if s.get('id') == sig_id), None)
        if idx is None:
            await ctx.send("Can't find this SIG's position in the SIG list.")
            return None
        new_idx = idx + 1 if choice == '>>' else idx - 1
        if not (0 <= new_idx < len(visible)):
            await ctx.send('Already at the last SIG.' if choice == '>>' else 'Already at the first SIG.')
            return None
        new_sig = visible[new_idx]
        new_board_ids = board_store.accessible_board_ids(ctx.player, meta_data, new_sig.get('board_ids', []))
        if not new_board_ids:
            await ctx.send(f"{new_sig.get('name', '(unnamed)')} has no boards yet.")
            return None
        await _enter_sig(ctx, new_sig)
        new_board_id = new_board_ids[0]
        await _enter_board(ctx, meta_data, new_board_id)
        return new_board_id, new_sig['id']

    async def _read_one(self, ctx, thread_id: int) -> CommandResult:
        all_threads = board_store.load_board()
        thread = next((t for t in all_threads if t.get('id') == thread_id), None)
        if thread is None or not _can_access_board(ctx, thread.get('board_id', _DEFAULT_BOARD_ID)):
            # Same "No such thread." either way -- a gated board's
            # threads shouldn't be distinguishable from ones that don't
            # exist, for a player who can't see that board at all.
            await ctx.send('No such thread.')
            return CommandResult.fail('Unknown thread.', error='not_found')
        # Total-count context is "how many threads on *this* thread's own
        # board" -- found by its own board_id, not the picker/listing's
        # (a bare 'board <id>' can jump straight to a thread on any
        # board, bypassing pick_board() entirely, since ids are globally
        # unique -- see this module's own docstring).
        board_threads = _threads_for_board(all_threads, thread.get('board_id', _DEFAULT_BOARD_ID))

        if ctx.player.query_flag(PlayerFlags.PROMPT_MODE):
            # One message at a time with an end-of-message [R]eply/[M]ail/
            # <#>/Enter menu, quote-with-preview on reply -- see
            # commands/board/reply.py's own module docstring.
            from commands.board.reply import read_thread_interactive
            await read_thread_interactive(ctx, thread)
            return CommandResult.ok('Displayed thread.')

        privileged = _is_privileged(ctx.player)
        await ctx.send([''] + board_store.format_thread(
            thread, ctx, privileged, total_threads=len(board_threads)) + [''])
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
        from date_cursor import INVALID, UNCHANGED, prompt_date_cursor

        settings = ctx.player.command_settings
        result = await prompt_date_cursor(
            ctx, ctx.player, self._last_date(ctx), label='threshold',
            note="'board rn' will show anything posted after this date.",
        )
        if result is UNCHANGED:
            return CommandResult.ok('Unchanged.')
        if result is INVALID:
            return CommandResult.fail('Bad date.', error='bad_args')

        settings.board.last_date = result.isoformat() if result else None
        ctx.player.unsaved_changes = True
        return CommandResult.ok('Threshold set.')

    # ------------------------------------------------------------------
    # "Read All" / "Scan All" new (board ra / board sa) -- Phase 4 of the
    # sig-editor plan (ImageBBS-style RA/SA): same "read new" threshold
    # as 'board rn', but walking every SIG/board the player can access
    # instead of just the one they happen to be viewing.
    # ------------------------------------------------------------------

    def _new_threads_by_board(self, ctx) -> list[tuple[dict | None, dict, dict]]:
        """[(sig_or_None, board_meta, thread), ...] for every thread with
        activity since the player's 'board ld' threshold, across every
        SIG/board they can access -- SIG/board order, thread order
        within each board. sig is None only for the single-board-
        shortcut install (no real SIG structure configured yet); a
        gated SIG/board is silently excluded, same as pick_board()'s
        own pickers (see board/access.py's visible_sigs()/
        accessible_board_ids())."""
        since = self._last_date(ctx)
        all_threads = board_store.load_board()
        sig_list = board_store.sigs.load_sigs().get('sigs', [])
        meta_data = board_store.meta.load_meta()

        if _single_board_shortcut(sig_list):
            board = board_store.meta.get_board(meta_data, _DEFAULT_BOARD_ID)
            boards = [(sig_list[0] if sig_list else None, board)] \
                if board_store.player_can_access(ctx.player, board) else []
        else:
            boards = [
                (sig, board_store.meta.get_board(meta_data, bid))
                for sig in board_store.visible_sigs(ctx.player, sig_list, meta_data)
                for bid in board_store.accessible_board_ids(ctx.player, meta_data, sig.get('board_ids', []))
            ]

        items = []
        for sig, board in boards:
            board_threads = _threads_for_board(all_threads, board['id'])
            items += [(sig, board, t) for t in board_threads if board_store.is_new_since(t, since)]
        return items

    @staticmethod
    def _sig_board_label(sig: dict | None, board: dict) -> str:
        board_name = board.get('name', '(unnamed)')
        return f"{sig['name']} > {board_name}" if sig else board_name

    async def _read_all_new(self, ctx) -> CommandResult:
        items = self._new_threads_by_board(ctx)
        if not items:
            await ctx.send('No new messages.')
            return CommandResult.ok('No new messages.')

        privileged = _is_privileged(ctx.player)
        for i, (sig, board, thread) in enumerate(items):
            await ctx.send(
                ['', f"|yellow|{self._sig_board_label(sig, board)}|reset|"]
                + board_store.format_thread(thread, ctx, privileged) + [''])
            if i < len(items) - 1:
                raw = await ctx.prompt(f'{ctx.player.return_key} for next, Q to stop')
                if raw is None or raw.strip().lower() == 'q':
                    return CommandResult.ok(f'Stopped after {i + 1} of {len(items)}.')
        return CommandResult.ok(f'Read {len(items)} new thread(s).')

    async def _scan_all_new(self, ctx) -> CommandResult:
        items = self._new_threads_by_board(ctx)
        if not items:
            await ctx.send('No new messages.')
            return CommandResult.ok('No new messages.')

        privileged = _is_privileged(ctx.player)
        lines = []
        last_label = None
        for sig, board, thread in items:
            label = self._sig_board_label(sig, board)
            if label != last_label:
                lines += ['', f'|yellow|{label}|reset|']
                last_label = label
            title = f"#{thread.get('id', 0)}  {thread.get('title', '(untitled)')}"
            lines += board_store.MessageHeader.for_entry(
                thread, title, privileged, ctx.player,
                reply_count=len(thread.get('replies', []))).display()
        await ctx.send(lines + [''])
        return CommandResult.ok(f'Scanned {len(items)} new thread(s).')

    # ------------------------------------------------------------------
    # Posting / replying (any logged-in player)
    # ------------------------------------------------------------------

    async def _post(self, ctx, board_id: int | None = None) -> CommandResult:
        from text_editor import run_editor

        if board_id is None:
            picked = await pick_board(ctx)
            if picked is None:
                return CommandResult.ok('Cancelled.')
            board_id, _sig_id = picked
        elif not _can_access_board(ctx, board_id):
            # Defense in depth -- pick_board() already filters its
            # pickers, but board_id can also arrive pre-chosen from
            # _list()'s own [P]ost shortcut/empty-board prompt, so a
            # mid-session access change (e.g. a guild switch) doesn't
            # leave a stale post path open.
            await ctx.send("You don't have access to that board.")
            return CommandResult.fail('Access denied.', error='permission_denied')

        anonymous = await resolve_anonymous(ctx, board_id)
        if anonymous is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        board_threads = _threads_for_board(board_store.load_board(), board_id)
        while True:
            title = await ctx.prompt('Title')
            if not title or not title.strip():
                await ctx.send('Cancelled — no title given.')
                return CommandResult.fail('No title.', error='missing_title')
            title = title.strip()
            if _title_taken(board_threads, title):
                await ctx.send(f'A thread titled "{title}" already exists on this board — '
                                'choose a different title.')
                continue
            break

        await ctx.send('Enter the thread body.')
        # \x1f (unit separator) joins title+anonymous+board_id into
        # activity_id's single rest-of-string slot -- see commands/
        # edit.py's _resume_board_post() for the other end of this.
        activity_id = f'board_post:{title}\x1f{int(anonymous)}\x1f{board_id}'
        body = await run_editor(ctx, activity_id=activity_id,
                                 activity_label=f'posting board thread "{title}"')
        if body is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        threads = board_store.load_board()
        thread = {
            'id':        board_store.next_id(threads),
            'board_id':  board_id,
            'title':     title,
            'author':    ctx.player.name,
            'anonymous': anonymous,
            'posted_at': datetime.datetime.now().isoformat(),
            'body':      body,
            'replies':   [],
            'frozen':    False,
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
        if thread is None or not _can_access_board(ctx, thread.get('board_id', _DEFAULT_BOARD_ID)):
            await ctx.send('No such thread.')
            return CommandResult.fail('Unknown thread.', error='not_found')
        if thread.get('frozen'):
            await ctx.send('This bulletin is frozen -- no new responses.')
            return CommandResult.fail('Bulletin frozen.', error='frozen')

        anonymous = await resolve_anonymous(ctx, thread.get('board_id', _DEFAULT_BOARD_ID))
        if anonymous is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        title = await prompt_reply_title(ctx, thread.get('title', '(untitled)'))
        if title is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        privileged = _is_privileged(ctx.player)
        await ctx.send(board_store.build_quote_preamble(ctx, thread, privileged))
        await ctx.send('Enter your reply.')
        body = await run_editor(ctx, activity_id=f'board_reply:{id_str}',
                                 activity_label=f'replying to board thread #{id_str}')
        if body is None:
            await ctx.send('Cancelled.')
            return CommandResult.fail('Cancelled.', error='cancelled')

        reply = {
            'author':    ctx.player.name,
            'title':     title,
            'anonymous': anonymous,
            'posted_at': datetime.datetime.now().isoformat(),
            'body':      body,
        }
        replies = thread.setdefault('replies', [])
        replies.append(reply)
        reply_number = len(replies)
        board_store.save_board(threads)
        await ctx.send(f'Reply {reply_number} posted to "{thread.get("title", "(untitled)")}".')
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
        if thread is None or not _can_access_board(ctx, thread.get('board_id', _DEFAULT_BOARD_ID)):
            # In practice this never fires for a global ADMIN (already
            # let through above, and player_can_access() always passes
            # them) -- kept for consistency with the other three call
            # sites and as a backstop if a board-local admin path ever
            # reaches here without the global flag.
            await ctx.send('No such thread.')
            return CommandResult.fail('Unknown thread.', error='not_found')

        threads.remove(thread)
        board_store.save_board(threads)
        await ctx.send(f"Thread #{thread['id']} deleted.")
        log.info('ADMIN BOARD DELETE: %s deleted thread #%s', ctx.player.name, thread['id'])
        return CommandResult.ok('Deleted thread.')
