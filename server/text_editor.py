"""text_editor.py — a ctx-aware, ed/Image-BBS-style line editor with
dot-commands (.L List, .D Delete, .E Edit, .I Insert, .J Justify, .B Border,
.G/.P/.&/.$ file ops (admin), .S Save, ...).

Architecture ported from Ryan's gist (a from-scratch rewrite, not the
never-merged `text_editor` git branch, which turned out to be missing this
work -- confirmed by searching every branch/PR/dangling commit this repo
still has): https://gist.github.com/Pinacolada64/b978ddc6dab0976db5f2ac45c6fcf998
That gist's class/flag design (CommandFlags, EditorMode, LineFlag,
Justification incl. PACK/INDENT/UN_INDENT, dot-leader .H Help, a Cursor
stub for a possible future full-screen editor) is kept close to as-given;
what changed:
  - Everything is async and ctx-aware -- one line at a time via
    ctx.prompt()/ctx.send(), not print()/input(). No raw keystrokes (see
    "Future work" below for why that's still worth doing later).
  - Every dot-command the gist left as a `print("...")` stub (Abort, Border,
    Columns, Delete, Edit, Find, New Text, Save, Search & Replace, plus all
    four privileged file commands) is filled in with a real implementation.
  - .I Insert: the gist's own docstring admitted this was unfinished
    ("if no line number is given, insert at... fixme: Finish this"). Design
    used here: `.i <n>` sets the insertion point to line n and turns Insert
    mode on; `.i` alone toggles it (defaulting to end-of-buffer the first
    time). While Insert mode is on, plain typed lines go in *before*
    buffer.current_line and advance it by one each time -- matching the
    very first text_editor.py prototype's own "I4:" / "I5:" example.
  - .J Justify: left/center/right/expand are persistent, render-time Line
    styles (formatting.py-style -- screen-width independent, exactly per
    the gist's own comment on why Justification lives on Line rather than
    being baked into .text). pack/indent/un-indent are one-time text
    mutations instead (there's nothing to "un-expand" if expand was never
    baked into .text in the first place).
  - Privileged commands (.$/.G/.P/.&) are permission-checked for real
    inside each function (ctx.player.query_flag(PlayerFlags.ADMIN)) --
    the gist's dispatch only ever gated them from .H Help's listing, not
    from actually being run. Filenames are sanitized against path
    traversal (matching combat/engine.py's statue-memorial precedent).
  - process_line_range_string()'s parsing logic is unchanged from the
    gist, but clamping is stricter (out-of-range/reversed ranges collapse
    to something valid instead of producing a LineRange that would index
    out of bounds).
  - .C Columns / .K Search & Replace / .W Word-wrap: not in the gist's
    dispatch table at all (or, for Columns, mislabeled with the wrong
    CommandFlags) -- Search & Replace is implemented for real since it was
    a genuine table entry; Word-wrap isn't (wasn't asked for -- but
    formatting.wrap_text() is right there if it's wanted later).

Not ported (out of scope for this pass, left as TODO.md follow-ups):
  - .T Tagline, .Q(uoter) reply-quoting a prior message -- both were only
    loose module-level functions in the gist, never wired into either
    dispatch table, and quoting needs a "what message is this replying to"
    concept this module doesn't have a source for yet. LineFlag.QUOTE and
    the IMMUTABLE-line skip logic (Edit/Delete/Justify) are implemented and
    ready for whenever that lands -- run_editor()'s initial_lines already
    accepts pre-built Line objects, not just plain strings, so a caller can
    seed an immutable quoted line today.
  - .U Undo -- same as above (a bare stub, never wired into any table).
  - Full-screen editing via raw keystrokes (Ryan's "capture raw keystrokes
    from a socket... blessed?" idea) -- the Cursor class is kept as a
    forward-compatible stub for this, but there's no raw-keystroke
    transport in network_context.py yet; this is a separate, larger
    future project, not part of this port.

Usage (see commands/news.py for the reference integration):
    body = await run_editor(ctx, initial_lines=existing_body)
    if body is None:
        # player aborted -- caller should leave prior content untouched
        ...
    else:
        # body is the new (possibly empty) list of plain strings to save --
        # Justification/Border formatting is already baked into the text.
        ...
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Union, TYPE_CHECKING

from flags import PlayerFlags

if TYPE_CHECKING:
    from network_context import GameContext

_VERSION = '2.0 (TADA port, 2026 -- architecture per Ryan\'s gist)'


# ---------------------------------------------------------------------------
# Enums / flags
# ---------------------------------------------------------------------------

class DefaultLineRange(Enum):
    """What an omitted line range defaults to for a given dot-command."""
    NONE       = 0  # command doesn't accept a line range at all
    ALL_LINES  = 1  # .L List
    FIRST_LINE = 2
    LAST_LINE  = 3  # .E Edit


class CommandFlags(Flag):
    """Documents what a dot-command accepts, mirrored from the gist.

    IMMEDIATE has no behavioral effect in this ctx/line-oriented port (it
    described skipping a "press Return to confirm" step in the old
    raw-keystroke model -- every command here already runs as soon as its
    whole line is submitted via ctx.prompt(), so there's no separate
    confirm step to skip). Kept for documentation parity with the gist.
    """
    IMMEDIATE         = 0
    ACCEPT_CHARACTER  = 1
    ACCEPT_LINE_RANGE = 2
    ACCEPT_NUMBERS    = 4
    ACCEPT_SUBCOMMAND = 8


class EditorMode(Flag):
    EDITING      = 0  # default
    INSERT       = auto()  # toggled by .I
    LINE_NUMBERS = auto()  # toggled by .O


class Justification(Enum):
    LEFT       = auto()
    CENTER     = auto()
    RIGHT      = auto()
    EXPAND     = auto()  # persistent render-time style (see Line.render)
    # PACK/INDENT/UN_INDENT are one-time text mutations, not persistent
    # styles -- see _cmd_justify -- but keeping them as Justification
    # members too matches the gist's dot-command vocabulary (.J p/i/u).
    PACK       = auto()
    INDENT     = auto()
    UN_INDENT  = auto()


class LineFlag(Enum):
    MUTABLE   = auto()  # default -- editable
    IMMUTABLE = auto()  # .E Edit / .D Delete / .J Justify skip these
    QUOTE     = auto()  # reserved for a future reply-quoting feature


_JUSTIFY_LETTERS = {
    'l': Justification.LEFT, 'c': Justification.CENTER,
    'r': Justification.RIGHT, 'e': Justification.EXPAND,
    'p': Justification.PACK, 'i': Justification.INDENT,
    'u': Justification.UN_INDENT,
}

_DEFAULT_INDENT = 4


# ---------------------------------------------------------------------------
# Line / LineRange / Buffer / Cursor
# ---------------------------------------------------------------------------

@dataclass
class LineRange:
    """A 1-based, inclusive line range. Either end may be None (only when
    the owning command takes no range at all -- see DefaultLineRange.NONE)."""
    start: Optional[int]
    end: Optional[int]


@dataclass
class Line:
    text: str = ''
    justification: Justification = Justification.LEFT
    line_flag: LineFlag = LineFlag.MUTABLE

    def render(self, width: int) -> str:
        """Return this line padded/justified to `width` columns per its
        stored Justification -- screen-width independent (see the module
        docstring / gist's own comment: storing *how* to justify, rather
        than baking padding into .text, means the same Line renders
        correctly for two players with different screen widths)."""
        text = self.text
        if self.justification == Justification.LEFT or len(text) >= width:
            return text
        if self.justification == Justification.CENTER:
            return text.center(width)
        if self.justification == Justification.RIGHT:
            return text.rjust(width)
        if self.justification == Justification.EXPAND:
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
class Cursor:
    """Row/column position within the buffer -- not used by this
    line-at-a-time port yet, kept as a forward-compatible stub for a
    possible future full-screen editor over raw keystrokes (see the
    module docstring's "Not ported" section)."""
    row: int = 1
    column: int = 1


@dataclass
class Buffer:
    lines: List[Line] = field(default_factory=list)
    current_line: int = 1
    cursor: Cursor = field(default_factory=Cursor)

    @property
    def used_lines(self) -> int:
        return len(self.lines)

    def line_slice(self, line_range: LineRange) -> range:
        """Convert a 1-based LineRange to a 0-based range() for indexing
        into self.lines, clamped to what's actually there."""
        if not self.lines:
            return range(0)
        start = max(1, line_range.start or 1) - 1
        end = min(line_range.end or self.used_lines, self.used_lines)
        if end < start + 1:
            end = start + 1
        return range(start, end)


# ---------------------------------------------------------------------------
# Dot-command dispatch metadata
# ---------------------------------------------------------------------------

DotFunc = Callable[['Editor', str], Awaitable[Optional[str]]]


@dataclass
class DotCommand:
    command_key: str
    command_text: str
    default_line_range: DefaultLineRange
    flags: CommandFlags
    function_name: DotFunc


def _screen_width(ctx: 'GameContext') -> int:
    return getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)


