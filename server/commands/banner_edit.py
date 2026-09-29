"""commands/banner_edit.py — 'banner': admin-only PETSCII banner/screen
editor, streaming a 40x24 character+color canvas (row 24 of the physical
screen is reserved on the client for a status line) down to a real
Commodore client and reading the edited canvas back.

Continues TODO.md's 7/23/26 "Online PETSCII editor" entry -- see
petscii_editor/__init__.py's docstring for the overall design (canvas
model, wire format, on-disk `[raw_petscii]`/`[tokenized]` file tagging).
This command is the integration point: petscii_editor itself has no
dispatcher hook of its own, matching how commands/play.py (not
sid_engine) owns the SID-streaming integration.

Only PETSCIINetworkContext (real Commodore hardware) can use this --
there's no local rendering for JSON/web clients, same guard commands/
play.py uses for SID streaming.

Phase 1 (Ryan's call): single-editor only, no live multi-viewer sync --
one admin opens a canvas, edits it locally on the C64, and uploads the
finished result when done. Live broadcast to other connected viewers is
an explicit later phase.
"""
from __future__ import annotations

import logging

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from petscii_editor import store as canvas_store
from petscii_editor.session import stream_canvas_edit

log = logging.getLogger(__name__)


class BannerEditCommand(Command):
    name  = 'banner'
    modes = {Mode.GAME}

    help = Help(
        summary  = 'Edit a PETSCII banner/screen on your Commodore 64.',
        category = HelpCategory.ADMINISTRATIVE,
        usage    = [
            ('banner edit <name>', 'Open (or create) a named banner in the visual editor.'),
            ('banner list',        'List saved banners.'),
        ],
        notes = [
            'Admin-only. Requires a real Commodore connection -- there\'s '
            'no local rendering for JSON/web clients.',
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        if not ctx.player.query_flag(PlayerFlags.ADMIN):
            await ctx.send('You lack the authority to do that.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        positional, _switches = self.parse_args(*args)
        if not positional:
            await ctx.send('Usage: banner edit <name> | banner list')
            return CommandResult.fail('No subcommand given.')

        sub, *rest = positional
        if sub == 'list':
            return await self._list(ctx)
        if sub == 'edit':
            if not rest:
                await ctx.send('Edit which banner? (banner edit <name>)')
                return CommandResult.fail('No banner name given.')
            return await self._edit(ctx, ' '.join(rest))

        await ctx.send(f'Unknown "banner" subcommand: {sub!r}. Try "banner list" or "banner edit <name>".')
        return CommandResult.fail('Unknown subcommand.', error='unknown_subcommand')

    async def _list(self, ctx) -> CommandResult:
        names = sorted(p.stem for p in canvas_store.CANVASES_DIR.glob('*.canvas')) \
            if canvas_store.CANVASES_DIR.is_dir() else []
        if not names:
            await ctx.send('No saved banners yet.')
            return CommandResult.ok('No saved banners.')
        await ctx.send(['|yellow|Saved banners|white|'] + [f'  {n}' for n in names])
        return CommandResult.ok(f'Listed {len(names)} banner(s).')

    async def _edit(self, ctx, name: str) -> CommandResult:
        path = canvas_store.path_for(name)
        return await stream_canvas_edit(
            ctx, path,
            opening_msg=f'|cyan|[[c64]]|white| opening banner editor for "{name}"...',
            timeout_msg='Banner editor timed out waiting for a save.',
            cancelled_msg=f'Banner edit for "{name}" cancelled.',
            saved_msg=f'Banner "{name}" saved.',
            log_label=f'banner {name!r}',
        )
