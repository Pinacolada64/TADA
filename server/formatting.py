#!/bin/env python3
"""
formatting.py

Pure text formatting functions for TADA output.
No I/O, no ctx, no network — just strings in, strings out.
ctx.send() calls these before writing to the wire or terminal.

Design goals:
  - All functions are pure (no side effects, no global state)
  - All functions accept a ClientSettings object for terminal parameters
  - Color/graphics handling is pluggable via a ColorCodec protocol
  - Works identically for ANSI terminals and PETSCII/Commodore

Typical call chain (ANSI):
    ctx.send("Hello [world]!")
        -> format_lines(["Hello [world]!"], ctx.player.client_settings)
            -> highlight_brackets()   # [world] -> ANSI color codes
            -> wrap_text()            # word-wrap to screen width
        -> write to wire / print

Typical call chain (PETSCII):
    ctx.send("Hello |red|world|reset|!")
        -> format_lines(...)          # wrap, highlight brackets
        -> petscii_encode(...)        # encode text + splice in raw control bytes
        -> raw bytes to Commodore client
"""
import logging
from _codecs import ascii_encode

try:
    from colorama import Fore, Style

    _COLORAMA_AVAILABLE = True
except ImportError:
    _COLORAMA_AVAILABLE = False
    logging.warning('colorama not available; ANSI color output will be plain text.')

try:
    import cbmcodecs2 as _cbmcodecs2  # noqa: F401 — registers the codec
    _CBMCODECS2_AVAILABLE = True
except ImportError:
    _CBMCODECS2_AVAILABLE = False
    logging.warning('cbmcodecs2 not available; PETSCII output will be ASCII only.')
import re
import textwrap
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# ClientSettings protocol
# Defines the minimum interface formatting.py needs from a settings object.
# Both terminal.ClientSettings and terminal_context.TerminalSettings satisfy it.
# ---------------------------------------------------------------------------

@runtime_checkable
class HasClientSettings(Protocol):
    screen_columns: int
    screen_rows: int


# ---------------------------------------------------------------------------
# ColorCodec protocol
# A pluggable translation layer for color/graphics codes.
# Implement this for ANSI, PETSCII, plain text, etc.
# ---------------------------------------------------------------------------

@runtime_checkable
class ColorCodec(Protocol):
    """
    Translates abstract color/style tokens into terminal-specific strings.
    Implement one per translation target (ANSI, PETSCII, plain, etc.)
    """

    def highlight_on(self) -> str: ...

    def highlight_off(self) -> str: ...

    def reset(self) -> str: ...


@dataclass
class ANSICodec:
    """ANSI color codes via colorama."""
    highlight_color: str = ''  # set at runtime from player prefs

    def __post_init__(self):
        try:
            from colorama import Fore, Style
            if not self.highlight_color:
                self.highlight_color = Fore.RED
            self._reset = Fore.RESET
        except ImportError:
            self.highlight_color = ''
            self._reset = ''

    def highlight_on(self) -> str:
        return self.highlight_color

    def highlight_off(self) -> str:
        return self._reset

    def reset(self) -> str:
        return self._reset


@dataclass
class PlainCodec:
    """No color codes — plain ASCII output."""

    def highlight_on(self) -> str: return ''

    def highlight_off(self) -> str: return ''

    def reset(self) -> str: return ''


@dataclass
class PETSCIICodec:
    """
    Commodore PETSCII color/reverse codes.
    Reverse video is used for [bracket] highlighting since it works on
    all Commodore models without needing a specific color.
    Full 16-color palette is available via |token| substitution in
    petscii_encode() — see PETSCII_CONTROL_CODES below.
    """

    def highlight_on(self) -> str: return '|reverse_on|'

    def highlight_off(self) -> str: return '|reverse_off|'

    def reset(self) -> str: return '|reset|'


# ---------------------------------------------------------------------------
# PETSCII control code table
# ---------------------------------------------------------------------------

