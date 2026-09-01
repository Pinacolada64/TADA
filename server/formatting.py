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
from enum import Enum, auto
from typing import Optional, Protocol, runtime_checkable


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
    highlight_color: str = ''  # set at runtime from player prefs (PREFS 'HC')
    reset_color:      str = ''  # set at runtime from player prefs (PREFS 'C' Text
                                 # color) -- what |reset|/highlight_off() return to.
                                 # Falls back to colorama's own Fore.RESET (terminal
                                 # default) if the player has no preference set.

    def __post_init__(self):
        try:
            from colorama import Fore, Style
            if not self.highlight_color:
                self.highlight_color = Fore.RED
            if not self.reset_color:
                self.reset_color = Fore.RESET
        except ImportError:
            self.highlight_color = ''
            self.reset_color = ''

    def highlight_on(self) -> str:
        return self.highlight_color

    def highlight_off(self) -> str:
        return self.reset_color

    def reset(self) -> str:
        return self.reset_color


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
    reset_color: str = ''  # set at runtime from player prefs (PREFS 'C' Text
                            # color) -- the |token| name that |reset| resolves
                            # to. Falls back to the raw '|reset|' token (CBM
                            # reverse-off, 146) if the player has no preference
                            # set. NOTE: reverse-off alone does *not* restore
                            # the C64's color-RAM text color -- it only clears
                            # reverse video -- so without a real reset_color,
                            # text after |red|...|reset| stays red.

    def highlight_on(self) -> str: return '|reverse_on|'

    def highlight_off(self) -> str: return '|reverse_off|'

    def reset(self) -> str:
        return f'|{self.reset_color}|' if self.reset_color else '|reset|'


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

# New in TADA: |entity| or |entity:count| -- the optional ':count' repeats
# whatever the entity resolves to that many times (e.g. |tab:5| == 5 tabs).
# Every |token| consumer below (ansi_encode, petscii_encode, _TOKEN_STRIP_RE)
# accepts and applies the same ':count' suffix, even though color tokens
# don't have an obvious use for it, so any future repeatable entity gets it
# for free. See _expand_tab_tokens() for 'tab', the first entity to use it.
#
# ||entity|| / ||entity:count|| is an escape, mirroring highlight_brackets()'s
# [[literal]] -> [literal]: it renders as a literal |entity| / |entity:count|
# (single pipes) with no color/tab interpretation, instead of vanishing or
# being substituted. Needed for anything that has to *show* this syntax
# rather than use it -- see commands/help.py's 'colors' topic, the first
# thing that actually needed to display raw |token| examples to a player.
# The escaped group is checked first (named 'etoken'/'ecount') since regex
# alternation tries left-to-right and ||x|| would otherwise partially match
# the plain |x| branch instead.
_TOKEN_RE = re.compile(
    r'\|\|(?P<etoken>[a-z_]+)(?::(?P<ecount>\d+))?\|\|'
    r'|\|(?P<token>[a-z_]+)(?::(?P<count>\d+))?\|'
)


def _token_strip_replace(match: re.Match) -> str:
    """Shared re.sub() replacement for contexts that just want tokens gone
    (petscii_encode's no-cbmcodecs2 fallback, plain_encode, _visible_len):
    a real |token| vanishes, but an escaped ||token|| survives as the
    literal |token| it's meant to display -- same asymmetry as
    highlight_brackets()'s [[x]] -> [x]."""
    if match.group('etoken') is not None:
        literal = '|' + match.group('etoken')
        if match.group('ecount'):
            literal += ':' + match.group('ecount')
        return literal + '|'
    return ''


# New in TADA: PETSCII-only alternate delimiter. '|' needs Shift+- on a
# real Commodore keyboard -- cumbersome enough that Ryan asked for an
# easier-to-type substitute for PETSCII clients specifically. '!' works
# the same as '|' here: !red!, !tab:5!, and the doubled-delimiter escape
# !!red!! (-> literal !red!), matching '|red|'/'|tab:5|'/'||red||' one
# for one. The two delimiters can't be mixed within one token (backreference
# (?P=d)/(?P=d2) requires the closing delimiter(s) to match the opening
# one) -- '|red!' is not a token, just literal text.
#
# Deliberately NOT wired into ansi_encode()/plain_encode(): '!' is common
# in ordinary game text ("Welcome, Alice!", "PILLAGE!"), unlike '|', so
# broadening this beyond PETSCII (where the whole point is avoiding an
# awkward keystroke, not typing convenience for its own sake) would raise
# real collision risk for no corresponding benefit -- ANSI/plain clients
# don't have the Commodore keyboard's Shift+- friction to begin with.
_PETSCII_TOKEN_RE = re.compile(
    r'(?P<d>[|!])(?P=d)(?P<etoken>[a-z_]+)(?::(?P<ecount>\d+))?(?P=d)(?P=d)'
    r'|(?P<d2>[|!])(?P<token>[a-z_]+)(?::(?P<count>\d+))?(?P=d2)'
)

# New in TADA: {$XX} / {DDD} / {NAME} -- a raw PETSCII byte literal, for
# ASCII-art-heavy files (graphics/banner-petscii.txt and friends) that
# need a specific screen/graphics character code with no |token|
# equivalent -- PETSCII_CONTROL_CODES above is for control codes/colors,
# not arbitrary character-set glyphs (e.g. the horizontal-line or
# box-corner characters used to draw a sword or a border). Ryan's idea,
# to make hand-authoring PETSCII art in a plain text file practical
# without a real visual PETSCII editor (see TODO.md for that).
#
#   {$c0}       -- byte 0xC0 (hex, 1-2 digits)
#   {192}       -- byte 192  (decimal, 0-255)
#   {LEFT_TEE}  -- named glyph, looked up in terminal.CommodoreGraphicsChars
#   {$c0:38}    -- any of the above + ':N' repeats the resolved byte N
#                  times, e.g. a 38-character horizontal rule
#
# {{...}} is the escape (mirrors [[...]] / ||token||): renders as the
# literal {...} instead of being resolved.
_GLYPH_TOKEN_RE = re.compile(
    r'\{\{(?P<gelit>[^{}]*)\}\}'
    r'|\{(?:\$(?P<ghex>[0-9a-fA-F]{1,2})'
    r'|(?P<gdec>[0-9]{1,3})'
    r'|(?P<gname>[A-Za-z_][A-Za-z0-9_]*))(?::(?P<gcount>\d+))?\}'
)

# Union of _PETSCII_TOKEN_RE and _GLYPH_TOKEN_RE for a single finditer()
# pass in petscii_encode() -- group names don't collide (d/etoken/ecount/
# d2/token/count vs gelit/ghex/gdec/gname/gcount), so one match object
# unambiguously tells which kind of token was hit.
_PETSCII_GLYPH_RE = re.compile(_PETSCII_TOKEN_RE.pattern + '|' + _GLYPH_TOKEN_RE.pattern)


