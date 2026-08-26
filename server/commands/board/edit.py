"""commands/board/edit.py — 'board #edit': admin-only SIG/board
structural editor.

Phase 2 of the sig-editor project (see the approved plan) grows this
from the old single anonymous-posting-mode toggle into the full editor:

  [S]IG management  — add/rename/delete a SIG, reorder SIGs
  [B]oard management — pick a board (across every SIG) then rename it,
                        move/share it between SIGs, reorder it within
                        its SIG, set its anonymous-posting mode, set its
                        access gate, manage its admin list, delete it
  [N]ew board        — create a board, choose which SIG(s) hold it

Same loop/submenu/mutate-in-memory/save-on-exit shape as the old
board_edit.py (see git history), generalized to two files instead of
one: board_sigs.json/board_meta.json are each loaded once on entry and
only written back to disk on the final top-level Enter -- nested
submenus mutate the same in-memory sigs_data/meta_data dicts and return
up a level on their own blank/Enter, never saving early. Every field
this editor can set (access gate, admins, anonymous_mode) already has
a place in board/meta.py's per-board dict from Phase 1 -- this phase
adds the UI to set it; nothing here enforces it yet (Phase 3).

Multi-select prompts (picking which SIG(s) a new/shared board lands in,
removing more than one admin at once) use text_editor.py's own
parse_multi_select() -- ed-style comma/range picks like '1,3-5' -- so
this editor's input style matches the text editor's rather than
inventing a second one-at-a-time-only picker (Ryan's call).
"""
from __future__ import annotations

import logging

import board as board_store
from base_classes import Guild
from commands.base_command import CommandResult
from flags import PlayerFlags

log = logging.getLogger(__name__)

_ANON_MODE_LABELS = {'ask': 'Ask', 'yes': 'Yes', 'no': 'No'}
_ANON_MODE_CHOICES = {'a': 'ask', 'y': 'yes', 'n': 'no'}

_ACCESS_LABELS = {
    'any':     'Anyone',
    'guild':   'Guild',
    'flag':    'Flag',
    'any_of':  'Guild or flag',
}


# ---------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------

def _sig_by_id(sigs_data: dict, sig_id: int) -> dict | None:
    return next((s for s in sigs_data.get('sigs', []) if s.get('id') == sig_id), None)


def _sigs_containing(sigs_data: dict, board_id: int) -> list[dict]:
    return [s for s in sigs_data.get('sigs', []) if board_id in s.get('board_ids', [])]


def _board_name(meta_data: dict, board_id: int) -> str:
    return board_store.meta.get_board(meta_data, board_id).get('name', f'Board {board_id}')


def _access_label(access: dict) -> str:
    kind = access.get('type', 'any')
    if kind == 'guild':
        return f"Guild: {access.get('value', '?')}"
    if kind == 'flag':
        return f"Flag: {access.get('value', '?')}"
    if kind == 'any_of':
        parts = [f"{v.get('type')}={v.get('value')}" for v in access.get('values', [])]
        return f"Any of: {', '.join(parts) or '(none)'}"
    return _ACCESS_LABELS.get(kind, kind)


def _board_name_taken(meta_data: dict, name: str, exclude_id: int | None = None) -> bool:
    target = name.strip().lower()
    for board in meta_data.get('boards', {}).values():
        if board.get('id') == exclude_id:
            continue
        if board.get('name', '').strip().lower() == target:
            return True
    return False


async def _prompt_multi_select(ctx, items: list[dict], *, noun: str, prompt: str) -> list[dict]:
    """Numbered listing of *items* + a parse_multi_select()-driven pick
    (e.g. '1,3-5'). [] on a blank/disconnected answer or an all-invalid
    one (reported and treated as "picked nothing" rather than looping
    forever -- this is a nested submenu step, not the whole editor).
    *prompt* should be short (see CLAUDE.md's ctx.prompt() length note)
    -- the range-syntax hint is appended to the preamble here, once,
    rather than every caller repeating it inline."""
    from text_editor import parse_multi_select

    if not items:
        await ctx.send(f'No {noun}s to choose from.')
        return []
    lines = [''] + [f'  {i}. {item.get("name", "(unnamed)")}' for i, item in enumerate(items, 1)]
    lines.append('(# or e.g. 1,3-5)')
    lines.append('')
    raw = await ctx.prompt(prompt, preamble_lines=lines)
    if raw is None or not raw.strip():
        return []
    picks = parse_multi_select(raw.strip(), len(items))
    if not picks:
        await ctx.send(f"'{raw.strip()}' didn't select any {noun}.")
        return []
    return [items[i - 1] for i in picks]


