"""petscii_editor/session.py — the streaming-edit round trip shared by
every in-game integration point that opens the visual canvas editor on a
real Commodore: download the current canvas, wait for the client to
upload its edit (or cancel/time out), save it.

Pulled out of commands/banner_edit.py (the original -- and until now,
only -- integration point) when the SIG/board intro-screen editor
(commands/board/edit.py's `[I]ntro` option) needed the exact same round
trip against a different on-disk path. petscii_editor itself still has
no dispatcher hook of its own (see petscii_editor/__init__.py) -- this
is plumbing for command modules to call, not a command.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from commands.base_command import CommandResult
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


async def stream_canvas_edit(ctx, path: Path, *,
                              opening_msg: str,
                              timeout_msg: str,
                              cancelled_msg: str,
                              saved_msg: str,
                              log_label: str) -> CommandResult:
    """Open the visual canvas editor on *ctx*'s real Commodore connection
    for the canvas saved at *path* (created fresh if *path* doesn't hold
    one yet), and save whatever comes back. The four *_msg strings are
    sent verbatim at their respective points, so each call site (banner
    edit, SIG/board intro-screen edit) keeps its own wording ("Banner
    ... saved." vs "Intro screen for ... saved.") rather than this
    sharing one generic template. *log_label* identifies the subject in
    the admin-action log line only.
    """
    if not isinstance(ctx, PETSCIINetworkContext):
        await ctx.send("Your connection can't run the visual banner editor -- it needs a real Commodore screen.")
        return CommandResult.fail('No PETSCII display available.', error='no_petscii_display')

    loaded = canvas_store.load(path)
    cv = loaded if isinstance(loaded, Canvas) else Canvas()

    await ctx.send(opening_msg)
    await ctx.send_raw(canvas_wire.encode_download(cv))

    try:
        header = await asyncio.wait_for(ctx.reader.readexactly(HEADER_LEN), UPLOAD_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await ctx.send(timeout_msg)
        return CommandResult.fail('Upload timed out.', error='upload_timeout')
    except (asyncio.IncompleteReadError, ConnectionError):
        log.warning('canvas edit %s: connection dropped mid-upload for %s', log_label, ctx.player.name)
        return CommandResult.fail('Connection lost during upload.', error='connection_lost')

    if header[1] == canvas_wire.STREAM_CANCEL:
        await ctx.send(cancelled_msg)
        return CommandResult.ok('Cancelled.')

    try:
        body_len = header[2] | (header[3] << 8)
        body = await asyncio.wait_for(ctx.reader.readexactly(body_len), UPLOAD_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await ctx.send(timeout_msg)
        return CommandResult.fail('Upload timed out.', error='upload_timeout')
    except (asyncio.IncompleteReadError, ConnectionError):
        log.warning('canvas edit %s: connection dropped mid-upload for %s', log_label, ctx.player.name)
        return CommandResult.fail('Connection lost during upload.', error='connection_lost')

    try:
        uploaded = canvas_wire.decode_upload(header + body)
    except ValueError as exc:
        await ctx.send(f'Upload rejected: {exc}')
        return CommandResult.fail(str(exc), error='bad_upload')

    canvas_store.save(path, uploaded)
    log.info('ADMIN CANVAS EDIT: %s saved %s', ctx.player.name, log_label)
    await ctx.send(saved_msg)
    return CommandResult.ok(f'Saved {log_label}.')