def _resolve_glyph_byte(match: re.Match) -> Optional[int]:
    """Resolve a _GLYPH_TOKEN_RE (sub-)match's ghex/gdec/gname group to a
    raw byte value 0-255, or None if it doesn't resolve (out-of-range
    decimal, unknown name)."""
    if match.group('ghex') is not None:
        return int(match.group('ghex'), 16)
    if match.group('gdec') is not None:
        val = int(match.group('gdec'))
        return val if val <= 255 else None
    name = match.group('gname')
    return _get_named_petscii_glyphs().get(name)


def _petscii_token_strip_replace(match: re.Match) -> str:
    """_token_strip_replace()'s PETSCII counterpart -- see _PETSCII_TOKEN_RE's
    comment. Preserves whichever delimiter ('|' or '!') was actually used."""
    if match.group('etoken') is not None:
        d = match.group('d')
        literal = d + match.group('etoken')
        if match.group('ecount'):
            literal += ':' + match.group('ecount')
        return literal + d
    return ''


# Characters that cbmcodecs2's petscii_c64en_lc codec has no mapping for
# (it maps 0x5E to the UPWARDS ARROW glyph, not '^'), so a plain
# .encode(codec_name) errors='replace's it to '?'. Maps straight to the
# raw PETSCII byte a real Commodore screen needs instead. '^' is the
# up-arrow key -- the same physical key/glyph HistoryCommand's '^N'
# shortcut uses, so this is what makes it round-trip to the C64 screen
# instead of showing as '?'. See _petscii_input_to_ascii in
# network_context.py for the matching keyboard-input (C64 -> server)
# direction of this same 0x5E mapping.
#
# '_' maps to wire/CHROUT byte 0xE4, NOT screen code 0x64 -- screen codes
# (what you POKE straight into SCREEN_RAM) and PETSCII/CHROUT transmission
# codes are two different numbering spaces for the same glyph. Screen
# code 0x64 is genuinely the underline-ish glyph ('▁', confirmed live via
# POKE 1024,100 in VICE), but sending raw byte 0x64 over the wire (as an
# earlier version of this mapping did) decodes as 'D' once CHROUT converts
# it back to a screen code (0x64 -> screen code 0x44 -> 'D') -- that's
# exactly what rendered as 'D' on Gadget's real hardware. 0xE4 (0x64 +
# 0x80) is the wire byte that CHROUT itself converts to screen code 0x64.
# See _petscii_input_to_ascii in network_context.py for the matching
# keyboard-input (C64 -> server) direction: Shift+Space (0xA0), not this
# byte or the back-arrow key.
_PETSCII_RAW_BYTE_OVERRIDES: dict[str, int] = {
    '^': 0x5E,  # up-arrow glyph
    '_': 0xE4,  # underline-ish glyph (-> screen code 0x64 via CHROUT)
}


def _encode_petscii_segment(text: str, codec_name: str,
                            apply_overrides: bool = True) -> bytes:
    """Encode a plain text segment, substituting raw PETSCII bytes for
    characters cbmcodecs2 has no mapping for (see
    _PETSCII_RAW_BYTE_OVERRIDES). Also used with codec_name='ascii' by
    petscii_encode's no-cbmcodecs2 fallback path -- str.encode() accepts
    'ascii' just as well as a cbmcodecs2 codec name, so the same handling
    applies either way rather than needing a second copy of this
    function. Ryan caught the '_' gap live: without this, the fallback
    path (this environment doesn't have cbmcodecs2 installed) sent a raw
    ASCII 0x5F for '_', which isn't underscore on a real Commodore
    screen -- it happened to render as an unrelated glyph. 0xE4 is the
    real wire/CHROUT byte for the underline-ish glyph (see
    _PETSCII_RAW_BYTE_OVERRIDES's comment for why it isn't 0x64).

    :param apply_overrides: False for PETSCIINetworkContext's genuine
        Translation.ASCII output (network_context.py's _text_codec_name())
        -- there, codec_name='ascii' means the player actually wants
        literal ASCII bytes, not PETSCII-emulating substitutes, so '_'/'^'
        must stay ASCII 0x5F/0x5E instead of becoming PETSCII glyph bytes.
    """
    if not apply_overrides or not any(c in text for c in _PETSCII_RAW_BYTE_OVERRIDES):
        return text.encode(codec_name, errors='replace')
    pattern = '[' + re.escape(''.join(_PETSCII_RAW_BYTE_OVERRIDES)) + ']'
    parts = re.split(f'({pattern})', text)
    buf = bytearray()
    for part in parts:
        if part in _PETSCII_RAW_BYTE_OVERRIDES:
            buf.append(_PETSCII_RAW_BYTE_OVERRIDES[part])
        elif part:
            buf.extend(part.encode(codec_name, errors='replace'))
    return bytes(buf)