# Maps |token| names to raw Commodore control code byte values.
# These are intentionally kept out of cbmcodecs2 encoding — they are
# spliced into the output as raw bytes after text encoding.
# Reference: https://sta.c64.org/cbm64petscii.html

PETSCII_CONTROL_CODES: dict[str, int] = {
    # 16-color palette (CBM color codes)
    'black': 144,
    'white': 5,
    'red': 28,
    'cyan': 159,
    'purple': 156,
    'green': 30,
    'blue': 31,
    'yellow': 158,
    'orange': 129,
    'brown': 149,
    'light_red': 150,
    'dark_gray': 151,
    'mid_gray': 152,
    'light_green': 153,
    'light_blue': 154,
    'light_gray': 155,

    # Screen control
    'reverse_on': 18,
    'reverse_off': 146,
    'clear': 147,  # clear screen + home
    'home': 19,  # cursor home (no clear)
    'reset': 146,  # alias for reverse_off

    # Cursor movement
    'cursor_up': 145,
    'cursor_down': 17,
    'cursor_left': 157,
    'cursor_right': 29,

    # Case switching
    'lowercase': 14,  # switch to upper/lower charset
    'uppercase': 142,  # switch to upper/graphics charset

    # Insert/delete
    'insert': 148,
    'delete': 20,
}

# Reverse lookup: raw byte value -> token name (for display/debugging)
PETSCII_CODE_NAMES: dict[int, str] = {
    v: k for k, v in PETSCII_CONTROL_CODES.items()
}

_TOKEN_RE = re.compile(r'\|([a-z_]+)\|')


def _encode_petscii_segment(text: str, codec_name: str) -> bytes:
    """Encode a plain text segment, mapping '_' → PETSCII $64 (underline glyph)."""
    if '_' not in text:
        return text.encode(codec_name, errors='replace')
    parts = text.split('_')
    buf = bytearray()
    for i, part in enumerate(parts):
        buf.extend(part.encode(codec_name, errors='replace'))
        if i < len(parts) - 1:
            buf.append(0x64)
    return bytes(buf)


def petscii_encode(text: str,
                   codec_name: str = 'petscii_c64en_lc') -> bytes:
    """
    Encode a string for transmission to a Commodore client.

    Text segments are encoded via cbmcodecs2 (handles PETSCII character
    mapping). |token| color/control sequences are replaced with their raw
    control byte values and spliced in *after* encoding, so cbmcodecs2
    never sees them.

    Unrecognised |token| sequences are left as-is in the encoded text.

    :param text:       Input string, may contain |token| sequences.
    :param codec_name: cbmcodecs2 codec name. Defaults to lowercase C64.
                       Use 'petscii_c64en_uc' for uppercase/graphics mode.
    :return:           Raw bytes ready to send to the Commodore client.

    >>> petscii_encode('|red|Hi|reset|')[0]   # first byte = red color code
    28
    >>> petscii_encode('|red|Hi|reset|')[-1]  # last byte = reverse off
    146
    """
    if not _CBMCODECS2_AVAILABLE:
        clean = _TOKEN_RE.sub('', text)
        return clean.encode('ascii', errors='replace')

    result = bytearray()
    pos = 0

    for match in _TOKEN_RE.finditer(text):
        # Encode plain text segment before this token
        segment = text[pos:match.start()]
        if segment:
            result.extend(_encode_petscii_segment(segment, codec_name))

        token = match.group(1)
        code = PETSCII_CONTROL_CODES.get(token)
        if code is not None:
            result.append(code)  # raw control byte, bypasses codec
        else:
            # Unknown token — encode as literal text
            logging.warning('petscii_encode: unknown token |%s|', token)
            result.extend(f'|{token}|'.encode(codec_name, errors='replace'))

        pos = match.end()

    # Encode any remaining text after the last token
    tail = text[pos:]
    if tail:
        result.extend(_encode_petscii_segment(tail, codec_name))

    return bytes(result)


