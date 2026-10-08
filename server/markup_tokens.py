"""markup_tokens.py — the |token| / !token! color-markup pattern, shared by
formatting.py (the encoders and width measuring), table.py and
menu_system.py, which keep no dependency on formatting.py.

'|red|word|reset|' colors 'word'. '!' works exactly like '|' --
'!red!word!reset!' -- on every terminal. It was first added for Commodore
(PETSCII) players, since '|' is an awkward Shift+- on that keyboard; text
a Commodore player writes with '!' (mail, posts, news, say) now renders
the same for readers on any terminal.

Because '!' is everyday punctuation ("Welcome, Alice!", "PILLAGE!"), it
only counts as a delimiter around a real token name (TOKEN_NAMES) --
"Wow!great!" is left alone, where '|great|' would still be a (logged,
unknown) token. The two delimiters can't be mixed in one token ('|red!'
is just text). A doubled delimiter is an escape that displays the
markup instead of applying it: '||red||' shows as '|red|', '!!red!!' as
'!red!'. An optional ':count' repeats a token ('|tab:3|').

Match groups: escaped form -- d (the delimiter), etoken, ecount; real
form -- d2, token, count.
"""
from __future__ import annotations

import re

# Every name any encoder resolves: formatting.ANSI_COLOR_CODES and
# PETSCII_CONTROL_CODES keys, plus 'tab' (formatting._expand_tab_tokens()).
# tests/test_markup_bang_everywhere.py checks this stays in sync.
TOKEN_NAMES = frozenset({
    'black', 'blue', 'bold', 'brown', 'clear', 'command', 'cursor_down',
    'cursor_left', 'cursor_right', 'cursor_up', 'cyan', 'dark_gray', 'delete',
    'dim', 'green', 'heading', 'home', 'insert', 'light_blue', 'light_cyan',
    'light_gray', 'light_green', 'light_red', 'light_white', 'light_yellow',
    'lowercase', 'magenta', 'mid_gray', 'orange', 'purple', 'red', 'reset',
    'reverse_off', 'reverse_on', 'tab', 'uppercase', 'white', 'yellow',
})

# Longest first, so 'light_red' is tried before 'red'.
_NAMES = '|'.join(sorted(TOKEN_NAMES, key=len, reverse=True))

# After an opening '|' any name is accepted (unknown ones are left as-is
# and logged by the encoders, as before); after an opening '!' the
# lookahead requires a real name, its optional count, and the closing '!'.
TOKEN_PATTERN = (
    r'(?P<d>[|!])(?P=d)(?:(?<=\|)|(?=(?:' + _NAMES + r')(?::\d+)?!!))'
    r'(?P<etoken>[a-z_]+)(?::(?P<ecount>\d+))?(?P=d)(?P=d)'
    r'|(?P<d2>[|!])(?:(?<=\|)|(?=(?:' + _NAMES + r')(?::\d+)?!))'
    r'(?P<token>[a-z_]+)(?::(?P<count>\d+))?(?P=d2)'
)
TOKEN_RE = re.compile(TOKEN_PATTERN)


def escaped_literal(match: re.Match) -> str:
    """What an escaped match ('||red||', '!!tab:2!!') displays as:
    the single-delimiter markup, same delimiter ('|red|', '!tab:2!')."""
    d = match.group('d')
    literal = d + match.group('etoken')
    if match.group('ecount'):
        literal += ':' + match.group('ecount')
    return literal + d


def displayed(text: str) -> str:
    """*text* as it shows on screen: real tokens gone (zero width),
    escaped ones as their literal markup."""
    return TOKEN_RE.sub(lambda m: escaped_literal(m) if m.group('etoken') else '', text)


def strip_real(text: str) -> str:
    """Drop real tokens but keep escaped ones exactly as written, so text
    passed on still *displays* them rather than turning into markup."""
    return TOKEN_RE.sub(lambda m: m.group(0) if m.group('etoken') else '', text)