def petscii_encode(text: str,
                   codec_name: str = 'petscii_c64en_lc',
                   reset_color: str | None = None,
                   apply_overrides: bool = True) -> bytes:
    """
    Encode a string for transmission to a Commodore client.

    Text segments are encoded via cbmcodecs2 (handles PETSCII character
    mapping). |token| (or !token! -- see _PETSCII_TOKEN_RE) color/control
    sequences and {glyph} raw byte literals (see _GLYPH_TOKEN_RE) are
    replaced with their raw byte values and spliced in *after* encoding,
    so cbmcodecs2 never sees them.

    Unrecognised |token|/!token!/{glyph} sequences are left as-is in the
    encoded text.

    :param text:       Input string, may contain |token|, !token!, or
                       {glyph} sequences.
    :param codec_name: cbmcodecs2 codec name. Defaults to lowercase C64.
                       Use 'petscii_c64en_uc' for uppercase/graphics mode.
    :param reset_color: overrides |reset|'s own control code -- pass
        codec.reset_color (a PETSCIICodec built via codec_for_settings(),
        a PETSCII_CONTROL_CODES token name like 'white') so |reset| sets
        this player's chosen default text color (PREFS 'C' Colors -> Text)
        instead of just clearing reverse video. On real hardware,
        reverse-off (the plain '|reset|' token, code 146) does NOT touch
        color RAM, so without this override text after |red|...|reset|
        stays red. None (the default) keeps that reverse-off behavior,
        e.g. for callers with no player/settings context.
    :return:           Raw bytes ready to send to the Commodore client.

    >>> petscii_encode('|red|Hi|reset|')[0]   # first byte = red color code
    28
    >>> petscii_encode('|red|Hi|reset|')[-1]  # last byte = reverse off
    146
    >>> petscii_encode('|red|Hi|reset|', reset_color='white')[-1]  # player's default color
    5
    >>> petscii_encode('!red!Hi!reset!')[0]   # '!' works the same as '|'
    28
    >>> petscii_encode('{$c0}')[0]            # raw hex byte literal
    192
    """
    if not _CBMCODECS2_AVAILABLE:
        clean = _PETSCII_TOKEN_RE.sub(_petscii_token_strip_replace, text)
        clean = _GLYPH_TOKEN_RE.sub(
            lambda m: m.group('gelit') if m.group('gelit') is not None else '', clean)
        return _encode_petscii_segment(clean, 'ascii')

    result = bytearray()
    pos = 0

    for match in _PETSCII_GLYPH_RE.finditer(text):
        # Encode plain text segment before this token
        segment = text[pos:match.start()]
        if segment:
            result.extend(_encode_petscii_segment(segment, codec_name, apply_overrides))

        if match.group('etoken') is not None:
            # !!token!! / ||token|| (and their ':count' forms) escape --
            # literal !token[:count]! / |token[:count]|, no color/tab
            # interpretation. See _PETSCII_TOKEN_RE's comment.
            d = match.group('d')
            literal = d + match.group('etoken')
            if match.group('ecount'):
                literal += ':' + match.group('ecount')
            literal += d
            result.extend(_encode_petscii_segment(literal, codec_name, apply_overrides))
            pos = match.end()
            continue

        if match.group('gelit') is not None:
            # {{literal}} escape -- literal {literal}, see _GLYPH_TOKEN_RE.
            result.extend(_encode_petscii_segment('{' + match.group('gelit') + '}', codec_name, apply_overrides))
            pos = match.end()
            continue

        if match.group('ghex') is not None or match.group('gdec') is not None or match.group('gname') is not None:
            code = _resolve_glyph_byte(match)
            count = int(match.group('gcount')) if match.group('gcount') else 1
            if code is not None:
                result.extend(bytes([code]) * count)  # raw byte(s), bypasses codec
            else:
                logging.warning('petscii_encode: unresolved glyph token %r', match.group(0))
                result.extend(match.group(0).encode(codec_name, errors='replace'))
            pos = match.end()
            continue

        token = match.group('token')
        count = int(match.group('count')) if match.group('count') else 1
        if token == 'reset' and reset_color:
            code = PETSCII_CONTROL_CODES.get(reset_color)
        else:
            code = PETSCII_CONTROL_CODES.get(token)
        if code is not None:
            result.extend(bytes([code]) * count)  # raw control byte(s), bypasses codec
        else:
            # Unknown token — encode as literal text
            logging.warning('petscii_encode: unknown token %s%s%s', match.group('d2'), token, match.group('d2'))
            result.extend(match.group(0).encode(codec_name, errors='replace'))

        pos = match.end()

    # Encode any remaining text after the last token
    tail = text[pos:]
    if tail:
        result.extend(_encode_petscii_segment(tail, codec_name, apply_overrides))

    return bytes(result)


def petscii_encode_lines(lines: list[str],
                         codec_name: str = 'petscii_c64en_lc',
                         line_ending: bytes = b'\r',
                         screen_columns: int = 0,
                         reset_color: str | None = None,
                         apply_overrides: bool = True) -> bytes:
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
    :param reset_color:    overrides |reset|'s own control code -- see
                           petscii_encode()'s reset_color param.
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
        result.extend(petscii_encode(line, codec_name, reset_color=reset_color,
                                     apply_overrides=apply_overrides))
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
    # True ANSI reverse video (SGR 7/27) -- colorama's Style enum has no
    # reverse-video constant of its own (only BRIGHT/DIM/NORMAL/RESET_ALL),
    # so these were previously (wrongly) aliased to Style.BRIGHT, which is
    # bold/intensity, not a foreground/background swap. A bold *space*
    # character (e.g. commands/map.py's #overview room squares) looks
    # identical to a plain space -- no visible highlight at all -- which
    # is exactly the bug this was: raw escape codes below match the
    # convention terminal.py's cursor-movement constants already use for
    # codes colorama doesn't expose. SGR 27 turns reverse back off
    # without also clearing color like Style.RESET_ALL would, so
    # |reverse_off| behaves correctly even without a following |reset|.
    'reverse_on': '\x1b[7m' if _COLORAMA_AVAILABLE else '',
    'reverse_off': '\x1b[27m' if _COLORAMA_AVAILABLE else '',
    'bold': Style.BRIGHT if _COLORAMA_AVAILABLE else '',
    'dim': Style.DIM if _COLORAMA_AVAILABLE else '',
    'reset': Fore.RESET if _COLORAMA_AVAILABLE else '',
}


def ansi_encode(text: str, reset_color: str | None = None) -> str:
    """
    Replace |token| color sequences with ANSI escape codes.
    Text passes through unchanged except for recognised |token| sequences.
    Unrecognised tokens are left as-is and logged at WARNING.
    Falls back to stripping tokens if colorama is unavailable.

    :param reset_color: overrides |reset|'s own ANSI code -- pass
        codec.reset() (an ANSICodec built via codec_for_settings()) so
        |reset| returns to *this player's* chosen default text color
        (PREFS 'C' Colors -> Text) instead of always hard-resetting to
        the terminal's own uncontrolled default. None (the default)
        keeps the plain colorama Fore.RESET behavior, e.g. for callers
        with no player/settings context.

    >>> ansi_encode('Hello |reset|world')  # no color, just reset
    'Hello \\x1b[39mworld'
    >>> ansi_encode('no tokens here')
    'no tokens here'
    >>> ansi_encode('|unknown|text')
    '|unknown|text'
    """

    def _replace(match) -> str:
        if match.group('etoken') is not None:
            # ||token|| / ||token:count|| escape -- literal |token[:count]|.
            literal = '|' + match.group('etoken')
            if match.group('ecount'):
                literal += ':' + match.group('ecount')
            return literal + '|'
        token = match.group('token')
        count = int(match.group('count')) if match.group('count') else 1
        if token == 'reset' and reset_color is not None:
            return reset_color * count
        code = ANSI_COLOR_CODES.get(token)
        if code is not None:
            return code * count
        logging.warning('ansi_encode: unknown token |%s|', token)
        return match.group(0)  # leave unknown tokens intact

    return _TOKEN_RE.sub(_replace, text)


def ansi_encode_lines(lines: list[str], reset_color: str | None = None) -> list[str]:
    """
    Apply ansi_encode() to each line in a list.
    Use this in GameContext.send() after format_lines() for ANSI clients.

    >>> ansi_encode_lines(['hello', '{red}world{reset}'])  # doctest: +ELLIPSIS
    ['hello', '...world...']
    """
    return [ansi_encode(line, reset_color) for line in lines]


# Shares _TOKEN_RE's escaped/plain alternation (named 'etoken'/'ecount' vs
# 'token'/'count') so _token_strip_replace() works for both this and
# ansi_encode/petscii_encode's fallback paths.
_TOKEN_STRIP_RE   = _TOKEN_RE
_ANSI_ESCAPE_RE   = re.compile(r'\x1b\[[^a-zA-Z]*[a-zA-Z]')