def process_line_range_string(range_str: str, buffer: Buffer,
                               default: DefaultLineRange = DefaultLineRange.ALL_LINES) -> LineRange:
    """Parse an ed-style line range: `x`, `x-`, `x-y`, `-y`, or empty
    (resolved against `default`). Out-of-range or reversed values are
    clamped into what the buffer actually has, rather than left invalid --
    e.g. '99' against a 5-line buffer becomes line 5, not line 99.
    """
    last = buffer.used_lines
    range_str = range_str.strip()

    if range_str:
        if '-' not in range_str:
            try:
                n = int(range_str)
            except ValueError:
                return LineRange(None, None)
            start = end = n
        else:
            start_str, end_str = range_str.split('-', 1)
            try:
                start = int(start_str) if start_str else 1
                end = int(end_str) if end_str else (last or 1)
            except ValueError:
                return LineRange(None, None)
    else:
        if default == DefaultLineRange.ALL_LINES:
            start, end = 1, (last or 1)
        elif default == DefaultLineRange.FIRST_LINE:
            start, end = 1, 1
        elif default == DefaultLineRange.LAST_LINE:
            start = end = (last or 1)
        else:
            return LineRange(None, None)

    ceiling = max(last, 1)
    start = min(max(start, 1), ceiling)
    end = min(max(end, 1), ceiling)
    if end < start:
        end = start
    return LineRange(start, end)


