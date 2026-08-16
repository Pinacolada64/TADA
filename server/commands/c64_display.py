"""commands/c64_display.py — native C64 display-settings popup: border/
background screen color (VIC-II 53280/53281) and cursor blink speed,
edited in a real popup window on the Commodore's own screen rather than
scrolling text like the rest of PREFS.

Reached via PREFS -> Terminal Settings -> 'V' (Video Settings (C64)),
PETSCII connections only (commands/prefs.py's _terminal_menu). Mirrors
commands/banner_edit.py's round trip: send a framed trigger (current
values + a distinct STREAM_CONFIRM byte so tada-client.asm's receive
dispatcher knows to load the config_menu.asm overlay module, same as
CANVAS_STREAM_CONFIRM triggers load_petscii_editor), then block for a
framed reply -- either new values (saved) or a cancel marker.

Wire format (must match tada-client.asm/config_menu.asm exactly):

    stream := STREAM_START STREAM_CONFIRM_OR_CANCEL len_lo len_hi body
    body   := border_color, bg_color, blink_speed  (3 raw bytes, only
              present when len != 0 -- a cancel reply has len 0)

STREAM_START (0x01) is shared with every other framed stream on this
connection (petscii_editor/canvas.py, sid_engine/frames.py) --
DISPLAY_STREAM_CONFIRM (0x44, 'D' for "display") is what tells the
client's handle_recv_byte scanner which kind of stream is starting, same
role as CANVAS_STREAM_CONFIRM ('B')/SID_STREAM_CONFIRM ('S').
DISPLAY_STREAM_CANCEL (0x58, 'X') is unrelated to petscii_editor/
canvas.py's own STREAM_CANCEL byte -- these are different streams
entirely, no need for the values to match.

border_color/bg_color are raw VIC-II color numbers (0-15), the same
values POKE 53280/53281 expect -- terminal.ColorName's first 16 members
are declared in that exact hardware order, so
list(ColorName)[raw] / list(ColorName).index(name) convert directly with
no separate lookup table.

blink_speed is 1-5 (fast/normal/slow/very slow/solid) -- BLINK_SPEED_MASKS
documents the jiffy-clock bitmask each maps to client-side
(config_menu.asm/tada-client.asm's update_cursor); the server never
needs the mask itself, just the 1-5 index round-tripped to storage.
"""
from __future__ import annotations

import asyncio
import logging

from network_context import PETSCIINetworkContext
from terminal import ColorName

log = logging.getLogger(__name__)

STREAM_START           = 0x01
DISPLAY_STREAM_CONFIRM = 0x44  # 'D'
DISPLAY_STREAM_CANCEL  = 0x58  # 'X'
HEADER_LEN = 4  # STREAM_START, CONFIRM/CANCEL, len_lo, len_hi
BODY_LEN   = 3  # border_color, bg_color, blink_speed

# Documented here for cross-reference with config_menu.asm's own copy of
# this table -- 2-3Hz was tada-client.asm's original hardcoded blink
# rate (bit 4 of $a2, the jiffy clock's fastest-changing byte) before
# speed became configurable; the other three real speeds are new presets
# around it. 5 (mask 0x00) is a reserved sentinel meaning "solid, no
# blink at all" -- Ryan's ask, since some screen-reader/accessibility
# software (e.g. Gadget) doesn't get along with a blinking cursor.
BLINK_SPEED_MASKS = {1: 0x08, 2: 0x10, 3: 0x20, 4: 0x40, 5: 0x00}
DEFAULT_BLINK_SPEED = 2

UPLOAD_TIMEOUT_SECONDS = 5 * 60


def _encode_trigger(border_color: int, bg_color: int, blink_speed: int) -> bytes:
    body = bytes([border_color, bg_color, blink_speed])
    return bytes([STREAM_START, DISPLAY_STREAM_CONFIRM, len(body), 0]) + body


async def pick_c64_display(ctx) -> None:
    """Open the native C64 display-settings popup and apply whatever the
    player saves. No-op (with an explanatory message) on anything that
    isn't a real Commodore connection."""
    if not isinstance(ctx, PETSCIINetworkContext):
        await ctx.send("Video Settings needs a real Commodore connection.")
        return

    cs      = ctx.player.client_settings
    colors  = cs.colors
    border  = list(ColorName).index(colors.border_color)
    bg      = list(ColorName).index(colors.background_color)
    blink   = cs.cursor_blink_speed

    await ctx.send_raw(_encode_trigger(border, bg, blink))

    try:
        header = await asyncio.wait_for(ctx.reader.readexactly(HEADER_LEN), UPLOAD_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await ctx.send('Video Settings timed out waiting for a reply.')
        return
    except (asyncio.IncompleteReadError, ConnectionError):
        log.warning('c64_display: connection dropped mid-reply for %s', ctx.player.name)
        return

    if header[1] == DISPLAY_STREAM_CANCEL:
        await ctx.send('Video settings unchanged.')
        return

    if header[0] != STREAM_START or header[1] != DISPLAY_STREAM_CONFIRM:
        log.warning('c64_display: unexpected reply header %r from %s', header, ctx.player.name)
        await ctx.send('Video Settings reply was garbled -- settings unchanged.')
        return

    body_len = header[2] | (header[3] << 8)
    if body_len != BODY_LEN:
        log.warning('c64_display: unexpected body length %d from %s', body_len, ctx.player.name)
        await ctx.send('Video Settings reply was garbled -- settings unchanged.')
        return

    try:
        body = await asyncio.wait_for(ctx.reader.readexactly(BODY_LEN), UPLOAD_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        await ctx.send('Video Settings timed out waiting for a reply.')
        return
    except (asyncio.IncompleteReadError, ConnectionError):
        log.warning('c64_display: connection dropped mid-reply for %s', ctx.player.name)
        return

    new_border, new_bg, new_blink = body[0], body[1], body[2]
    palette = list(ColorName)
    if not (0 <= new_border < 16 and 0 <= new_bg < 16 and new_blink in BLINK_SPEED_MASKS):
        log.warning('c64_display: out-of-range reply %r from %s', body, ctx.player.name)
        await ctx.send('Video Settings reply was out of range -- settings unchanged.')
        return

    colors.border_color     = palette[new_border]
    colors.background_color = palette[new_bg]
    cs.cursor_blink_speed   = new_blink
    ctx.player.unsaved_changes = True
    await ctx.send(
        f'Video settings saved: {colors.border_color.value} border, '
        f'{colors.background_color.value} background, blink speed {new_blink}.'
    )