def plain_encode(text: str) -> str:
    """Strip all |token| sequences for plain-text clients. An escaped
    ||token|| survives as the literal |token| it's meant to display --
    see _TOKEN_RE's comment."""
    return _TOKEN_STRIP_RE.sub(_token_strip_replace, text)

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


def _build_named_petscii_glyphs() -> dict:
    """{NAME} glyph lookup for _resolve_glyph_byte() -- terminal.
    CommodoreGraphicsChars' members (LEFT_TEE, CORNER_UPPER_LEFT, etc),
    keyed by name, resolved to their raw PETSCII byte value."""
    try:
        from terminal import CommodoreGraphicsChars
        # __members__, not a plain `for member in CommodoreGraphicsChars`
        # iteration -- CommodoreGraphicsChars has genuine value collisions
        # (e.g. TOP_TEE and LEFT_TEE are both chr(178), likely a stale
        # copy-paste in terminal.py rather than intentional), which makes
        # Enum treat the second name as an *alias* of the first and drops
        # it from plain iteration entirely. __members__ still has both
        # names, each resolving to whichever byte its (possibly shared)
        # canonical member holds, so {LEFT_TEE} keeps working even though
        # the underlying byte table has a bug worth someone fixing later.
        return {name: ord(str(member.value))
                for name, member in CommodoreGraphicsChars.__members__.items()}
    except ImportError as e:
        logging.warning('terminal.CommodoreGraphicsChars not available; '
                        'NAMED_PETSCII_GLYPHS will be empty. (%s)', e)
        return {}
    except Exception as e:
        logging.warning('NAMED_PETSCII_GLYPHS build failed: %s: %s', type(e).__name__, e)
        return {}


# Lazy caches — built on first access via module __getattr__ below.
# This avoids the circular import that occurs when formatting.py is
# still initialising and terminal.py tries to import back from it.
_COLOR_NAME_TO_TOKEN_CACHE: dict | None = None
_NAMED_PETSCII_GLYPHS_CACHE: dict | None = None


def _get_named_petscii_glyphs() -> dict:
    """Internal accessor for the {NAME} glyph lookup used by
    _resolve_glyph_byte() -- a bare 'NAMED_PETSCII_GLYPHS' reference
    inside this module would NOT go through __getattr__ below (that PEP
    562 hook only fires for module.attribute access from *outside*, not
    a function body's own global name lookup), so code inside this
    module must call this helper instead of naming the lazy attribute
    directly."""
    global _NAMED_PETSCII_GLYPHS_CACHE
    if _NAMED_PETSCII_GLYPHS_CACHE is None:
        _NAMED_PETSCII_GLYPHS_CACHE = _build_named_petscii_glyphs()
    return _NAMED_PETSCII_GLYPHS_CACHE


def __getattr__(name: str):
    """PEP 562 module __getattr__: called when attribute lookup fails normally."""
    global _COLOR_NAME_TO_TOKEN_CACHE
    if name == 'COLOR_NAME_TO_TOKEN':
        if _COLOR_NAME_TO_TOKEN_CACHE is None:
            _COLOR_NAME_TO_TOKEN_CACHE = _build_color_name_to_token()
        return _COLOR_NAME_TO_TOKEN_CACHE
    if name == 'NAMED_PETSCII_GLYPHS':
        return _get_named_petscii_glyphs()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


_BRACKET_RE = re.compile(r'\[\[(.+?)\]\]|\[(.+?)\]')


def _bracket_replace_len(m: re.Match) -> str:
    """[bracket]-resolution with zero-width highlighting -- shared by
    highlight_brackets() (real codec) and _visible_len() (PlainCodec-
    equivalent, for measuring the width text will render at). Keeping
    one regex/replacement pair means a future change to the [[escape]]
    rule can't drift between what gets highlighted and what gets sized."""
    if m.group(1) is not None:          # [[...]] escape → literal [...]
        return f'[{m.group(1)}]'
    return m.group(2)                   # [...] → content only (delimiters vanish)


def highlight_brackets(text: str, codec: ColorCodec) -> str:
    """
    Replace [bracketed text] with color-coded equivalents.
    Uses the codec's highlight_on/highlight_off to wrap matched text.

    Double brackets [[like this]] are an escape: they render as a literal
    [like this] without any colour applied.

    >>> codec = PlainCodec()
    >>> highlight_brackets("Hello [world]!", codec)
    'Hello world!'
    >>> highlight_brackets("No brackets here.", codec)
    'No brackets here.'
    >>> highlight_brackets("Usage: cmd [[optional]]", codec)
    'Usage: cmd [optional]'
    """
    def _replace(m: re.Match) -> str:
        if m.group(1) is not None:      # [[...]] escape → literal [...]
            return f'[{m.group(1)}]'
        return f'{codec.highlight_on()}{m.group(2)}{codec.highlight_off()}'
    return _BRACKET_RE.sub(_replace, text)


def _glyph_visible_replace(m: re.Match) -> str:
    """_visible_len()'s {glyph} counterpart to _token_strip_replace(): a
    real {glyph}/{glyph:N} token is NOT zero-width like a |token| color
    code -- it renders N actual on-screen characters -- so it's replaced
    with a same-length placeholder rather than removed. An escaped
    {{literal}} counts its literal {literal} rendering, same asymmetry as
    ||token||/[[bracket]]."""
    if m.group('gelit') is not None:
        return '{' + m.group('gelit') + '}'
    count = int(m.group('gcount')) if m.group('gcount') else 1
    return 'x' * count


def _visible_len(text: str) -> int:
    """Count visible columns: resolves [bracket] highlighting (the '['/']'
    delimiters vanish on render -- see _bracket_replace_len()), strips
    |token| sequences and raw ANSI escape codes, and measures {glyph}
    raw-byte tokens by their actual on-screen width. An escaped ||token||
    counts its literal |token| rendering (not zero) since it actually
    prints -- see _TOKEN_RE's comment.

    Safe to call on text *before* highlight_brackets() has run (e.g. a
    table/box column-sizing or .ljust()-padding pass over raw tip/cell
    text still carrying literal [LOOT]) as well as after (already-
    resolved text has no bare [...] left to match) -- either way this
    returns the width it will actually occupy on screen once
    highlight_brackets() runs, which pre-highlight .ljust()/width math
    must use instead of len()/[bracket]-blind counts, or a highlighted
    word renders 2 columns narrower than reserved and misaligns the
    border/column to its right (found via tips.json's [LOOT]/[GIVE] tags
    and STAT's ally table '[ELITE]'-style status tags)."""
    text = _BRACKET_RE.sub(_bracket_replace_len, text)
    text = _TOKEN_STRIP_RE.sub(_token_strip_replace, text)
    text = _GLYPH_TOKEN_RE.sub(_glyph_visible_replace, text)
    text = _ANSI_ESCAPE_RE.sub('', text)
    return len(text)


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