def petscii_encode_lines(lines: list[str],
                         codec_name: str = 'petscii_c64en_lc',
                         line_ending: bytes = b'\r',
                         screen_columns: int = 0) -> bytes:
    """
    Encode a list of formatted strings for a Commodore client.
    Each line is encoded via petscii_encode() and joined with the
    Commodore line ending (CR by default).

    :param lines:          Formatted strings (output of format_lines()).
    :param codec_name:     cbmcodecs2 codec name.
    :param line_ending:    Byte separator between lines (CR = b'\\r').
    :param screen_columns: When non-zero, suppress the CR after any line whose
                           visible length fills the screen — the hardware wrap
                           already advances the cursor, and a CR would cause an
                           extra blank line.
    :return:               Raw bytes for the full block of text.

    >>> result = petscii_encode_lines(['Hello', 'World'])
    >>> result == b'Hello\\rWorld'  # simplified — real output is PETSCII encoded
    True
    """
    """
    # Game code:
    await ctx.send("You find |red|a ruby|reset| on the floor.")

    # GameContext.send():
    raw       = flatten_send_args(*lines)
    codec     = PETSCIICodec()              # from codec_for_settings()
    formatted = format_lines(raw, settings, codec)
    # formatted = ["You find \x12a ruby\x92 on the floor."]
    #   \x12 = REVERSE ON (bracket highlight for now, swap for color token later)

    # Then for PETSCII clients:
    encoded = petscii_encode_lines(formatted)
    # "You find " -> cbmcodecs2 -> PETSCII bytes
    # "|red|"     -> chr(28) spliced in raw
    # "a ruby"    -> cbmcodecs2 -> PETSCII bytes
    # "|reset|"   -> chr(146) spliced in raw
    """
    result = bytearray()
    for line in lines:
        result.extend(petscii_encode(line, codec_name))
        # Always CR after each line so consecutive send() calls don't run
        # together — except when the line fills the full screen width, where
        # the C64 hardware-wraps and a CR would produce an extra blank line.
        if not (screen_columns and _visible_len(line) >= screen_columns):
            result.extend(line_ending)
    return bytes(result)


# ---------------------------------------------------------------------------
# ANSI color code table
# ---------------------------------------------------------------------------

# Maps |token| names to colorama ANSI escape strings.
# Token names deliberately match PETSCII_CONTROL_CODES so game strings
# like "|red|text|reset|" work the same way regardless of terminal type.
ANSI_COLOR_CODES: dict[str, str] = {
    'black': Fore.BLACK if _COLORAMA_AVAILABLE else '',
    'white': Fore.WHITE if _COLORAMA_AVAILABLE else '',
    'red': Fore.RED if _COLORAMA_AVAILABLE else '',
    'cyan': Fore.CYAN if _COLORAMA_AVAILABLE else '',
    'green': Fore.GREEN if _COLORAMA_AVAILABLE else '',
    'blue': Fore.BLUE if _COLORAMA_AVAILABLE else '',
    'yellow': Fore.YELLOW if _COLORAMA_AVAILABLE else '',
    'magenta': Fore.MAGENTA if _COLORAMA_AVAILABLE else '',
    'light_red': Fore.LIGHTRED_EX if _COLORAMA_AVAILABLE else '',
    'light_green': Fore.LIGHTGREEN_EX if _COLORAMA_AVAILABLE else '',
    'light_blue': Fore.LIGHTBLUE_EX if _COLORAMA_AVAILABLE else '',
    'light_cyan': Fore.LIGHTCYAN_EX if _COLORAMA_AVAILABLE else '',
    'light_yellow': Fore.LIGHTYELLOW_EX if _COLORAMA_AVAILABLE else '',
    'light_white': Fore.LIGHTWHITE_EX if _COLORAMA_AVAILABLE else '',
    'dark_gray': Fore.LIGHTBLACK_EX if _COLORAMA_AVAILABLE else '',
    'mid_gray': Fore.LIGHTWHITE_EX if _COLORAMA_AVAILABLE else '',
    'light_gray': Fore.WHITE if _COLORAMA_AVAILABLE else '',
    'brown': Fore.YELLOW if _COLORAMA_AVAILABLE else '',
    'orange': Fore.YELLOW if _COLORAMA_AVAILABLE else '',  # closest ANSI approximation
    'purple': Fore.MAGENTA if _COLORAMA_AVAILABLE else '',  # closest ANSI approximation
    'reverse_on': Style.BRIGHT if _COLORAMA_AVAILABLE else '',
    'reverse_off': Style.RESET_ALL if _COLORAMA_AVAILABLE else '',
    'bold': Style.BRIGHT if _COLORAMA_AVAILABLE else '',
    'dim': Style.DIM if _COLORAMA_AVAILABLE else '',
    'reset': Fore.RESET if _COLORAMA_AVAILABLE else '',
}