# ---------------------------------------------------------------------------
# Get/Put/Read/Directory file support (privileged)
# ---------------------------------------------------------------------------

_SAFE_FILENAME_RE = re.compile(r'[^A-Za-z0-9_.-]')


def _sanitize_filename(name: str) -> str:
    """Strip anything but alnum/underscore/dash/dot, and any leading dots
    (blocks '../' traversal and dotfiles) -- same spirit as combat/engine.py's
    statue-memorial filename sanitizing."""
    name = _SAFE_FILENAME_RE.sub('', name).lstrip('.')
    return name or 'unnamed'


def _editor_files_dir() -> Path:
    import net_common
    base = getattr(net_common, 'run_server_dir', None) or Path('run') / 'server'
    directory = Path(base) / 'editor_files'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def make_box(lines: List[str], width: int, border_char: str = '-') -> List[str]:
    """Wrap `lines` in a simple ASCII box, `width` columns wide overall
    (border included). Lines longer than the interior are truncated."""
    width = max(width, 4)
    inner_width = width - 4  # "| " + text + " |"
    out = [f'+{border_char * (width - 2)}+']
    for line in lines:
        text = line[:inner_width].ljust(inner_width)
        out.append(f'| {text} |')
    out.append(f'+{border_char * (width - 2)}+')
    return out


# ---------------------------------------------------------------------------
# Editor -- holds per-session state (mode, buffer, column width, the
# default justification for lines typed from here on) across the dispatch
# loop in run_editor(). Mirrors the gist's Editor class.
# ---------------------------------------------------------------------------