def numbered_list(items: list[str], width: int) -> list[str]:
    """
    Format *items* as a numbered list (1., 2., 3., ...), wrapping
    continuation lines with a hanging indent so they align under the text
    rather than the number -- same idea as format_bullet(), but for a
    whole list of items at once instead of one already-numbered line.

    >>> numbered_list(['Short item'], 40)
    ['1. Short item']
    >>> numbered_list(['One', 'Two'], 40)
    ['1. One', '2. Two']
    """
    lines: list[str] = []
    for i, item in enumerate(items, start=1):
        prefix = f'{i}. '
        lines.extend(wrap_text(item, width,
                               initial_indent=prefix,
                               subsequent_indent=' ' * len(prefix)))
    return lines


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


# Only matches the *real* (single-pipe) form -- ||tab||/||tab:N|| (escaped)
# is deliberately left alone here and falls through to ansi_encode()'s/
# petscii_encode()'s/plain_encode()'s own _TOKEN_RE-based escape handling
# later in the pipeline. Collapsing the escape here too, before those run,
# would hand them a bare single-pipe "|tab|" indistinguishable from a real
# token -- plain_encode() in particular would then strip it as if it were
# live markup instead of preserving it as the literal text it's meant to
# display (found while writing commands/help.py's 'colors' topic, whose
# usage table showed |tab| examples that vanished under plain_encode()).
_TAB_TOKEN_RE = re.compile(r'(?<!\|)\|tab(?::(?P<n>\d+))?\|(?!\|)')

# PETSCII-only: also accepts '!tab!'/'!tab:N!' -- see _PETSCII_TOKEN_RE's
# comment on why '!' is scoped to PETSCII instead of joining _TAB_TOKEN_RE
# above for every codec. Matches '|tab|' too (petscii_encode()/plain_encode()
# still accept '|' as well), just with '!' additionally recognized.
_TAB_TOKEN_RE_PETSCII = re.compile(
    r'(?<![|!])(?P<d>[|!])tab(?::(?P<n>\d+))?(?P=d)(?![|!])'
)


def _expand_tab_tokens(text: str, settings, codec: 'ColorCodec | None' = None) -> str:
    """
    Replace |tab| / |tab:N| (or, for PETSCII clients only, !tab! / !tab:N! --
    see _TAB_TOKEN_RE_PETSCII's comment) with the player's actual tab
    output -- see PREFS 'K' (Tab Key), which sets
    client_settings.tab_settings.has_tab_key/tab_width.

    If the client has a real Tab key, each token becomes a literal '\\t'
    (repeated N times) -- the terminal itself handles tab-stop spacing, so
    no column math is needed here. Otherwise (tabs simulated with spaces)
    each token advances to the *next actual tab stop* -- a real terminal's
    Tab key doesn't emit a fixed number of spaces, it emits just enough to
    reach the next multiple of tab_width from the current column, so a
    |tab| at column 3 with tab_width 8 emits 5 spaces while one at column 9
    emits 7 -- not tab_width spaces every time. That requires tracking the
    running visible column across the line (via _visible_len(), which
    already knows how to skip color |token|s/[bracket]s/etc.), so this
    walks the token matches in order rather than using a single blind
    pattern.sub(). The escaped form ||tab||/!!tab!! (see _TOKEN_RE's
    comment) is left untouched here -- ansi_encode()/petscii_encode()/
    plain_encode() resolve it to a literal |tab|/!tab! later.

    Unlike color |token|s (a static per-codec substitution table applied
    at ansi_encode()/petscii_encode() time), a tab's rendered width is
    player-specific and needs to participate in word-wrap/visible-length
    the same as any other character -- so this expands to real characters
    here, in format_lines(), before format_line()'s wrapping runs, rather
    than staying an opaque token until the codec stage.
    """
    tab_settings = getattr(settings, 'tab_settings', None)
    has_tab_key = getattr(tab_settings, 'has_tab_key', False) if tab_settings else False
    tab_output = getattr(tab_settings, 'tab_output', '\t') if tab_settings else '\t'
    tab_width = getattr(tab_settings, 'tab_width', 0) if tab_settings else 0

    pattern = _TAB_TOKEN_RE_PETSCII if isinstance(codec, PETSCIICodec) else _TAB_TOKEN_RE

    if has_tab_key or tab_width <= 0:
        # Real Tab key (or a degenerate 0-width simulated tab): no stop
        # math to do, just emit the configured output N times.
        def _replace(match) -> str:
            count = int(match.group('n')) if match.group('n') else 1
            return tab_output * count
        return pattern.sub(_replace, text)

    # Simulated tabs: advance to the next real tab stop from the running
    # visible column, not a flat tab_width-space repeat every time.
    out_parts: list[str] = []
    last_end = 0
    col = 0
    for match in pattern.finditer(text):
        segment = text[last_end:match.start()]
        out_parts.append(segment)
        col += _visible_len(segment)
        count = int(match.group('n')) if match.group('n') else 1
        for _ in range(count):
            spaces = tab_width - (col % tab_width)
            out_parts.append(' ' * spaces)
            col += spaces
        last_end = match.end()
    out_parts.append(text[last_end:])
    return ''.join(out_parts)


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
        line = _expand_tab_tokens(line, settings, codec)
        result.extend(format_line(line, width, codec))
    return result


# ---------------------------------------------------------------------------
# Codec factory
# ---------------------------------------------------------------------------

def _ansi_color_for(settings, attr: str) -> str:
    """Resolve settings.colors.<attr> (a terminal.ColorName) to its
    colorama value via terminal.ANSIColors, or '' if unset/unmapped
    (ANSICodec falls back to its own hardcoded default in that case)."""
    from terminal import ANSIColors
    color_name = getattr(getattr(settings, 'colors', None), attr, None)
    if color_name is None:
        return ''
    try:
        return ANSIColors[color_name.name].value or ''
    except KeyError:
        return ''


# ColorName -> PETSCII_CONTROL_CODES token name. Most just lowercase, but a
# few CBM color names diverge from ColorName's ANSI-flavored spelling.
_COLOR_NAME_TO_PETSCII_TOKEN: dict[str, str] = {
    'DARK_GREEN':  'green',
    'DARK_BLUE':   'blue',
    'MEDIUM_GRAY': 'mid_gray',
}


def _petscii_color_for(settings, attr: str) -> str:
    """Resolve settings.colors.<attr> (a terminal.ColorName) to its
    PETSCII_CONTROL_CODES |token| name, or '' if unset/unmapped
    (PETSCIICodec falls back to the raw '|reset|' token in that case)."""
    color_name = getattr(getattr(settings, 'colors', None), attr, None)
    if color_name is None:
        return ''
    token = _COLOR_NAME_TO_PETSCII_TOKEN.get(color_name.name, color_name.name.lower())
    return token if token in PETSCII_CONTROL_CODES else ''