def ansi_encode(text: str) -> str:
    """
    Replace |token| color sequences with ANSI escape codes.
    Text passes through unchanged except for recognised |token| sequences.
    Unrecognised tokens are left as-is and logged at WARNING.
    Falls back to stripping tokens if colorama is unavailable.

    >>> ansi_encode('Hello |reset|world')  # no color, just reset
    'Hello \\x1b[39mworld'
    >>> ansi_encode('no tokens here')
    'no tokens here'
    >>> ansi_encode('|unknown|text')
    '|unknown|text'
    """

    def _replace(match) -> str:
        token = match.group(1)
        code = ANSI_COLOR_CODES.get(token)
        if code is not None:
            return code
        logging.warning('ansi_encode: unknown token |%s|', token)
        return match.group(0)  # leave unknown tokens intact

    return _TOKEN_RE.sub(_replace, text)


def ansi_encode_lines(lines: list[str]) -> list[str]:
    """
    Apply ansi_encode() to each line in a list.
    Use this in GameContext.send() after format_lines() for ANSI clients.

    >>> ansi_encode_lines(['hello', '{red}world{reset}'])  # doctest: +ELLIPSIS
    ['hello', '...world...']
    """
    return [ansi_encode(line) for line in lines]


_TOKEN_STRIP_RE = re.compile(r'\|[a-z_]+\|')

def plain_encode(text: str) -> str:
    """Strip all |token| sequences for plain-text clients."""
    return _TOKEN_STRIP_RE.sub('', text)

def plain_encode_lines(lines: list[str]) -> list[str]:
    """Apply plain_encode() to each line."""
    return [plain_encode(line) for line in lines]

# ---------------------------------------------------------------------------
# ColorName -> token bridge

# ---------------------------------------------------------------------------

# Maps terminal.ColorName enum values to |token| names used in
# ANSI_COLOR_CODES and PETSCII_CONTROL_CODES.
# ColorName is the player-facing name ("Dark Green");
# the token is the encode-pipeline key ("green").
# Imported lazily inside _build_color_name_to_token() to avoid the
# circular import:  formatting -> terminal -> player -> formatting
def _build_color_name_to_token() -> dict:
    try:
        from terminal import ColorName
        logging.debug('_build_color_name_to_token: ColorName loaded OK')
        return {
            ColorName.BLACK: 'black',
            ColorName.WHITE: 'white',
            ColorName.RED: 'red',
            ColorName.CYAN: 'cyan',
            ColorName.PURPLE: 'purple',
            ColorName.DARK_GREEN: 'green',
            ColorName.DARK_BLUE: 'blue',
            ColorName.YELLOW: 'yellow',
            ColorName.ORANGE: 'orange',
            ColorName.BROWN: 'brown',
            ColorName.LIGHT_RED: 'light_red',
            ColorName.DARK_GRAY: 'dark_gray',
            ColorName.MEDIUM_GRAY: 'mid_gray',
            ColorName.LIGHT_GREEN: 'light_green',
            ColorName.LIGHT_BLUE: 'light_blue',
            ColorName.LIGHT_GRAY: 'light_gray',
            ColorName.RESET: 'reset',
            ColorName.REVERSE_ON: 'reverse_on',
            ColorName.REVERSE_OFF: 'reverse_off',
        }
    except ImportError as e:
        logging.warning('terminal.ColorName not available; COLOR_NAME_TO_TOKEN will be empty. (%s)', e)
        return {}
    except Exception as e:
        logging.warning('COLOR_NAME_TO_TOKEN build failed: %s: %s', type(e).__name__, e)
        return {}