# ---------------------------------------------------------------------
# Top level
# ---------------------------------------------------------------------

async def edit_board_settings(ctx) -> CommandResult:
    """The 'board #edit' menu itself -- loops until the admin presses
    Enter at the top level, which is the only point either file actually
    gets written to disk."""
    if not ctx.player.query_flag(PlayerFlags.ADMIN):
        await ctx.send('You lack the authority to do that.')
        return CommandResult.fail('Permission denied.', error='permission_denied')

    sigs_data = board_store.sigs.load_sigs()
    meta_data = board_store.meta.load_meta()

    while True:
        lines = [
            '', '|yellow|Board & SIG Editor|reset|', '',
            f"  S  Manage SIGs ...................... ({len(sigs_data.get('sigs', []))})",
            f"  B  Manage Boards .................... ({len(meta_data.get('boards', {}))})",
            '  N  New board',
            f'({ctx.player.return_key} saves and exits)',
            '',
        ]
        raw = await ctx.prompt('Change which', preamble_lines=lines)
        if raw is None or not raw.strip():
            board_store.sigs.save_sigs(sigs_data)
            board_store.meta.save_meta(meta_data)
            await ctx.send('Board settings saved.')
            log.info('ADMIN BOARD EDIT: %s saved SIG/board settings', ctx.player.name)
            return CommandResult.ok('Saved board settings.')

        choice = raw.strip().lower()
        if choice == 's':
            await _manage_sigs(ctx, sigs_data, meta_data)
        elif choice == 'b':
            await _manage_boards(ctx, sigs_data, meta_data)
        elif choice == 'n':
            await _new_board(ctx, sigs_data, meta_data)
        else:
            await ctx.send(f"Unrecognized choice '{choice}'.")


# ---------------------------------------------------------------------
# [S] SIG management
# ---------------------------------------------------------------------

async def _manage_sigs(ctx, sigs_data: dict, meta_data: dict) -> None:
    while True:
        sig_list = sigs_data.get('sigs', [])
        lines = ['', '|yellow|SIGs|reset|', '']
        for i, sig in enumerate(sig_list, 1):
            lines.append(f"  {i}. {sig.get('name', '(unnamed)')} "
                          f"({len(sig.get('board_ids', []))} board(s))")
        lines.append(f'(# to edit, A to add, {ctx.player.return_key} to go back)')
        lines.append('')
        raw = await ctx.prompt('Which SIG', preamble_lines=lines)
        if raw is None or not raw.strip():
            return
        choice = raw.strip()
        if choice.lower() == 'a':
            await _add_sig(ctx, sigs_data)
        elif choice.isdigit() and 1 <= int(choice) <= len(sig_list):
            await _sig_detail(ctx, sigs_data, meta_data, sig_list[int(choice) - 1])
        else:
            await ctx.send(f"'{choice}' is not a valid choice.")


async def _add_sig(ctx, sigs_data: dict) -> None:
    raw = await ctx.prompt('New SIG name')
    name = (raw or '').strip()
    if not name:
        await ctx.send('Cancelled.')
        return
    new_sig = {'id': board_store.sigs.next_sig_id(sigs_data), 'name': name, 'board_ids': []}
    sigs_data.setdefault('sigs', []).append(new_sig)
    await ctx.send(f"SIG '{name}' added.")


async def _sig_detail(ctx, sigs_data: dict, meta_data: dict, sig: dict) -> None:
    while True:
        board_ids = sig.get('board_ids', [])
        lines = [
            '', f"|yellow|SIG: {sig.get('name', '(unnamed)')}|reset|", '',
        ]
        lines += _board_listing_lines(meta_data, board_ids) if board_ids else ['  (no boards)', '']
        lines += [
            '  R  Rename', '  X  Delete (only if it has no boards)',
            '  O  Reorder (move to a new position in the SIG list)',
            '  E<range>  Edit board(s) one at a time, e.g. E1, E2-4',
            '  L<range>  List a range of boards, e.g. L1-4',
            f'({ctx.player.return_key} to go back)', '',
        ]
        raw = await ctx.prompt('Change which', preamble_lines=lines)
        if raw is None or not raw.strip():
            return
        choice = raw.strip()
        lower = choice.lower()

        if lower == 'r':
            raw_name = await ctx.prompt('New name')
            new_name = (raw_name or '').strip()
            if new_name:
                sig['name'] = new_name
                await ctx.send(f"Renamed to '{new_name}'.")
            else:
                await ctx.send('Cancelled.')
        elif lower == 'x':
            if sig.get('board_ids'):
                await ctx.send('That SIG still has boards in it -- move or delete them first.')
            else:
                sigs_data['sigs'].remove(sig)
                await ctx.send(f"SIG '{sig.get('name', '(unnamed)')}' deleted.")
                return
        elif lower == 'o':
            await _move_to_position(ctx, sigs_data['sigs'], sig, name=sig.get('name', '(unnamed)'))
        elif lower.startswith('e'):
            await _edit_boards_in_range(ctx, sigs_data, meta_data, board_ids, choice[1:].strip())
        elif lower.startswith('l'):
            await _list_boards_range(ctx, meta_data, board_ids, choice[1:].strip())
        else:
            await ctx.send(f"Unrecognized choice '{choice}'.")