def codec_for_settings(settings) -> ColorCodec:
    """
    Return the appropriate ColorCodec for a ClientSettings object.
    Falls back to PlainCodec if the translation type can't be determined.

    For ANSI, threads two of the player's own PREFS 'C' Colors choices
    into the codec (commands/prefs.py's colors menu), via terminal.
    ANSIColors' matching colorama values -- previously ANSICodec() always
    fell back to its own hardcoded defaults (Fore.RED / Fore.RESET)
    regardless of what the player picked; the preferences were stored
    but never actually read anywhere:
      - highlight_color <- settings.colors.highlight_color ('HC' row):
        the color [bracket] highlighting uses.
      - reset_color <- settings.colors.text_color ('Text' row): what
        |reset|/highlight_off() return to, so text goes back to the
        player's own chosen default color instead of an uncontrolled
        terminal-default reset.

    PETSCII gets the same reset_color treatment -- see PETSCIICodec's
    reset_color field.
    """
    try:
        from terminal import Translation
        t = getattr(settings, 'translation', None)
        if t == Translation.ANSI:
            return ANSICodec(
                highlight_color=_ansi_color_for(settings, 'highlight_color'),
                reset_color=_ansi_color_for(settings, 'text_color'),
            )
        if t == Translation.PETSCII:
            return PETSCIICodec(
                reset_color=_petscii_color_for(settings, 'text_color'),
            )
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


def _localize_for_player(dt, player):
    """Anchor a naive *dt* to a source timezone and convert to *player*'s
    own PREFS timezone choice (commands/prefs.py 'Z' row) -- shared by
    format_player_datetime() and format_player_time().

    *dt* is expected to be a naive datetime (this codebase's timestamps
    -- e.g. player.last_connection -- are stored via bare datetime.now(),
    never made timezone-aware) or already timezone-aware. A naive *dt* is
    first anchored to a *source* zone -- config.server_timezone if a
    sysop has set one (setup/server_setup.py / the in-game CONFIG
    command's 'server_timezone' setting declares what timezone these
    naive timestamps actually represent), else the server process's own
    OS-local zone, unchanged from before that setting existed. The
    player's own timezone choice then converts from that source zone; an
    empty/unset player timezone means "use the source zone as-is," which
    is what PREFS 'Z' Timezone's 'Server Local' option means. A bad/
    unknown IANA zone name (either source) falls back gracefully rather
    than raising.
    """
    import zoneinfo

    cs      = getattr(player, 'client_settings', None)
    tz_name = (getattr(cs, 'timezone', '') or '').strip()

    if dt.tzinfo is None:
        server_tz_name = ''
        try:
            from config import config
            server_tz_name = (config.server_timezone or '').strip()
        except Exception:
            pass
        if server_tz_name:
            try:
                dt = dt.replace(tzinfo=zoneinfo.ZoneInfo(server_tz_name))
            except Exception:
                logging.warning("_localize_for_player: unknown/invalid server_timezone %r", server_tz_name)
                dt = dt.astimezone()
        else:
            dt = dt.astimezone()

    if tz_name:
        try:
            dt = dt.astimezone(zoneinfo.ZoneInfo(tz_name))
        except Exception:
            logging.warning("_localize_for_player: unknown/invalid timezone %r", tz_name)

    return dt


def format_player_datetime(dt, player) -> str:
    """Render *dt* using *player*'s PREFS timezone/date-format choice
    (commands/prefs.py's 'Z'/'D' rows, ClientSettings.timezone/
    date_format -- New in TADA). Whether a weekday name appears at all,
    and whether it's abbreviated, is entirely up to which preset the
    player picked (commands/prefs.py's _DATE_FORMAT_PRESETS pairs a
    plain and a "Weekday, ..." variant of each format, e.g. 'Month Day,
    Year' vs. 'Weekday, Month Day, Year') -- there's no separate weekday
    step here, unlike before 2026-08-27. See _localize_for_player() for
    how the timezone conversion works."""
    cs          = getattr(player, 'client_settings', None)
    date_format = getattr(cs, 'date_format', '') or '%A, %B %d, %Y'
    dt          = _localize_for_player(dt, player)

    try:
        return dt.strftime(date_format)
    except (ValueError, TypeError):
        logging.warning("format_player_datetime: bad date_format %r", date_format)
        return dt.strftime('%A, %B %d, %Y')


def format_player_time(dt, player) -> str:
    """Render *dt* (time-of-day only) using *player*'s PREFS timezone/
    time-format choice (commands/prefs.py's 'Z'/'F' rows,
    ClientSettings.timezone/time_format -- New in TADA). Used by the
    Hourglass clock (network_context.py/terminal_context.py's prompt())
    and available for any other player-facing time-of-day display. See
    _localize_for_player() for how the timezone conversion works."""
    cs          = getattr(player, 'client_settings', None)
    time_format = getattr(cs, 'time_format', '') or '%H:%M'
    dt          = _localize_for_player(dt, player)

    try:
        return dt.strftime(time_format)
    except (ValueError, TypeError):
        logging.warning("format_player_time: bad time_format %r", time_format)
        return dt.strftime('%H:%M')


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
# Guild territory sigils
#
# ANSI/ASCII terminals get the classic SPUR ASCII glyphs -- just in full
# color now. PETSCII/Commodore terminals get a couple of real C64
# box-drawing glyphs instead, where cbmcodecs2 actually has a PETSCII slot
# for them (verified by direct encode against 'petscii_c64en_lc', the
# upper/lowercase charset mode -- NOT the upper/graphics mode, which maps
# some of these code points to different glyphs):
#   '├' (U+251C, left tee)      -> encodes fine, used for the sword's hilt
#   '─' (U+2500, horizontal)    -> encodes fine, used for the sword's blade
#   '│' (U+2502, vertical)      -> encodes fine
#   '\' and ASCII '|' (pipe)    -> NEITHER has a PETSCII slot at all, in
#                                  either charset mode (cbmcodecs2 raises
#                                  UnicodeEncodeError for both) -- not just
#                                  a charset-mode mismatch, they simply
#                                  don't exist as C64 screen codes.
#   '╲' / '╱' (diagonal lines)  -> also no PETSCII slot; there is exactly
#                                  one double-quadrant block on the C64
#                                  ('▚' U+259E-adjacent, NW+SE quadrants
#                                  filled) and no mirrored NE+SW version.
# Claw's original SPUR sigil ('\|/') is therefore unrenderable as-is on a
# real Commodore -- replaced with '/))' (claw-scratch curves), which is
# plain ASCII and renders identically, and correctly, on both terminal
# types.
#
# NOTE for later: real thick diagonal-line PETSCII glyphs *do* exist on the
# C64, but only as raw screen/CHR$ codes 0x4D ('\'-ish, upper-left to
# lower-right) and 0x43 ('/'-ish, lower-left to upper-right) in the
# upper/graphics charset (the '|uppercase|' control token, PETSCII code
# 142) -- NOT the upper/lowercase mode this codebase uses by default (see
# 'lowercase'/'uppercase' entries in PETSCII_CONTROL_CODES above). Since
# they're graphics-only glyphs, cbmcodecs2 doesn't expose them via a
# distinct Unicode codepoint through 'petscii_c64en_uc' (it decodes those
# byte values back to plain ASCII 'M'/'C' instead) -- using them for real
# would mean splicing the raw bytes directly, the same way
# PETSCII_CONTROL_CODES' control codes bypass the codec, and switching the
# client to graphics mode first. Not attempted here since this codebase
# intentionally stays in upper/lowercase mode; worth revisiting if that
# ever changes.
# ---------------------------------------------------------------------------