class Editor:
    def __init__(self, ctx: 'GameContext', initial_lines: Optional[List[Union[str, Line]]] = None):
        self.ctx = ctx
        self.mode = EditorMode.EDITING
        self.buffer = Buffer(lines=[
            line if isinstance(line, Line) else Line(text=line)
            for line in (initial_lines or [])
        ])
        if self.buffer.lines:
            self.buffer.current_line = self.buffer.used_lines
        self.screen_width = _screen_width(ctx)
        self.column_width = self.screen_width
        self.justification = Justification.LEFT  # default for newly typed lines
        self.result: Optional[str] = None  # set to 'save'/'abort' to end the session

        self.dot_command_table: List[DotCommand] = [
            DotCommand('a', 'Abort',            DefaultLineRange.NONE,       CommandFlags.IMMEDIATE, _cmd_abort),
            DotCommand('b', 'Border',            DefaultLineRange.ALL_LINES,  CommandFlags.ACCEPT_CHARACTER | CommandFlags.ACCEPT_LINE_RANGE, _cmd_border),
            DotCommand('c', 'Columns',           DefaultLineRange.NONE,       CommandFlags.ACCEPT_NUMBERS, _cmd_columns),
            DotCommand('d', 'Delete',            DefaultLineRange.LAST_LINE,  CommandFlags.ACCEPT_LINE_RANGE, _cmd_delete),
            DotCommand('e', 'Edit',              DefaultLineRange.LAST_LINE,  CommandFlags.ACCEPT_LINE_RANGE, _cmd_edit),
            DotCommand('f', 'Find',              DefaultLineRange.ALL_LINES,  CommandFlags.ACCEPT_LINE_RANGE, _cmd_find),
            DotCommand('h', 'Help!',             DefaultLineRange.NONE,       CommandFlags.ACCEPT_CHARACTER, _cmd_help),
            DotCommand('i', 'Insert',            DefaultLineRange.NONE,       CommandFlags.ACCEPT_NUMBERS, _cmd_insert),
            DotCommand('j', 'Justify',           DefaultLineRange.NONE,       CommandFlags.ACCEPT_CHARACTER | CommandFlags.ACCEPT_LINE_RANGE, _cmd_justify),
            DotCommand('k', 'Search & Replace',  DefaultLineRange.ALL_LINES,  CommandFlags.ACCEPT_LINE_RANGE, _cmd_search_and_replace),
            DotCommand('l', 'List',              DefaultLineRange.ALL_LINES,  CommandFlags.ACCEPT_LINE_RANGE, _cmd_list),
            DotCommand('n', 'New Text',          DefaultLineRange.NONE,       CommandFlags.IMMEDIATE, _cmd_new_text),
            DotCommand('o', 'Line Numbers',      DefaultLineRange.NONE,       CommandFlags.IMMEDIATE, _cmd_line_numbers),
            DotCommand('q', 'Query',             DefaultLineRange.NONE,       CommandFlags.IMMEDIATE, _cmd_query),
            DotCommand('r', 'Read Text',         DefaultLineRange.ALL_LINES,  CommandFlags.ACCEPT_LINE_RANGE, _cmd_read),
            DotCommand('s', 'Save Text',         DefaultLineRange.NONE,       CommandFlags.IMMEDIATE, _cmd_save),
            DotCommand('v', 'Version',           DefaultLineRange.NONE,       CommandFlags.IMMEDIATE, _cmd_version),
            DotCommand('#', 'Scale',             DefaultLineRange.NONE,       CommandFlags.IMMEDIATE, _cmd_scale),
        ]
        self.privileged_commands: List[DotCommand] = [
            DotCommand('$', 'Directory',  DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _priv_directory),
            DotCommand('p', 'Put File',   DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _priv_put_file),
            DotCommand('&', 'Read File',  DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _priv_read_file),
            DotCommand('g', 'Get File',   DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _priv_get_file),
        ]

    def is_admin(self) -> bool:
        return bool(self.ctx.player.query_flag(PlayerFlags.ADMIN))

    def find_command(self, key: str) -> Optional[DotCommand]:
        for cmd in self.dot_command_table:
            if cmd.command_key == key:
                return cmd
        for cmd in self.privileged_commands:
            if cmd.command_key == key:
                return cmd
        return None


# ---------------------------------------------------------------------------
# Dot-command implementations
# ---------------------------------------------------------------------------

async def _cmd_abort(editor: 'Editor', arg: str) -> Optional[str]:
    raw = await editor.ctx.prompt('Abort and discard changes? (Y/N)')
    if raw and raw.strip().upper() == 'Y':
        await editor.ctx.send('Aborted.')
        editor.result = 'abort'
        return editor.result
    await editor.ctx.send('Continuing.')
    return None


async def _cmd_save(editor: 'Editor', arg: str) -> Optional[str]:
    await editor.ctx.send('Saved.')
    editor.result = 'save'
    return editor.result


async def _cmd_list(editor: 'Editor', arg: str) -> Optional[str]:
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.ALL_LINES)
    out = []
    for i in buffer.line_slice(line_range):
        out.append(f'{i + 1:3}: {buffer.lines[i].render(editor.column_width)}')
    await editor.ctx.send(out)
    return None