def _board_listing_lines(meta_data: dict, board_ids: list[int]) -> list[str]:
    return [f'  {i}. {_board_name(meta_data, bid)}' for i, bid in enumerate(board_ids, 1)] + ['']


async def _edit_boards_in_range(ctx, sigs_data: dict, meta_data: dict,
                                 board_ids: list[int], range_str: str) -> None:
    """'E<range>' -- mirrors text_editor.py's own '.e' dot-command: a
    blank range defaults to just the last board (DefaultLineRange.
    LAST_LINE, same as '.e' with no argument), and each selected board
    is opened one at a time via _board_detail(), not as a bulk-edit
    across all of them at once."""
    from text_editor import parse_multi_select

    if not board_ids:
        await ctx.send('This SIG has no boards.')
        return
    if not range_str:
        picks = [len(board_ids)]
    else:
        picks = parse_multi_select(range_str, len(board_ids))
        if not picks:
            await ctx.send(f"'{range_str}' didn't select any board.")
            return
    for i in picks:
        await _board_detail(ctx, sigs_data, meta_data, board_ids[i - 1])


async def _list_boards_range(ctx, meta_data: dict, board_ids: list[int], range_str: str) -> None:
    """'L<range>' -- mirrors text_editor.py's own '.l' dot-command: a
    blank range lists every board (DefaultLineRange.ALL_LINES)."""
    from text_editor import Buffer, DefaultLineRange, Line, process_line_range_string

    if not board_ids:
        await ctx.send('This SIG has no boards.')
        return
    buffer = Buffer(lines=[Line() for _ in board_ids])
    line_range = process_line_range_string(range_str, buffer, DefaultLineRange.ALL_LINES)
    indices = buffer.line_slice(line_range)
    lines = [''] + [f'  {i + 1}. {_board_name(meta_data, board_ids[i])}' for i in indices] + ['']
    await ctx.send(lines)


async def _move_to_position(ctx, items: list, item, *, name: str) -> None:
    """ImageBBS-style reorder (Ryan's call, over an up/down nudge):
    'Move <name> before which? (1-N)', N being *items*' own current
    length (item included) so the numbering matches what the caller's
    own numbered listing just showed. Inserting at position N (the last
    slot) means "after everything else", same as ed-style range clamping
    elsewhere in this game (see text_editor.py's process_line_range_string).
    *items* can hold anything (SIG dicts, or plain board-id ints for
    reordering within a SIG's board_ids) -- *name* is passed in rather
    than pulled off *item* since a plain int has no .get('name')."""
    raw = await ctx.prompt(
        f'Move {name} before which',
        preamble_lines=['', f'(1-{len(items)})', ''],
    )
    if raw is None or not raw.strip() or not raw.strip().isdigit():
        await ctx.send('Cancelled.')
        return
    target = int(raw.strip())
    if not (1 <= target <= len(items)):
        await ctx.send(f'Not a valid position (1-{len(items)}).')
        return
    items.remove(item)
    items.insert(min(target - 1, len(items)), item)
    await ctx.send(f'Moved {name}.')


# ---------------------------------------------------------------------
# [B] Board management
# ---------------------------------------------------------------------