# Lazy cache — built on first access via module __getattr__ below.
# This avoids the circular import that occurs when formatting.py is
# still initialising and terminal.py tries to import back from it.
_COLOR_NAME_TO_TOKEN_CACHE: dict | None = None


def __getattr__(name: str):
    """PEP 562 module __getattr__: called when attribute lookup fails normally."""
    global _COLOR_NAME_TO_TOKEN_CACHE
    if name == 'COLOR_NAME_TO_TOKEN':
        if _COLOR_NAME_TO_TOKEN_CACHE is None:
            _COLOR_NAME_TO_TOKEN_CACHE = _build_color_name_to_token()
        return _COLOR_NAME_TO_TOKEN_CACHE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def highlight_brackets(text: str, codec: ColorCodec) -> str:
    """
    Replace [bracketed text] with color-coded equivalents.
    Uses the codec's highlight_on/highlight_off to wrap matched text.

    >>> codec = PlainCodec()
    >>> highlight_brackets("Hello [world]!", codec)
    'Hello world!'
    >>> highlight_brackets("No brackets here.", codec)
    'No brackets here.'
    """
    return re.sub(
        r'\[(.+?)\]',
        lambda m: f'{codec.highlight_on()}{m.group(1)}{codec.highlight_off()}',
        text
    )


def _visible_len(text: str) -> int:
    """`|token|` sequences are zero-width on screen — strip them before measuring."""
    return len(_TOKEN_STRIP_RE.sub('', text))


def wrap_text(text: str, width: int,
              initial_indent: str = '',
              subsequent_indent: str = '') -> list[str]:
    """
    Word-wrap a single string to `width` visible columns.
    `|token|` color sequences are treated as zero-width so they don't
    cause premature line breaks.
    Returns a list of wrapped lines.
    Empty string input returns [''] (preserves intentional blank lines).

    >>> wrap_text('Hello world', 5)
    ['Hello', 'world']
    >>> wrap_text('', 80)
    ['']
    >>> wrap_text('|yellow|Hello |white|world|reset|', 12)
    ['|yellow|Hello |white|world|reset|']
    >>> wrap_text('|red|One two three|reset|', 7)
    ['|red|One two', 'three|reset|']
    """
    if not text.strip():
        return ['']

    words = text.split(' ')
    lines: list[str] = []
    current: list[str] = []
    indent = initial_indent
    vis_len = len(indent)

    for word in words:
        word_vis = _visible_len(word)
        space = 1 if current else 0
        if current and vis_len + space + word_vis > width:
            lines.append(indent + ' '.join(current))
            indent = subsequent_indent
            current = [word]
            vis_len = len(indent) + word_vis
        else:
            vis_len += space + word_vis
            current.append(word)

    if current:
        lines.append(indent + ' '.join(current))

    return lines if lines else ['']


def format_bullet(text: str, width: int) -> list[str]:
    """
    Format a bullet point, wrapping continuation lines with hanging indent.
    Input text should already have the '* ' prefix stripped.

    >>> format_bullet('Short bullet', 40)
    ['* Short bullet']
    """
    return wrap_text(text, width,
                     initial_indent='* ',
                     subsequent_indent='  ')


