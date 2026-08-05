"""petscii_editor/canvas.py — the Canvas data model, the client<->server
wire format for downloading/uploading one, and rendering a Canvas into
this codebase's existing `{glyph}`/`|token|` text format for display.

Wire format (consumed by tada-client.asm's banner-editor receiver, mirrors
sid_engine/frames.py's convention and its reasoning for why a length
prefix beats an in-band end marker -- a canvas byte is just as free to
collide with any hand-picked sentinel as a SID register value is):

    stream := STREAM_START STREAM_CONFIRM len_lo len_hi body
    body   := chars (WIDTH*HEIGHT bytes) + colors (WIDTH*HEIGHT bytes)

STREAM_CONFIRM (0x42, 'B' for "banner") is deliberately a different byte
than sid_engine.frames.STREAM_CONFIRM (0x53, 'S') -- both streams share
the same STREAM_START (0x01) and ride the same connection, so the
client's handle_recv_byte scanner needs the second byte to tell which
kind of stream is starting, exactly as sid_engine.frames' own docstring
describes for why STREAM_CONFIRM exists at all.

This wire format is distinct from the on-disk `[raw_petscii]` file
format in store.py, even though both carry the same 2000-byte
chars+colors payload -- one is a framed stream for a live connection,
the other is a saved file with its own header tag.
"""
from __future__ import annotations

from dataclasses import dataclass, field

WIDTH  = 40
HEIGHT = 24  # not the full 40x25 physical screen -- row 24 is reserved
             # on the client for a persistent status line (current
             # color, cursor row/col; see petscii_editor.asm's
             # draw_status_line), so it's never part of the canvas
             # itself.
CELLS  = WIDTH * HEIGHT

STREAM_START   = 0x01
STREAM_CONFIRM = 0x42  # 'B' -- distinct from sid_engine.frames.STREAM_CONFIRM ('S')

# RUN/STOP-cancel marker: the client sends STREAM_START+STREAM_CANCEL+00+00
# (a fixed 4 bytes, the same length as a real STREAM_CONFIRM header) instead
# of a real upload when the player cancels out of the editor. Found live
# (Ryan): without this, edit_cancel sent nothing at all, so the server sat
# in banner_edit.py's readexactly(HEADER_LEN) for the full
# UPLOAD_TIMEOUT_SECONDS (15 minutes) before the client ever got its next
# prompt back -- the client-side screen looked hung the whole time even
# though RUN/STOP had dispatched correctly. Keeping this the same 4-byte
# length as a real header (rather than a shorter distinct marker) means
# banner_edit.py's existing single readexactly(HEADER_LEN) call always
# completes immediately either way; only the second byte differs.
STREAM_CANCEL  = 0x43  # 'C' -- distinct from STREAM_CONFIRM

# Default blank cell: PETSCII space, white -- matches a freshly-cleared
# C64 text screen.
BLANK_CHAR  = 0x20
BLANK_COLOR = 1  # white, see COLOR_NUMBER_TO_TOKEN below

# C64 color-RAM values 0-15, in hardware order -- matches the order
# PETSCII_CONTROL_CODES (formatting.py) lists its 16-color palette in.
COLOR_NUMBER_TO_TOKEN = [
    'black', 'white', 'red', 'cyan', 'purple', 'green', 'blue', 'yellow',
    'orange', 'brown', 'light_red', 'dark_gray', 'mid_gray', 'light_green',
    'light_blue', 'light_gray',
]


@dataclass
class Canvas:
    """A WIDTH x HEIGHT grid of (PETSCII char code, C64 color 0-15) cells,
    row-major. chars/colors default to a blank white screen."""
    chars:  bytearray = field(default_factory=lambda: bytearray([BLANK_CHAR] * CELLS))
    colors: bytearray = field(default_factory=lambda: bytearray([BLANK_COLOR] * CELLS))
    width:  int = WIDTH
    height: int = HEIGHT

    def __post_init__(self) -> None:
        if len(self.chars) != self.width * self.height:
            raise ValueError(f'chars must be {self.width * self.height} bytes, got {len(self.chars)}')
        if len(self.colors) != self.width * self.height:
            raise ValueError(f'colors must be {self.width * self.height} bytes, got {len(self.colors)}')


def encode_download(canvas: Canvas) -> bytes:
    """Encode *canvas* as a complete STREAM_START+STREAM_CONFIRM +
    length-prefixed byte stream, for sending to the C64 client via
    ctx.send_raw()."""
    body = bytes(canvas.chars) + bytes(canvas.colors)
    if len(body) > 0xffff:
        raise ValueError(f'encoded canvas too long ({len(body)} bytes) for a 16-bit length prefix')
    header = bytes([STREAM_START, STREAM_CONFIRM, len(body) & 0xff, (len(body) >> 8) & 0xff])
    return header + body


def decode_upload(data: bytes, width: int = WIDTH, height: int = HEIGHT) -> Canvas:
    """Decode a client-uploaded canvas stream (same wire format as
    encode_download()) back into a Canvas. Raises ValueError on a
    malformed stream (wrong markers, wrong body length)."""
    cells = width * height
    if len(data) < 4:
        raise ValueError('canvas stream too short for a header')
    start, confirm, len_lo, len_hi = data[0], data[1], data[2], data[3]
    if start != STREAM_START or confirm != STREAM_CONFIRM:
        raise ValueError(f'bad canvas stream markers: {start:#x} {confirm:#x}')
    body_len = len_lo | (len_hi << 8)
    body = data[4:4 + body_len]
    if len(body) != body_len:
        raise ValueError(f'canvas stream body truncated: expected {body_len} bytes, got {len(body)}')
    if body_len != cells * 2:
        raise ValueError(f'canvas stream body is {body_len} bytes, expected {cells * 2} for {width}x{height}')
    return Canvas(chars=bytearray(body[:cells]), colors=bytearray(body[cells:]), width=width, height=height)


def render_lines(canvas: Canvas) -> list[str]:
    """Render *canvas* into this codebase's `{$xx}`/`|token|` text
    format (formatting.py's petscii_encode()) -- one line per row, a
    `{$xx}` raw-byte literal per cell (guarantees an exact round trip
    regardless of what the byte value is, including ones that would
    otherwise collide with '{', '}', '|' in the text itself), with a
    `|colorname|` token spliced in only when the color actually changes
    from the previous cell (matches how hand-authored banner files
    already write color runs, not one token per character)."""
    lines = []
    for row in range(canvas.height):
        parts = []
        prev_color = None
        for col in range(canvas.width):
            i = row * canvas.width + col
            color = canvas.colors[i]
            if color != prev_color:
                parts.append(f'|{COLOR_NUMBER_TO_TOKEN[color]}|')
                prev_color = color
            parts.append(f'{{${canvas.chars[i]:02x}}}')
        lines.append(''.join(parts))
    return lines