_GUILD_SIGIL_ANSI: dict = {
    'free_fire': '|red|+|reset|',
    'claw':      '|magenta|/))|reset|',
    'sword':     '|cyan|-}===>|reset|',
    'fist':      '|light_red|==[]|reset|',
    'hq':        '|yellow|HQ|reset|',
}

_GUILD_SIGIL_PETSCII: dict = {
    'free_fire': '|red|+|reset|',
    'claw':      '|purple|/))|reset|',
    'sword':     '|yellow|├|mid_gray|──|light_gray|>|reset|',
    'fist':      '|light_red|==[]|reset|',
    'hq':        '|yellow|HQ|reset|',
}


def guild_sigil_for(ctx, alignment) -> str | None:
    """Return a colorized guild-territory sigil for *alignment*, styled for
    ctx's terminal type. None for NEUTRAL/unset/unrecognized -- NEUTRAL means
    "no marker" (see base_classes.RoomAlignment's docstring).

    *alignment* may be a RoomAlignment member or its raw string value.
    """
    if not alignment or str(getattr(alignment, 'value', alignment)) == 'neutral':
        return None
    key = str(getattr(alignment, 'value', alignment))
    codec = codec_for_settings(ctx.player.client_settings)
    table = _GUILD_SIGIL_PETSCII if isinstance(codec, PETSCIICodec) else _GUILD_SIGIL_ANSI
    return table.get(key)


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


def underline(text: str, ctx) -> list[str]:
    """Return [text, rule] where the rule character matches the client's border style."""
    return [text, hrule_char(ctx) * len(text)]


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
        # .ljust(inner) would pad from len(line), which still counts
        # [bracket]-highlighted words at their raw (un-highlighted) width
        # -- pad from _visible_len() instead so the right border still
        # lands at column `inner` once highlight_brackets() shrinks those
        # words downstream (see _visible_len()'s docstring).
        _col(b.v, frame_color) + ' '
        + _col(line + ' ' * max(0, inner - _visible_len(line)), text_color)
        + ' ' + _col(b.v, frame_color)
        for line in lines
    ]

    return [top] + body + [bot]


def make_box_for_settings(settings,
                          lines:       list[str],
                          title:       str       = '',
                          width:       int | None = None,
                          frame_color: str | None = None,
                          title_color: str | None = None,
                          text_color:  str | None = None) -> list[str]:
    """Convenience wrapper: build a box sized and styled for *settings*.

    Reads ``screen_columns``, ``border_style``, and the translation codec
    from the settings object so callers don't have to pass them manually
    -- pass *width* explicitly to override ``screen_columns`` (e.g. a
    caller with its own fixed default, or a test using a bare mock
    settings object with no real screen_columns to read).

    Usage::

        await ctx.send(*make_box_for_settings(
            ctx.player.client_settings,
            ['You have 5 new messages.'],
            title='Inbox',
        ))
    """
    codec        = codec_for_settings(settings)
    if width is None:
        width = getattr(settings, 'screen_columns', 60)
    border_style = getattr(settings, 'border_style', None)
    return make_box(lines, title=title, width=width, codec=codec,
                    border_style=border_style,
                    frame_color=frame_color,
                    title_color=title_color,
                    text_color=text_color)


def titled_box(ctx, title: str, body: str | list[str], width: int | None = None,
                frame_color: str | None = None,
                title_color: str | None = None,
                text_color:  str | None = None) -> list[str]:
    """Word-wrap *body* and wrap it in a titled, terminal-aware box via
    make_box_for_settings(). *body* may be a single string (wrapped as one
    paragraph) or a list of strings (each wrapped independently, so a
    caller can control paragraph breaks). *width* defaults to
    ctx.player's own screen_columns; pass it explicitly to pin a fixed
    width instead (e.g. a caller with its own default, or a test using a
    bare mock settings object with no real screen_columns to read).

    Extracted from tips.py's format_tip_box() (the "Tip #x / y" box shown
    at login) so any other caller wanting the same look -- e.g. a
    "Quoting <player>" box shown before composing a threaded-board reply
    -- doesn't have to hand-roll the wrap-then-box plumbing again.
    """
    import textwrap

    settings = ctx.player.client_settings
    if width is None:
        width = getattr(settings, 'screen_columns', 60)
    paragraphs = [body] if isinstance(body, str) else body
    lines: list[str] = []
    for paragraph in paragraphs:
        lines.extend(textwrap.wrap(paragraph, width=width - 4) or [''])
    return make_box_for_settings(
        settings, lines, title=title, width=width,
        frame_color=frame_color, title_color=title_color, text_color=text_color,
    )


# ---------------------------------------------------------------------------
# Line model -- Justification/Border-aware text lines, rendered fresh at
# view time rather than baked into .text, so the same saved content
# displays correctly for two players with different screen widths or
# terminal types. text_editor.py (the ed-style line editor) builds saved
# content out of these; news.py persists the serialized form via
# serialize_lines()/deserialize_lines() below so a saved post re-renders
# per-viewer instead of being frozen at whichever width/glyph-set the
# author's terminal had at save time.
# ---------------------------------------------------------------------------

class Justification(Enum):
    LEFT       = auto()
    CENTER     = auto()
    RIGHT      = auto()
    EXPAND     = auto()  # persistent render-time style (see Line.render)
    # PACK/INDENT/UN_INDENT are one-time text mutations, not persistent
    # styles -- see text_editor.py's _cmd_justify -- but keeping them as
    # Justification members too matches the .J dot-command's vocabulary.
    PACK       = auto()
    INDENT     = auto()
    UN_INDENT  = auto()


class LineFlag(Enum):
    MUTABLE   = auto()  # default -- editable
    IMMUTABLE = auto()  # text_editor.py's Edit/Delete/Justify skip these
    QUOTE     = auto()  # reserved for a future reply-quoting feature


class BorderRole(Enum):
    """Which part of a border box a Line represents. Only CONTENT lines
    carry real text -- TOP/BOTTOM render as a rule line regardless of
    .text (a box's width should track *whoever's viewing it*, not
    whatever screen width was active when the border was made, so
    nothing about box width is baked into .text at command time --
    render() draws it fresh every time)."""
    TOP     = auto()
    CONTENT = auto()
    BOTTOM  = auto()