def format_line(text: str, width: int, codec: ColorCodec) -> list[str]:
    """
    Format a single line of text:
      1. Apply bracket highlighting
      2. Detect bullet points
      3. Word-wrap to width

    Returns a list of output lines (may be more than one after wrapping).

    >>> codec = PlainCodec()
    >>> format_line('Hello [world]!', 80, codec)
    ['Hello world!']
    >>> format_line('* A bullet point', 20, codec)
    ['* A bullet point']
    >>> format_line('', 80, codec)
    ['']
    """
    if not text.strip():
        return ['']

    highlighted = highlight_brackets(text, codec)

    if highlighted.lstrip().startswith('* '):
        # Strip the bullet prefix, wrap, re-add via format_bullet
        content = highlighted.lstrip()[2:]
        return format_bullet(content, width)

    return wrap_text(highlighted, width)


def format_lines(lines: list[str],
                 settings: HasClientSettings,
                 codec: ColorCodec | None = None) -> list[str]:
    """
    Format a list of strings for output to a player's terminal.
    Applies bracket highlighting, bullet formatting, and word-wrapping.

    :param lines:    Input strings (one logical line each).
    :param settings: ClientSettings-compatible object for screen dimensions.
    :param codec:    ColorCodec to use; defaults to PlainCodec if not provided.
    :return:         Flat list of output-ready strings.

    >>> settings = _MockSettings(screen_columns=20, screen_rows=25)
    >>> codec = PlainCodec()
    >>> format_lines(['Hello world', ''], settings, codec)
    ['Hello world', '']
    """
    if codec is None:
        codec = PlainCodec()

    width = getattr(settings, 'screen_columns', 80)
    result = []
    for line in lines:
        result.extend(format_line(line, width, codec))
    return result


# ---------------------------------------------------------------------------
# Codec factory
# ---------------------------------------------------------------------------

def codec_for_settings(settings) -> ColorCodec:
    """
    Return the appropriate ColorCodec for a ClientSettings object.
    Falls back to PlainCodec if the translation type can't be determined.
    """
    try:
        from terminal import Translation
        t = getattr(settings, 'translation', None)
        if t == Translation.ANSI:
            return ANSICodec()
        if t == Translation.PETSCII:
            return PETSCIICodec()
        if t == Translation.ASCII:
            return PlainCodec()
    except ImportError:
        pass
    return PlainCodec()


def border_style_for_ctx(ctx) -> str:
    """Return the right Table/make_box border style name for this context."""
    cs = ctx.player.client_settings
    if isinstance(codec_for_settings(cs), PETSCIICodec):
        return 'petscii'
    return getattr(cs, 'border_style', 'single')


_HRULE_CHAR: dict[str, str] = {
    'single':  '─',   # U+2500 box drawings light horizontal
    'double':  '═',   # U+2550 box drawings double horizontal
    'petscii': '─',   # cbmcodecs2 maps U+2500 to C64 horizontal line
    'ascii':   '-',
}


def hrule_char(ctx) -> str:
    """Return the single horizontal-rule character for this client's border style."""
    try:
        style = border_style_for_ctx(ctx)
    except AttributeError:
        return '-'
    return _HRULE_CHAR.get(style, '-')


# ---------------------------------------------------------------------------
# Header / rule helpers (pure, return list[str])
# ---------------------------------------------------------------------------

def make_header(text: str, char: str = '=') -> list[str]:
    """
    Return a two-line header: the text and an underline of equal length.

    >>> make_header('Hello')
    ['Hello', '=====']
    >>> make_header('Hi', '-')
    ['Hi', '--']
    """
    return [text, char * len(text)]


def make_rule(width: int, char: str = '-') -> str:
    """
    Return a horizontal rule string of `width` characters.

    >>> make_rule(5)
    '-----'
    """
    return char * width


def _col(text: str, color: str | None) -> str:
    """Wrap text in a |color|…|reset| token pair, or return it unchanged."""
    return f'|{color}|{text}|reset|' if color else text


