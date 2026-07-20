"""commands/board_edit.py — 'board #edit': admin-only, board-wide
threaded-board settings menu.

Split out of commands/board.py (Ryan's call, matching commands/
board_reply.py's own precedent) rather than nesting a commands/board/
subpackage -- commands/ has ~60 files and no subdirectories anywhere
in this codebase even for larger multi-file features (bar/, shoppe/),
so flat files stay the convention regardless of how many board_*.py
modules there end up being.

Currently one setting: the anonymous-posting default (board.py's
load_config()/save_config(), read by commands/board.py's own
resolve_anonymous(), shared with commands/board_reply.py's reply flow).
Ask/Yes/No, board-wide -- not a per-player preference like
command_settings.board.last_date is, since an admin is choosing site
policy here, not their own reading habits.
"""
from __future__ import annotations

import logging

import board as board_store
from commands.base_command import CommandResult
from flags import PlayerFlags

log = logging.getLogger(__name__)

_ANON_MODE_LABELS = {'ask': 'Ask', 'yes': 'Yes', 'no': 'No'}
_ANON_MODE_CHOICES = {'a': 'ask', 'y': 'yes', 'n': 'no'}


async def edit_board_settings(ctx) -> CommandResult:
    """The 'board #edit' menu itself -- loops showing current settings
    until the admin presses Enter to save and exit."""
    if not ctx.player.query_flag(PlayerFlags.ADMIN):
        await ctx.send('You lack the authority to do that.')
        return CommandResult.fail('Permission denied.', error='permission_denied')

    config = board_store.load_config()
    while True:
        mode_label = _ANON_MODE_LABELS.get(config.get('anonymous_mode', 'ask'), 'Ask')
        lines = [
            '', '|yellow|Board Settings|reset|', '',
            f'  A  Anonymous posting default ....... {mode_label}',
            '',
        ]
        raw = await ctx.prompt(
            f'Change which (or {ctx.player.return_key} to save and exit)',
            preamble_lines=lines,
        )
        if raw is None or not raw.strip():
            board_store.save_config(config)
            await ctx.send('Board settings saved.')
            log.info('ADMIN BOARD EDIT: %s saved board settings %r', ctx.player.name, config)
            return CommandResult.ok('Saved board settings.')

        choice = raw.strip().lower()
        if choice == 'a':
            await _edit_anonymous_mode(ctx, config)
        else:
            await ctx.send(f"Unrecognized choice '{choice}'.")


async def _edit_anonymous_mode(ctx, config: dict) -> None:
    raw = await ctx.prompt('[A]sk / [Y]es / [N]o')
    choice = (raw or '').strip().lower()[:1]
    new_mode = _ANON_MODE_CHOICES.get(choice)
    if new_mode is None:
        await ctx.send(f"Unrecognized choice '{raw}'. Use A, Y, or N.")
        return
    config['anonymous_mode'] = new_mode
    await ctx.send(f'Anonymous posting default: {_ANON_MODE_LABELS[new_mode]}.')