async def _manage_boards(ctx, sigs_data: dict, meta_data: dict) -> None:
    while True:
        board_ids = sorted(int(k) for k in meta_data.get('boards', {}).keys())
        lines = ['', '|yellow|Boards|reset|', '']
        for i, board_id in enumerate(board_ids, 1):
            sig_names = ', '.join(s.get('name', '(unnamed)') for s in _sigs_containing(sigs_data, board_id))
            lines.append(f"  {i}. {_board_name(meta_data, board_id)}  (in: {sig_names or 'no SIG'})")
        lines.append(f'(# to edit, {ctx.player.return_key} to go back)')
        lines.append('')
        raw = await ctx.prompt('Which board', preamble_lines=lines)
        if raw is None or not raw.strip():
            return
        choice = raw.strip()
        if choice.isdigit() and 1 <= int(choice) <= len(board_ids):
            await _board_detail(ctx, sigs_data, meta_data, board_ids[int(choice) - 1])
        else:
            await ctx.send(f"'{choice}' is not a valid choice.")


async def _board_detail(ctx, sigs_data: dict, meta_data: dict, board_id: int) -> None:
    while True:
        board = board_store.meta.get_board(meta_data, board_id)
        containing = _sigs_containing(sigs_data, board_id)
        sig_names = ', '.join(s.get('name', '(unnamed)') for s in containing) or 'no SIG'
        lines = [
            '', f"|yellow|Board: {board.get('name', '(unnamed)')}|reset|", '',
            f'  In SIG(s): {sig_names}',
            f"  Anonymous posting: {_ANON_MODE_LABELS.get(board.get('anonymous_mode', 'ask'), 'Ask')}",
            f"  Access: {_access_label(board.get('access', {'type': 'any'}))}",
            f"  Admins: {', '.join(board.get('admins', [])) or '(none)'}",
            '',
            '  R  Rename', '  M  Move to another SIG', '  H  Share into another SIG',
            '  O  Reorder (move to a new position within its SIG)',
            '  A  Set anonymous-posting mode', '  G  Set access gate',
            '  P  Manage admins', '  X  Delete (only if it has no threads)',
            f'({ctx.player.return_key} to go back)', '',
        ]
        raw = await ctx.prompt('Change which', preamble_lines=lines)
        if raw is None or not raw.strip():
            return
        choice = raw.strip().lower()

        if choice == 'r':
            await _rename_board(ctx, meta_data, board_id)
        elif choice == 'm':
            await _move_board(ctx, sigs_data, meta_data, board_id)
        elif choice == 'h':
            await _share_board(ctx, sigs_data, meta_data, board_id)
        elif choice == 'o':
            await _reorder_board(ctx, sigs_data, meta_data, board_id)
        elif choice == 'a':
            await _edit_anonymous_mode(ctx, meta_data, board_id)
        elif choice == 'g':
            await _edit_access_gate(ctx, meta_data, board_id)
        elif choice == 'p':
            await _manage_admins(ctx, meta_data, board_id)
        elif choice == 'x':
            if await _delete_board(ctx, sigs_data, meta_data, board_id):
                return
        else:
            await ctx.send(f"Unrecognized choice '{choice}'.")


async def _rename_board(ctx, meta_data: dict, board_id: int) -> None:
    raw = await ctx.prompt('New name')
    new_name = (raw or '').strip()
    if not new_name:
        await ctx.send('Cancelled.')
        return
    if _board_name_taken(meta_data, new_name, exclude_id=board_id):
        await ctx.send(f"A board named '{new_name}' already exists.")
        return
    board = board_store.meta.get_board(meta_data, board_id)
    board['name'] = new_name
    board_store.meta.set_board(meta_data, board_id, board)
    await ctx.send(f"Renamed to '{new_name}'.")


async def _move_board(ctx, sigs_data: dict, meta_data: dict, board_id: int) -> None:
    containing = _sigs_containing(sigs_data, board_id)
    if not containing:
        await ctx.send("This board isn't in any SIG -- use Share instead.")
        return
    if len(containing) == 1:
        source = containing[0]
    else:
        picks = await _prompt_multi_select(
            ctx, containing, noun='SIG', prompt='Remove from which SIG')
        if len(picks) != 1:
            await ctx.send('Pick exactly one SIG to move from.')
            return
        source = picks[0]

    targets = [s for s in sigs_data.get('sigs', []) if s is not source]
    picks = await _prompt_multi_select(ctx, targets, noun='SIG', prompt='Move to which SIG')
    if len(picks) != 1:
        await ctx.send('Pick exactly one destination SIG.')
        return
    target = picks[0]

    source['board_ids'].remove(board_id)
    if board_id not in target.setdefault('board_ids', []):
        target['board_ids'].append(board_id)
    await ctx.send(f"Moved '{_board_name(meta_data, board_id)}' to '{target.get('name')}'.")