def make_box(lines: list[str], title: str = '', width: int = 60,
             codec: 'ColorCodec | None' = None,
             frame_color:  str | None = None,
             title_color:  str | None = None,
             text_color:   str | None = None,
             border_style: str | None = None) -> list[str]:
    """
    Wrap lines in a box with an optional title.

    Border characters match the terminal type:
      ANSICodec    → Unicode single-line box-drawing (┌─┐ │ └─┘)
      PETSCIICodec → PETSCII line-drawing characters
      PlainCodec / None → plain ASCII (+ - |)

    Color parameters accept |token| names ('cyan', 'yellow', etc.) or None:
      frame_color  — border characters
      title_color  — title text
      text_color   — body lines

    >>> make_box(['Hello'], width=12)
    ['+----------+', '| Hello    |', '+----------+']
    >>> make_box(['Hi'], width=12, frame_color='cyan')
    ['|cyan|+----------+|reset|', '|cyan|||reset| Hi       |cyan|||reset|', '|cyan|+----------+|reset|']
    """
    from table import ASCII as _ASCII, SINGLE as _SINGLE, DOUBLE as _DOUBLE, PETSCII as _PETSCII

    if isinstance(codec, PETSCIICodec):
        b = _PETSCII
    elif border_style == 'double':
        b = _DOUBLE
    elif border_style == 'ascii':
        b = _ASCII
    elif isinstance(codec, ANSICodec) or border_style == 'single':
        b = _SINGLE
    else:
        b = _ASCII

    inner = width - 4  # '| ' and ' |'

    if title:
        title_str  = f' {title} '
        pad        = width - 2 - len(title_str)
        left_pad   = pad // 2
        right_pad  = pad - left_pad
        top = (
            _col(b.top_left + b.h * left_pad, frame_color)
            + _col(title_str, title_color)
            + _col(b.h * right_pad + b.top_right, frame_color)
        )
    else:
        top = _col(b.top_left + b.h * (width - 2) + b.top_right, frame_color)

    bot  = _col(b.bot_left + b.h * (width - 2) + b.bot_right, frame_color)
    body = [
        _col(b.v, frame_color) + ' ' + _col(line.ljust(inner), text_color) + ' ' + _col(b.v, frame_color)
        for line in lines
    ]

    return [top] + body + [bot]


def make_box_for_settings(settings,
                          lines:       list[str],
                          title:       str       = '',
                          frame_color: str | None = None,
                          title_color: str | None = None,
                          text_color:  str | None = None) -> list[str]:
    """Convenience wrapper: build a box sized and styled for *settings*.

    Reads ``screen_columns``, ``border_style``, and the translation codec
    from the settings object so callers don't have to pass them manually.

    Usage::

        await ctx.send(*make_box_for_settings(
            ctx.player.client_settings,
            ['You have 5 new messages.'],
            title='Inbox',
        ))
    """
    codec        = codec_for_settings(settings)
    width        = getattr(settings, 'screen_columns', 60)
    border_style = getattr(settings, 'border_style', None)
    return make_box(lines, title=title, width=width, codec=codec,
                    border_style=border_style,
                    frame_color=frame_color,
                    title_color=title_color,
                    text_color=text_color)


# ---------------------------------------------------------------------------
# Doctest support
# ---------------------------------------------------------------------------

class _MockSettings:
    """Minimal settings stub for doctests."""

    def __init__(self, screen_columns: int = 80, screen_rows: int = 25):
        self.screen_columns = screen_columns
        self.screen_rows = screen_rows


def flatten_send_args(*args) -> list[str]:
    """
    Flatten the variable args passed to ctx.send() into a single list of strings.
    Handles: single strings, multiple strings, lists of strings, mixed.
    Shared by GameContext.send() and TerminalContext.send().

    >>> flatten_send_args("hello")
    ['hello']
    >>> flatten_send_args("a", "b", "c")
    ['a', 'b', 'c']
    >>> flatten_send_args(["a", "b"])
    ['a', 'b']
    >>> flatten_send_args("a", ["b", "c"])
    ['a', 'b', 'c']
    """
    result: list[str] = []
    for item in args:
        if isinstance(item, list):
            result.extend(str(i) for i in item)
        else:
            result.append(str(item))
    return result


if __name__ == '__main__':
    import doctest

    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)10s | %(funcName)20s() | %(message)s')
    doctest.testmod(verbose=True)