@dataclass
class Border:
    # None means "use make_box()'s terminal-aware glyphs for whoever's
    # viewing this" (Unicode box-drawing for ANSI, PETSCII line-drawing
    # for C64 clients, ASCII fallback otherwise) -- only an explicit
    # character falls back to a plain hand-rolled box with that literal
    # character instead. See render_lines().
    char: str | None = None
    role: BorderRole = BorderRole.CONTENT


def _justify_text(text: str, width: int, justification: Justification) -> str:
    if justification == Justification.LEFT or len(text) >= width:
        return text
    if justification == Justification.CENTER:
        return text.center(width)
    if justification == Justification.RIGHT:
        return text.rjust(width)
    if justification == Justification.EXPAND:
        return _expand_justify(text, width)
    return text  # PACK/INDENT/UN_INDENT never persist as a style


def _expand_justify(text: str, width: int) -> str:
    """Full-justify `text` to exactly `width` columns by distributing extra
    spaces between words. Single-word lines, or text that's already too
    wide to expand, are returned unchanged."""
    words = text.split()
    if len(words) < 2:
        return text
    total_word_len = sum(len(w) for w in words)
    gaps = len(words) - 1
    total_spaces = width - total_word_len
    if total_spaces < gaps:
        return text
    base, extra = divmod(total_spaces, gaps)
    out = words[0]
    for i, word in enumerate(words[1:], start=1):
        out += ' ' * (base + (1 if i <= extra else 0)) + word
    return out


@dataclass
class Line:
    text: str = ''
    justification: Justification = Justification.LEFT
    line_flag: LineFlag = LineFlag.MUTABLE
    border: Border | None = None

    def render(self, width: int) -> str:
        """Return this line padded/justified (and, if a Border tagged it,
        boxed) to `width` columns -- screen-width independent: storing
        *how* to justify, rather than baking padding into .text, means
        the same Line renders correctly for two players with different
        screen widths -- and the same reasoning extends to Border below."""
        if self.border is not None:
            return self._render_bordered(width)
        return _justify_text(self.text, width, self.justification)

    def _render_bordered(self, width: int) -> str:
        """Standalone (no ctx) fallback: a plain ASCII box using the
        stored character, or '-' if none was given. Used when a bordered
        Line is rendered outside of render_lines()'s ctx-aware, whole-
        buffer pass (e.g. a partial selection cut off mid-box) -- see
        that function's own docstring for the normal, preferred path."""
        width = max(width, 4)
        char = self.border.char or '-'
        if self.border.role in (BorderRole.TOP, BorderRole.BOTTOM):
            return f'+{char * (width - 2)}+'
        inner_width = width - 4  # "| " + text + " |"
        rows = wrap_text(self.text, max(inner_width, 1)) or ['']
        return '\n'.join(
            f'| {_justify_text(r, inner_width, self.justification).ljust(inner_width)} |'
            for r in rows
        )

    def to_dict(self) -> dict:
        """JSON-safe representation for persisting saved content (see
        serialize_lines()/deserialize_lines()) -- only non-default fields
        are included, so plain unformatted lines stay compact."""
        d: dict = {'text': self.text}
        if self.justification != Justification.LEFT:
            d['justification'] = self.justification.name
        if self.line_flag != LineFlag.MUTABLE:
            d['line_flag'] = self.line_flag.name
        if self.border is not None:
            border_d: dict = {'role': self.border.role.name}
            if self.border.char is not None:
                border_d['char'] = self.border.char
            d['border'] = border_d
        return d

    @staticmethod
    def from_dict(d: dict) -> 'Line':
        border = None
        if 'border' in d:
            b = d['border']
            border = Border(char=b.get('char'), role=BorderRole[b.get('role', 'CONTENT')])
        return Line(
            text=d.get('text', ''),
            justification=Justification[d.get('justification', 'LEFT')],
            line_flag=LineFlag[d.get('line_flag', 'MUTABLE')],
            border=border,
        )


def serialize_lines(lines: list[Line]) -> list[dict]:
    """Structured form of a Line list, JSON-safe -- what callers persisting
    saved content (e.g. news.py's item['body']) should store, instead of
    pre-rendered strings, so it can be re-rendered per-viewer later via
    render_lines() rather than being frozen at the author's own screen
    width/terminal type."""
    return [line.to_dict() for line in lines]


def deserialize_lines(data: list) -> list[Line]:
    """Inverse of serialize_lines(). Also accepts plain strings for each
    entry (old-format saved content from before Lines were persisted
    structurally) as a migration path -- those become plain, unformatted
    Lines, same as they always rendered."""
    return [Line.from_dict(d) if isinstance(d, dict) else Line(text=d) for d in data]


def render_lines(lines: list[Line], ctx, width: int) -> list[str]:
    """Render a full list of Lines to display strings, one output string
    per input Line (same length in and out -- callers can freely index
    into the result with whatever range they actually wanted, even a
    slice that only partly overlaps a box).

    A contiguous TOP/CONTENT.../BOTTOM run with no explicit Border.char
    is rendered as one batch via make_box() -- the real, terminal-aware
    box-drawing this server already has for every other ANSI/PETSCII
    client (Unicode box-drawing, PETSCII line-drawing, or ASCII fallback,
    picked from ctx.player.client_settings). Everything else (including a
    Border run that DID get an explicit character, or a partial/orphaned
    box fragment) falls back to each Line's own .render(width) -- see
    Line._render_bordered()'s docstring.
    """
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if (line.border is not None and line.border.role == BorderRole.TOP
                and line.border.char is None):
            j = i + 1
            content = []
            while j < n and lines[j].border is not None and lines[j].border.role == BorderRole.CONTENT:
                content.append(lines[j])
                j += 1
            has_bottom = j < n and lines[j].border is not None and lines[j].border.role == BorderRole.BOTTOM
            inner_width = max(width - 4, 1)
            # Word-wrap each content Line to the box's inner width first --
            # make_box() only pads, never wraps, so an over-long line would
            # otherwise shove the right border past the screen edge and the
            # terminal would wrap it, breaking the frame. A Line that wraps
            # to several physical rows still collapses back to ONE output
            # string (newline-joined) so render_lines() keeps its one-string-
            # per-input-Line contract (callers index the result by Line #).
            texts: list[str] = []
            row_counts: list[int] = []
            for ln in content:
                wrapped = wrap_text(ln.text, inner_width) or ['']
                wrapped = [_justify_text(w, inner_width, ln.justification) for w in wrapped]
                texts.extend(wrapped)
                row_counts.append(len(wrapped))
            settings = ctx.player.client_settings
            boxed = make_box(texts, width=width, codec=codec_for_settings(settings),
                             border_style=border_style_for_ctx(ctx))
            out.append(boxed[0])
            body = boxed[1:1 + len(texts)]
            k = 0
            for count in row_counts:
                out.append('\n'.join(body[k:k + count]))
                k += count
            if has_bottom:
                out.append(boxed[-1])
                i = j + 1
            else:
                i = j
            continue
        out.append(line.render(width))
        i += 1
    return out


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