async def _share_board(ctx, sigs_data: dict, meta_data: dict, board_id: int) -> None:
    already_in = {s.get('id') for s in _sigs_containing(sigs_data, board_id)}
    targets = [s for s in sigs_data.get('sigs', []) if s.get('id') not in already_in]
    picks = await _prompt_multi_select(ctx, targets, noun='SIG', prompt='Share into which SIG(s)')
    if not picks:
        return
    for sig in picks:
        sig.setdefault('board_ids', []).append(board_id)
    names = ', '.join(s.get('name', '(unnamed)') for s in picks)
    await ctx.send(f"Shared '{_board_name(meta_data, board_id)}' into: {names}.")


async def _reorder_board(ctx, sigs_data: dict, meta_data: dict, board_id: int) -> None:
    containing = _sigs_containing(sigs_data, board_id)
    if not containing:
        await ctx.send("This board isn't in any SIG.")
        return
    if len(containing) == 1:
        sig = containing[0]
    else:
        picks = await _prompt_multi_select(
            ctx, containing, noun='SIG', prompt='Reorder within which SIG')
        if len(picks) != 1:
            await ctx.send('Pick exactly one SIG.')
            return
        sig = picks[0]
    await _move_to_position(ctx, sig['board_ids'], board_id, name=_board_name(meta_data, board_id))


async def _edit_anonymous_mode(ctx, meta_data: dict, board_id: int) -> None:
    raw = await ctx.prompt(
        'Anonymous posting', preamble_lines=['', '[A]sk / [Y]es / [N]o', ''])
    choice = (raw or '').strip().lower()[:1]
    new_mode = _ANON_MODE_CHOICES.get(choice)
    if new_mode is None:
        await ctx.send(f"Unrecognized choice '{raw}'. Use A, Y, or N.")
        return
    board = board_store.meta.get_board(meta_data, board_id)
    board['anonymous_mode'] = new_mode
    board_store.meta.set_board(meta_data, board_id, board)
    await ctx.send(f'Anonymous posting default: {_ANON_MODE_LABELS[new_mode]}.')


async def _edit_access_gate(ctx, meta_data: dict, board_id: int) -> None:
    raw = await ctx.prompt(
        'Access gate',
        preamble_lines=['', '[A]nyone / [G]uild / [F]lag / [O]r (guild or flag)', ''],
    )
    choice = (raw or '').strip().lower()[:1]

    if choice == 'a':
        access = {'type': 'any'}
    elif choice == 'g':
        access = await _pick_guild_gate(ctx)
    elif choice == 'f':
        access = await _pick_flag_gate(ctx)
    elif choice == 'o':
        guild_gate = await _pick_guild_gate(ctx)
        flag_gate = await _pick_flag_gate(ctx)
        if guild_gate is None or flag_gate is None:
            access = None
        else:
            access = {'type': 'any_of', 'values': [guild_gate, flag_gate]}
    else:
        await ctx.send(f"Unrecognized choice '{raw}'. Use A, G, F, or O.")
        return

    if access is None:
        await ctx.send('Cancelled.')
        return
    board = board_store.meta.get_board(meta_data, board_id)
    board['access'] = access
    board_store.meta.set_board(meta_data, board_id, board)
    await ctx.send(f'Access gate: {_access_label(access)}.')


async def _pick_guild_gate(ctx) -> dict | None:
    guilds = list(Guild)
    lines = [''] + [f'  {i}. {g.value}' for i, g in enumerate(guilds, 1)]
    lines.append('')
    raw = await ctx.prompt('Which guild', preamble_lines=lines)
    if raw is None or not raw.strip() or not raw.strip().isdigit():
        return None
    idx = int(raw.strip())
    if not (1 <= idx <= len(guilds)):
        await ctx.send('Not a valid guild number.')
        return None
    return {'type': 'guild', 'value': guilds[idx - 1].value}


# PlayerFlags has ~30 entries total, most of which are transient world/
# health/item state (HUNGER, MOUNTED, WRAITH_KING_ALIVE, ...) that make
# no sense as a board access gate. This curated subset is the
# role/permission-like ones actually worth gating on -- Ryan's call,
# a numbered pick (matching _pick_guild_gate()'s shape) rather than
# requiring an admin to type/remember an exact flag name.
_GATE_FLAG_CHOICES = (
    PlayerFlags.ADMIN,
    PlayerFlags.DUNGEON_MASTER,
    PlayerFlags.ARCHITECT,
    PlayerFlags.GUILD_MEMBER,
    PlayerFlags.ORATOR,
)