async def _cmd_read(editor: 'Editor', arg: str) -> Optional[str]:
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.ALL_LINES)
    out = [buffer.lines[i].render(editor.column_width) for i in buffer.line_slice(line_range)]
    await editor.ctx.send(out)
    return None


async def _cmd_delete(editor: 'Editor', arg: str) -> Optional[str]:
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.LAST_LINE)
    indices = list(buffer.line_slice(line_range))
    deletable = [i for i in indices if buffer.lines[i].line_flag != LineFlag.IMMUTABLE]
    skipped = len(indices) - len(deletable)
    for i in sorted(deletable, reverse=True):
        del buffer.lines[i]
    buffer.current_line = min(buffer.current_line, max(buffer.used_lines, 1))
    msg = f'Deleted {len(deletable)} line(s).'
    if skipped:
        msg += f' ({skipped} immutable line(s) skipped.)'
    await editor.ctx.send(msg)
    return None


async def _cmd_edit(editor: 'Editor', arg: str) -> Optional[str]:
    """Edit a line (or range) one at a time. Blank Enter leaves a line
    unchanged; a lone '.' ends editing early. Immutable lines are skipped."""
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.LAST_LINE)
    await editor.ctx.send("Enter new text for each line. Blank leaves it unchanged; '.' alone stops.")
    for i in buffer.line_slice(line_range):
        line = buffer.lines[i]
        if line.line_flag == LineFlag.IMMUTABLE:
            await editor.ctx.send(f'Line {i + 1} is immutable, skipping.')
            continue
        raw = await editor.ctx.prompt(f'{i + 1}: {line.text}')
        if raw is None or raw.strip() == '.':
            break
        if raw != '':
            line.text = raw
    return None


async def _cmd_insert(editor: 'Editor', arg: str) -> Optional[str]:
    """`.i <n>` sets the insertion point to line n and turns Insert mode on;
    `.i` alone toggles it (defaulting to end-of-buffer). While on, plain
    typed lines go in before buffer.current_line and advance it by one."""
    buffer = editor.buffer
    arg = arg.strip()
    if arg:
        try:
            pos = int(arg)
        except ValueError:
            await editor.ctx.send(f"Expected a line number, got '{arg}'.")
            return None
        buffer.current_line = max(1, min(pos, buffer.used_lines + 1))
        editor.mode |= EditorMode.INSERT
    else:
        if not (editor.mode & EditorMode.INSERT):
            buffer.current_line = buffer.used_lines + 1
        editor.mode ^= EditorMode.INSERT

    if editor.mode & EditorMode.INSERT:
        await editor.ctx.send(f'Insert mode is now on, at line {buffer.current_line}.')
    else:
        await editor.ctx.send('Insert mode is now off.')
    return None


async def _cmd_find(editor: 'Editor', arg: str) -> Optional[str]:
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.ALL_LINES)
    search = await editor.ctx.prompt('Find what')
    if not search:
        await editor.ctx.send('Aborted.')
        return None
    hits = []
    for i in buffer.line_slice(line_range):
        if search in buffer.lines[i].text:
            hits.append(f'{i + 1}:')
            hits.append(buffer.lines[i].text)
    await editor.ctx.send(hits if hits else [f"No match for '{search}'."])
    return None


async def _cmd_search_and_replace(editor: 'Editor', arg: str) -> Optional[str]:
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.ALL_LINES)
    search = await editor.ctx.prompt('Find what')
    if not search:
        await editor.ctx.send('Aborted.')
        return None
    replacement = await editor.ctx.prompt('Replace with')
    if replacement is None:
        await editor.ctx.send('Aborted.')
        return None
    count = 0
    for i in buffer.line_slice(line_range):
        line = buffer.lines[i]
        if line.line_flag == LineFlag.IMMUTABLE or search not in line.text:
            continue
        count += line.text.count(search)
        line.text = line.text.replace(search, replacement)
    await editor.ctx.send(f"Replaced {count} occurrence{'s' if count != 1 else ''}.")
    return None


