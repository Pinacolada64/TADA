"""commands/banner_edit.py — 'banner': admin-only PETSCII banner/screen
editor, streaming a 40x25 character+color canvas down to a real
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

import asyncio
import logging

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import PETSCIINetworkContext
from petscii_editor import canvas as canvas_wire
from petscii_editor import store as canvas_store
from petscii_editor.canvas import Canvas

log = logging.getLogger(__name__)

# How long to wait for the client to upload its edited canvas back.
# There's no clean cancel signal from the client yet (see this feature's
# plan notes) -- an admin who just walks away from an open editor
# shouldn't hang the connection forever, so this is a generous but
# finite backstop rather than a real abort mechanism. Revisit if a
# RUN/STOP-triggered cancel byte gets added client-side.
UPLOAD_TIMEOUT_SECONDS = 15 * 60

HEADER_LEN = 4  # STREAM_START, STREAM_CONFIRM, len_lo, len_hi


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
        if not isinstance(ctx, PETSCIINetworkContext):
            await ctx.send("Your connection can't run the visual banner editor -- it needs a real Commodore screen.")
            return CommandResult.fail('No PETSCII display available.', error='no_petscii_display')

        path = canvas_store.path_for(name)
        loaded = canvas_store.load(path)
        cv = loaded if isinstance(loaded, Canvas) else Canvas()

        await ctx.send(f'|cyan|[[c64]]|white| opening banner editor for "{name}"...')
        await ctx.send_raw(canvas_wire.encode_download(cv))

        try:
            header = await asyncio.wait_for(ctx.reader.readexactly(HEADER_LEN), UPLOAD_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await ctx.send('Banner editor timed out waiting for a save.')
            return CommandResult.fail('Upload timed out.', error='upload_timeout')
        except (asyncio.IncompleteReadError, ConnectionError):
            log.warning('banner edit %r: connection dropped mid-upload for %s', name, ctx.player.name)
            return CommandResult.fail('Connection lost during upload.', error='connection_lost')

        if header[1] == canvas_wire.STREAM_CANCEL:
            await ctx.send(f'Banner edit for "{name}" cancelled.')
            return CommandResult.ok('Cancelled.')

        try:
            body_len = header[2] | (header[3] << 8)
            body = await asyncio.wait_for(ctx.reader.readexactly(body_len), UPLOAD_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await ctx.send('Banner editor timed out waiting for a save.')
            return CommandResult.fail('Upload timed out.', error='upload_timeout')
        except (asyncio.IncompleteReadError, ConnectionError):
            log.warning('banner edit %r: connection dropped mid-upload for %s', name, ctx.player.name)
            return CommandResult.fail('Connection lost during upload.', error='connection_lost')

        try:
            uploaded = canvas_wire.decode_upload(header + body)
        except ValueError as exc:
            await ctx.send(f'Banner upload rejected: {exc}')
            return CommandResult.fail(str(exc), error='bad_upload')

        canvas_store.save(path, uploaded)
        log.info('ADMIN BANNER EDIT: %s saved banner %r', ctx.player.name, name)
        await ctx.send(f'Banner "{name}" saved.')
        return CommandResult.ok(f'Saved banner {name!r}.')