async def _pick_flag_gate(ctx) -> dict | None:
    lines = [''] + [f'  {i}. {f.value}' for i, f in enumerate(_GATE_FLAG_CHOICES, 1)]
    lines.append('')
    raw = await ctx.prompt('Which flag', preamble_lines=lines)
    if raw is None or not raw.strip() or not raw.strip().isdigit():
        return None
    idx = int(raw.strip())
    if not (1 <= idx <= len(_GATE_FLAG_CHOICES)):
        await ctx.send('Not a valid flag number.')
        return None
    return {'type': 'flag', 'value': _GATE_FLAG_CHOICES[idx - 1].name}


async def _manage_admins(ctx, meta_data: dict, board_id: int) -> None:
    while True:
        board = board_store.meta.get_board(meta_data, board_id)
        admins = board.get('admins', [])
        lines = ['', f"|yellow|Admins for {board.get('name', '(unnamed)')}|reset|", '']
        lines += [f'  {i}. {name}' for i, name in enumerate(admins, 1)] or ['  (none)']
        lines.append(f'(A to add, R<range> to remove e.g. R1,3, {ctx.player.return_key} back)')
        lines.append('')
        raw = await ctx.prompt('Change which', preamble_lines=lines)
        if raw is None or not raw.strip():
            return
        choice = raw.strip()

        if choice.lower() == 'a':
            raw_names = await ctx.prompt('Name(s) to add (comma separated)')
            new_names = [n.strip() for n in (raw_names or '').split(',') if n.strip()]
            added = [n for n in new_names if n not in admins]
            admins.extend(added)
            board['admins'] = admins
            board_store.meta.set_board(meta_data, board_id, board)
            await ctx.send(f"Added: {', '.join(added) or '(nothing new)'}.")
        elif choice[:1].lower() == 'r':
            from text_editor import parse_multi_select

            picks = parse_multi_select(choice[1:], len(admins))
            if not picks:
                await ctx.send(f"'{choice}' didn't select any admin.")
                continue
            removed = [admins[i - 1] for i in picks]
            board['admins'] = [n for i, n in enumerate(admins, 1) if i not in picks]
            board_store.meta.set_board(meta_data, board_id, board)
            await ctx.send(f"Removed: {', '.join(removed)}.")
        else:
            await ctx.send(f"Unrecognized choice '{choice}'.")


async def _delete_board(ctx, sigs_data: dict, meta_data: dict, board_id: int) -> bool:
    """True if deletion actually happened (caller should stop showing
    this board's now-gone detail menu)."""
    threads = [t for t in board_store.load_board() if t.get('board_id') == board_id]
    if threads:
        await ctx.send(f'That board still has {len(threads)} thread(s) on it -- delete those first.')
        return False
    name = _board_name(meta_data, board_id)
    meta_data.get('boards', {}).pop(str(board_id), None)
    for sig in sigs_data.get('sigs', []):
        if board_id in sig.get('board_ids', []):
            sig['board_ids'].remove(board_id)
    await ctx.send(f"Board '{name}' deleted.")
    return True


# ---------------------------------------------------------------------
# [N] New board
# ---------------------------------------------------------------------

async def _new_board(ctx, sigs_data: dict, meta_data: dict) -> None:
    sig_list = sigs_data.get('sigs', [])
    if not sig_list:
        await ctx.send('Create a SIG first ([S]IG management -> A to add).')
        return

    raw_name = await ctx.prompt('New board name')
    name = (raw_name or '').strip()
    if not name:
        await ctx.send('Cancelled.')
        return
    if _board_name_taken(meta_data, name):
        await ctx.send(f"A board named '{name}' already exists.")
        return

    picks = await _prompt_multi_select(ctx, sig_list, noun='SIG', prompt='Add to which SIG(s)')
    if not picks:
        await ctx.send('Cancelled -- a new board needs at least one SIG.')
        return

    board_id = board_store.meta.next_board_id(meta_data)
    board_store.meta.set_board(meta_data, board_id, {
        'id': board_id,
        'name': name,
        'anonymous_mode': 'ask',
        'access': {'type': 'any'},
        'admins': [],
    })
    for sig in picks:
        sig.setdefault('board_ids', []).append(board_id)
    sig_names = ', '.join(s.get('name', '(unnamed)') for s in picks)
    await ctx.send(f"Board '{name}' created in: {sig_names}.")