async def _cmd_justify(editor: 'Editor', arg: str) -> Optional[str]:
    """.J <mode> [range] -- l/c/r/e set a persistent per-line style;
    p(ack)/i(ndent)/u(n-indent) are one-time text edits instead (there's
    nothing to "un-expand" -- expand is never baked into .text to begin
    with). `.J <mode>` with no range changes the default for future typed
    lines rather than touching the buffer at all."""
    parts = arg.strip().split(maxsplit=1)
    if not parts:
        await editor.ctx.send('Usage: .j <l|c|r|e|p|i|u> [range]')
        return None
    mode = _JUSTIFY_LETTERS.get(parts[0][:1].lower())
    if mode is None:
        await editor.ctx.send(f"Unknown justification '{parts[0]}'. Use l, c, r, e, p, i, or u.")
        return None
    range_str = parts[1] if len(parts) > 1 else ''

    if not range_str:
        editor.justification = mode if mode in (
            Justification.LEFT, Justification.CENTER, Justification.RIGHT, Justification.EXPAND,
        ) else editor.justification
        await editor.ctx.send(f'Future lines will be {mode.name.lower()}-justified.')
        return None

    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(range_str, buffer, DefaultLineRange.ALL_LINES)
    indices = [i for i in buffer.line_slice(line_range) if buffer.lines[i].line_flag != LineFlag.IMMUTABLE]

    if mode == Justification.PACK:
        for i in indices:
            buffer.lines[i].text = ' '.join(buffer.lines[i].text.split())
    elif mode == Justification.INDENT:
        raw = await editor.ctx.prompt(f'Indent by how many spaces? [{_DEFAULT_INDENT}]')
        amount = int(raw) if raw and raw.strip().isdigit() else _DEFAULT_INDENT
        for i in indices:
            buffer.lines[i].text = ' ' * amount + buffer.lines[i].text
    elif mode == Justification.UN_INDENT:
        for i in indices:
            buffer.lines[i].text = buffer.lines[i].text.lstrip(' ')
    else:
        for i in indices:
            buffer.lines[i].justification = mode

    await editor.ctx.send([buffer.lines[i].render(editor.column_width) for i in indices])
    return None


async def _cmd_border(editor: 'Editor', arg: str) -> Optional[str]:
    """.B [char] [range] -- wrap a line range in an ASCII box. An optional
    single border character may be given (default '-')."""
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    parts = arg.strip().split(maxsplit=1)
    border_char = '-'
    range_str = arg.strip()
    if parts and len(parts[0]) == 1 and not parts[0].isdigit():
        border_char = parts[0]
        range_str = parts[1] if len(parts) > 1 else ''

    line_range = process_line_range_string(range_str, buffer, DefaultLineRange.ALL_LINES)
    indices = list(buffer.line_slice(line_range))
    width = editor.column_width
    inner_width = max(width - 4, 1)
    rendered = [buffer.lines[i].render(inner_width) for i in indices]
    boxed = [Line(text=t) for t in make_box(rendered, width=width, border_char=border_char)]

    start = indices[0]
    end = indices[-1] + 1
    buffer.lines[start:end] = boxed
    await editor.ctx.send([ln.text for ln in boxed])
    return None


async def _cmd_columns(editor: 'Editor', arg: str) -> Optional[str]:
    arg = arg.strip()
    if not arg:
        await editor.ctx.send(f'Column width is set to {editor.column_width} characters.')
        return None
    try:
        new_width = int(arg)
    except ValueError:
        await editor.ctx.send(f"Invalid column width: '{arg}'. Please enter a number.")
        return None
    if new_width > editor.screen_width:
        await editor.ctx.send(f'Column width cannot exceed {editor.screen_width} characters.')
        return None
    if new_width < 1:
        await editor.ctx.send('Column width cannot be less than 1 character.')
        return None
    editor.column_width = new_width
    await editor.ctx.send(f'Column width set to {new_width} characters.')
    return None


async def _cmd_new_text(editor: 'Editor', arg: str) -> Optional[str]:
    raw = await editor.ctx.prompt('Erase buffer? (Y/N)')
    if raw and raw.strip().upper() == 'Y':
        editor.buffer = Buffer()
        await editor.ctx.send('Erased text.')
    else:
        await editor.ctx.send('Cancelled.')
    return None


async def _cmd_line_numbers(editor: 'Editor', arg: str) -> Optional[str]:
    editor.mode ^= EditorMode.LINE_NUMBERS
    on = bool(editor.mode & EditorMode.LINE_NUMBERS)
    await editor.ctx.send(f"Line numbers are now {'on' if on else 'off'}.")
    return None


async def _cmd_query(editor: 'Editor', arg: str) -> Optional[str]:
    buffer = editor.buffer
    chars = sum(len(ln.text) for ln in buffer.lines)
    words = sum(len(ln.text.split()) for ln in buffer.lines)
    await editor.ctx.send([
        f'Total lines used: {buffer.used_lines}',
        f'Total characters: {chars}',
        f'Total words: {words}',
    ])
    return None


async def _cmd_version(editor: 'Editor', arg: str) -> Optional[str]:
    await editor.ctx.send(f'Text editor version {_VERSION}.')
    return None


async def _cmd_scale(editor: 'Editor', arg: str) -> Optional[str]:
    """Show a ruler of screen columns, to help align text."""
    width = editor.screen_width
    if arg.strip().isdigit():
        width = min(width, int(arg.strip()))
    tens = ''.join(str((i // 10) % 10) if i % 10 == 0 else ' ' for i in range(1, width + 1))
    ones = ''.join(str(i % 10) for i in range(1, width + 1))
    await editor.ctx.send([tens, ones])
    return None


def _format_help_line(command_key: str, command_text: str, screen_width: int) -> str:
    """Dot-leader help line: '.a .......... Abort'"""
    left = f'.{command_key} '
    right = f' {command_text}'
    dot_count = max(1, screen_width - len(left) - len(right))
    return f"{left}{'.' * dot_count}{right}"


async def _cmd_help(editor: 'Editor', arg: str) -> Optional[str]:
    arg = arg.strip().lstrip('./')
    commands = list(editor.dot_command_table)
    if editor.is_admin():
        commands += editor.privileged_commands

    if not arg:
        out = [_format_help_line(cmd.command_key, cmd.command_text, editor.screen_width) for cmd in commands]
        await editor.ctx.send(out)
        return None

    match = next((cmd for cmd in commands if cmd.command_key == arg.lower()), None)
    if match is None:
        await editor.ctx.send(f'Unknown command: .{arg}')
        return None
    doc = (match.function_name.__doc__ or '').strip()
    await editor.ctx.send([
        _format_help_line(match.command_key, match.command_text, editor.screen_width),
        doc or '(no help available)',
    ])
    return None


# ---------------------------------------------------------------------------
# Privileged (admin-only) file commands
# ---------------------------------------------------------------------------

async def _priv_directory(editor: 'Editor', arg: str) -> Optional[str]:
    """List files available for .G Get File / .& Read File."""
    if not editor.is_admin():
        await editor.ctx.send('You lack the authority to do that.')
        return None
    files = sorted(p.name for p in _editor_files_dir().iterdir() if p.is_file())
    await editor.ctx.send(['Files available:'] + [f'  {name}' for name in files] if files else ['(no files available)'])
    return None


async def _priv_get_file(editor: 'Editor', arg: str) -> Optional[str]:
    """Append the contents of a server-side text file to the end of the
    buffer. Files live in run/server/editor_files/ -- filenames are
    sanitized, there's no way to escape that directory."""
    if not editor.is_admin():
        await editor.ctx.send('You lack the authority to do that.')
        return None
    directory = _editor_files_dir()
    raw_name = arg.strip() or await editor.ctx.prompt('Get which file')
    if not raw_name:
        await editor.ctx.send('Aborted.')
        return None
    safe_name = _sanitize_filename(raw_name)
    path = directory / safe_name
    if not path.is_file():
        await editor.ctx.send(f"No such file '{safe_name}'.")
        return None
    text_lines = path.read_text(errors='replace').splitlines()
    editor.buffer.lines.extend(Line(text=t) for t in text_lines)
    editor.buffer.current_line = editor.buffer.used_lines
    await editor.ctx.send(f'{len(text_lines)} line(s) appended from {safe_name}.')
    return None


async def _priv_read_file(editor: 'Editor', arg: str) -> Optional[str]:
    """Preview a server-side text file's contents without touching the
    buffer."""
    if not editor.is_admin():
        await editor.ctx.send('You lack the authority to do that.')
        return None
    directory = _editor_files_dir()
    raw_name = arg.strip() or await editor.ctx.prompt('Read which file')
    if not raw_name:
        await editor.ctx.send('Aborted.')
        return None
    safe_name = _sanitize_filename(raw_name)
    path = directory / safe_name
    if not path.is_file():
        await editor.ctx.send(f"No such file '{safe_name}'.")
        return None
    await editor.ctx.send(path.read_text(errors='replace').splitlines())
    return None


async def _priv_put_file(editor: 'Editor', arg: str) -> Optional[str]:
    """Save the buffer to a server-side text file (justification baked in,
    per the editor's current column width). On a name collision, offers
    [N]ew name, [R]eplace, or [A]bort."""
    if not editor.is_admin():
        await editor.ctx.send('You lack the authority to do that.')
        return None
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    directory = _editor_files_dir()
    raw_name = arg.strip() or await editor.ctx.prompt('Save as filename')
    if not raw_name:
        await editor.ctx.send('Aborted.')
        return None
    safe_name = _sanitize_filename(raw_name)
    while True:
        path = directory / safe_name
        if not path.exists():
            break
        choice_raw = await editor.ctx.prompt(f"'{safe_name}' exists. [N]ew name, [R]eplace, [A]bort")
        choice = (choice_raw or 'a').strip().lower()[:1]
        if choice == 'r':
            break
        if choice == 'n':
            new_name = await editor.ctx.prompt('New filename')
            if not new_name:
                await editor.ctx.send('Aborted.')
                return None
            safe_name = _sanitize_filename(new_name)
            continue
        await editor.ctx.send('Aborted.')
        return None
    text = '\n'.join(ln.render(editor.column_width) for ln in buffer.lines)
    path.write_text(text + '\n')
    await editor.ctx.send(f'Saved to {safe_name}.')
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_editor(ctx: 'GameContext',
                      initial_lines: Optional[List[Union[str, Line]]] = None) -> Optional[List[str]]:
    """Run an editing session. Returns the final list of lines on .S Save
    (possibly empty, if the player deleted everything; justification/box
    formatting already baked into the text), or None on .A Abort or
    disconnect -- callers should treat None as "leave prior content
    untouched," matching commands/news.py's edit flow.

    `initial_lines` may be plain strings or pre-built Line objects (e.g.
    LineFlag.IMMUTABLE for content the player shouldn't be able to edit --
    see the module docstring's note on the not-yet-built reply-quoting
    feature).

    Typed lines that aren't a recognized dot-command (don't start with '.'
    or '/', or have no letter after it) are appended to the buffer --
    or, while .I Insert mode is on, inserted at the current insertion
    point instead. Classic ed/Image-BBS append-mode-by-default behavior.
    """
    editor = Editor(ctx, initial_lines)
    await ctx.send([
        "Line editor -- type text to add lines; commands start with '.' or '/'.",
        "'.h' for help, '.s' to save, '.a' to abort.",
    ])

    while True:
        buffer = editor.buffer
        if editor.mode & EditorMode.LINE_NUMBERS:
            prompt_text = f'{buffer.current_line}: '
        elif editor.mode & EditorMode.INSERT:
            prompt_text = f'Insert {buffer.current_line}: '
        else:
            prompt_text = ''
        raw = await ctx.prompt(prompt_text)
        if raw is None:
            return None  # disconnected mid-edit

        prefix = raw[0] if raw else ''
        letter = raw[1:2].lower() if len(raw) >= 2 else ''
        if prefix in ('.', '/') and letter:
            cmd = editor.find_command(letter)
            arg = raw[2:].strip()
            if cmd is None:
                await ctx.send(f"Unrecognized command '.{letter}'. Type '.h' for help.")
                continue
            await cmd.function_name(editor, arg)
            if editor.result == 'save':
                return [ln.render(editor.column_width) for ln in editor.buffer.lines]
            if editor.result == 'abort':
                return None
            continue

        if not raw:
            continue  # blank Enter with nothing typed -- ignore, don't add an empty line

        new_line = Line(text=raw, justification=editor.justification, line_flag=LineFlag.MUTABLE)
        if editor.mode & EditorMode.INSERT:
            pos = max(1, min(buffer.current_line, buffer.used_lines + 1))
            buffer.lines.insert(pos - 1, new_line)
            buffer.current_line = pos + 1
        else:
            buffer.lines.append(new_line)
            buffer.current_line = buffer.used_lines
