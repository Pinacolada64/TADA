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
  - .E Edit subcommands (Ryan's addition, not in the gist at all): '.e
    m'ove/'c'opy <range> <destination>, '.e l'ist <range> (delegates
    straight to _cmd_list()), and multi-level '.e u'ndo/'r'edo/'s'how --
    Editor.checkpoint() pushes a deep-copied snapshot onto an undo stack
    before every real buffer mutation (typing a line, .D/.E/.M/.C/.N/.J's
    text-mutating modes, .G Get File), capped at _MAX_UNDO_DEPTH; undo/
    redo swap snapshots between two stacks, clearing the redo stack on
    any new change, same as any standard undo/redo history. A completely
    bare '.e' (nothing typed at all) prompts for which of these you want
    instead of guessing "edit the last line."

Not ported (out of scope for this pass, left as TODO.md follow-ups):
  - .T Tagline -- was only a loose module-level function in the gist,
    never wired into either dispatch table.
  - .Q(uoter) reply-quoting IS wired up, just one layer up rather than
    as a dot-command here: commands/board_reply.py's _reply_with_quote()
    seeds run_editor()'s initial_lines with the quoted text (plus a
    "<author> wrote:" attribution line), each tagged LineFlag.QUOTE.
    Every place this module skips LineFlag.IMMUTABLE lines (.E Edit/
    Delete/Search&Replace/Justify/Move/Copy -- see each one's own
    docstring) treats QUOTE the same way: any non-MUTABLE line is
    protected, so a reply can't be edited into claiming the original
    poster said something they didn't (Ryan's explicit call). A preview
    of the quote is also shown as a titled box (formatting.titled_box())
    before the editor opens, so the player sees it and confirms it
    before it's committed to the buffer.
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
        # body is the new (possibly empty) list of serialized Line dicts
        # to save (formatting.serialize_lines()'s output) -- Justification/
        # Border are NOT baked into flat text; a caller persisting this
        # (e.g. news.py) should re-render it per-viewer at display time via
        # formatting.render_lines(formatting.deserialize_lines(body), ...)
        # rather than storing pre-rendered strings, so a centered/bordered
        # post displays correctly regardless of who's reading it or on
        # what terminal width/type -- see formatting.py's own docstring
        # section on the Line model for why.
        ...

The Line/Border/Justification/LineFlag/BorderRole data model itself lives in
formatting.py, not here -- news.py (and any future consumer of saved,
structured text) needs it without depending on this whole dot-command
editor module, so it moved to formatting.py's existing terminal-rendering
layer alongside make_box()/codec_for_settings(), which render_lines() (this
module's old _render_buffer_lines()) is built on.
"""
from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field
from enum import Enum, Flag, auto
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Union, TYPE_CHECKING

from flags import PlayerFlags
from formatting import (
    Border, BorderRole, Justification, Line, LineFlag,
    _justify_text, render_lines, serialize_lines,
)

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


_JUSTIFY_LETTERS = {
    'l': Justification.LEFT, 'c': Justification.CENTER,
    'r': Justification.RIGHT, 'e': Justification.EXPAND,
    'p': Justification.PACK, 'i': Justification.INDENT,
    'u': Justification.UN_INDENT,
}

_DEFAULT_INDENT = 4
_MAX_UNDO_DEPTH = 20


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
    # Player-facing prose for '.H <key>' -- kept separate from
    # function_name's own docstring (implementation notes for whoever's
    # reading the code, same convention as every other command's
    # commands/base_command.py Help dataclass keeping summary/description
    # apart from the code). Paragraphs are separated by a blank line;
    # _cmd_help() collapses each paragraph's own internal line breaks
    # (wrapped to fit this source file, not a player's screen) but keeps
    # paragraph breaks intact.
    help_text: str = ''


def _screen_width(ctx: 'GameContext') -> int:
    return getattr(getattr(ctx.player, 'client_settings', None), 'screen_columns', 80)


def process_line_range_string(range_str: str, buffer: Buffer,
                               default: DefaultLineRange = DefaultLineRange.ALL_LINES) -> LineRange:
    """Parse an ed-style line range: `x`, `x-`, `x-y`, `-y`, `x-+n`, or
    empty (resolved against `default`). Out-of-range or reversed values
    are clamped into what the buffer actually has, rather than left
    invalid -- e.g. '99' against a 5-line buffer becomes line 5, not
    line 99.

    `x-+n` is a relative end: `n` more lines *from* `x`, e.g. '1-+5' is
    lines 1-6 (six lines: x plus n more), same idea as ed/vi's own
    `,+n` relative addressing. Only the end may be relative -- a
    relative start has no fixed reference point to be relative to.
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
                if end_str.startswith('+'):
                    end = start + int(end_str[1:])
                else:
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
        # Multi-level undo/redo -- checkpoint() is called right before
        # every operation that actually changes buffer content (not on
        # validation failures/no-ops), pushing a snapshot onto
        # _undo_stack and clearing _redo_stack (a new change always
        # invalidates whatever was redo-able, same as any standard
        # undo/redo history). '.E U'ndo/'.E R'edo move a snapshot between
        # the two stacks; '.E S'how lists both. See checkpoint() and
        # _cmd_edit_undo()/_cmd_edit_redo()/_cmd_edit_show_buffers().
        self._undo_stack: List[List[Line]] = []
        self._redo_stack: List[List[Line]] = []

        self.dot_command_table: List[DotCommand] = [
            DotCommand('a', 'Abort', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _cmd_abort,
                help_text="Discard everything you've typed and leave the editor. "
                          "You'll be asked to confirm first."),
            DotCommand('b', 'Border', DefaultLineRange.ALL_LINES,
                CommandFlags.ACCEPT_CHARACTER | CommandFlags.ACCEPT_LINE_RANGE, _cmd_border,
                help_text="Wrap a line range in a box. With no character given, uses your "
                          "terminal's own line-drawing style. Give a single character "
                          "(e.g. '.b *') to use that instead.\n\n"
                          "Examples:\n"
                          "  .b        Box the whole buffer\n"
                          "  .b 1-3    Box lines 1-3\n"
                          "  .b * 1-3  Box lines 1-3 with '*' for the border"),
            DotCommand('c', 'Columns', DefaultLineRange.NONE, CommandFlags.ACCEPT_NUMBERS, _cmd_columns,
                help_text="Show or change how many columns wide your lines can be. "
                          "Can't exceed your screen width.\n\n"
                          "Examples:\n"
                          "  .c      Show the current column width\n"
                          "  .c 40   Set column width to 40"),
            DotCommand('d', 'Delete', DefaultLineRange.LAST_LINE, CommandFlags.ACCEPT_LINE_RANGE, _cmd_delete,
                help_text="Delete a line or range of lines. Defaults to the last line if "
                          "no range is given.\n\n"
                          "Examples:\n"
                          "  .d      Delete the last line\n"
                          "  .d 3    Delete line 3\n"
                          "  .d 2-5  Delete lines 2 through 5"),
            DotCommand('e', 'Edit', DefaultLineRange.LAST_LINE,
                CommandFlags.ACCEPT_LINE_RANGE | CommandFlags.ACCEPT_SUBCOMMAND, _cmd_edit,
                help_text="Edit a line or range of lines, one at a time. You'll be shown "
                          "each line's current text and asked for new text -- press Enter "
                          "with nothing typed to leave a line unchanged, or type a single "
                          "'.' to stop early. A completely bare '.e' asks which of the "
                          "below you want, instead of guessing.\n\n"
                          "Subcommands -- '.e [m]ove'/'[c]opy' <range> <destination>: a "
                          "destination is the line number to insert before; immutable "
                          "lines in the range are skipped when moving (never when "
                          "copying, since the original is left in place either way). "
                          "Leave off the range and/or destination and you'll be prompted "
                          "for whichever's missing. "
                          "'.e [l]ist' <range> is the same as .L. '.e [u]ndo'/'[r]edo' "
                          "step back and forward through your recent changes (typing, "
                          "deleting, moving, etc.); '.e [s]how' lists what's on both "
                          "stacks.\n\n"
                          "Examples:\n"
                          "  .e            Edit the last line\n"
                          "  .e 3          Edit line 3\n"
                          "  .e 2-4        Edit lines 2 through 4, one at a time\n"
                          "  .e m 4-6 8    Move lines 4-6 to before line 8\n"
                          "  .e c 4-6 8    Copy lines 4-6 to before line 8\n"
                          "  .e l 4-6      List lines 4-6 (like .L 4-6)\n"
                          "  .e u          Undo your last change\n"
                          "  .e r          Redo what you just undid\n"
                          "  .e s          Show the undo/redo history"),
            DotCommand('f', 'Find', DefaultLineRange.ALL_LINES, CommandFlags.ACCEPT_LINE_RANGE, _cmd_find,
                help_text="Search for text in a line range (defaults to the whole "
                          "buffer). Matches are highlighted in the results.\n\n"
                          "Examples:\n"
                          "  .f      Search the whole buffer\n"
                          "  .f 2-5  Search only lines 2-5"),
            DotCommand('h', 'Help!', DefaultLineRange.NONE, CommandFlags.ACCEPT_CHARACTER, _cmd_help,
                help_text="Show this list, or '.h <letter>' for details on one command."),
            DotCommand('i', 'Insert', DefaultLineRange.NONE, CommandFlags.ACCEPT_NUMBERS, _cmd_insert,
                help_text="Insert new lines before a given line number, shifting "
                          "everything else down. With no number, toggles Insert mode "
                          "on/off (starting at the end of the buffer the first time). "
                          "While Insert mode is on, everything you type goes in at the "
                          "insertion point instead of being added to the end.\n\n"
                          "Examples:\n"
                          "  .i      Toggle Insert mode\n"
                          "  .i 3    Start inserting before line 3"),
            DotCommand('j', 'Justify', DefaultLineRange.NONE,
                CommandFlags.ACCEPT_CHARACTER | CommandFlags.ACCEPT_LINE_RANGE, _cmd_justify,
                help_text="Set how a line range is aligned: [l]eft, [c]enter, [r]ight, "
                          "[e]xpand (spread words to fill the line), [p]ack (collapse "
                          "extra spaces), [i]ndent, or [u]n-indent. With no range given, "
                          "sets the default for lines you type from now on -- it does NOT "
                          "change anything already on screen.\n\n"
                          "Examples:\n"
                          "  .j c 1-3   Center lines 1-3\n"
                          "  .j e 4     Expand line 4 to fill the line\n"
                          "  .j l       New lines from here on will be left-justified"),
            DotCommand('k', 'Search & Replace', DefaultLineRange.ALL_LINES,
                CommandFlags.ACCEPT_LINE_RANGE, _cmd_search_and_replace,
                help_text="Find and replace text within a line range (defaults to the "
                          "whole buffer).\n\n"
                          "Examples:\n"
                          "  .k      Replace throughout the buffer\n"
                          "  .k 2-5  Replace only within lines 2-5"),
            DotCommand('l', 'List', DefaultLineRange.ALL_LINES, CommandFlags.ACCEPT_LINE_RANGE, _cmd_list,
                help_text="List a line range (defaults to the whole buffer), with line "
                          "numbers.\n\n"
                          "Examples:\n"
                          "  .l      List everything\n"
                          "  .l 3-7  List lines 3 through 7"),
            DotCommand('n', 'New Text', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _cmd_new_text,
                help_text="Erase the whole buffer and start over, after confirming."),
            DotCommand('o', 'Line Numbers', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _cmd_line_numbers,
                help_text="Toggle whether line numbers are shown while you type."),
            DotCommand('q', 'Query', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _cmd_query,
                help_text="Show how many lines, characters, and words are in the buffer."),
            DotCommand('r', 'Read Text', DefaultLineRange.ALL_LINES, CommandFlags.ACCEPT_LINE_RANGE, _cmd_read,
                help_text="Display a line range (defaults to the whole buffer) without "
                          "line numbers -- handy for previewing exactly what will be "
                          "saved.\n\n"
                          "Examples:\n"
                          "  .r      Read everything\n"
                          "  .r 2-4  Read lines 2 through 4"),
            DotCommand('s', 'Save Text', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _cmd_save,
                help_text='Save your changes and leave the editor.'),
            DotCommand('u', 'Un-border', DefaultLineRange.ALL_LINES, CommandFlags.ACCEPT_LINE_RANGE, _cmd_unborder,
                help_text="Inverse of .B: remove a box from a line range. Un-boxing an "
                          "entire box removes its top/bottom rule lines too; un-boxing "
                          "only part of one leaves the rest of the outline in place.\n\n"
                          "Examples:\n"
                          "  .u        Un-box the whole buffer\n"
                          "  .u 1-3    Un-box lines 1-3"),
            DotCommand('v', 'Version', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _cmd_version,
                help_text="Show the editor's version."),
            DotCommand('#', 'Scale', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _cmd_scale,
                help_text="Show a ruler of column numbers, to help line things up.\n\n"
                          "Examples:\n"
                          "  .#      Ruler across your whole screen width\n"
                          "  .# 40   Ruler up to column 40"),
        ]
        self.privileged_commands: List[DotCommand] = [
            DotCommand('$', 'Directory', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _priv_directory,
                help_text='List files available for .G Get File and .& Read File. Admin only.'),
            DotCommand('p', 'Put File', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _priv_put_file,
                help_text="Save the buffer to a server-side file. If the name's taken, "
                          "you'll be asked to pick a [N]ew name, [R]eplace it, or "
                          "[A]bort. Admin only."),
            DotCommand('&', 'Read File', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _priv_read_file,
                help_text="Preview a server-side file's contents without changing the "
                          "buffer. Admin only."),
            DotCommand('g', 'Get File', DefaultLineRange.NONE, CommandFlags.IMMEDIATE, _priv_get_file,
                help_text='Append the contents of a server-side file to the end of the '
                          'buffer. Admin only.'),
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

    def checkpoint(self) -> None:
        """Push a snapshot of the buffer onto the undo stack, and clear
        the redo stack -- any new change invalidates whatever was
        previously redo-able. Capped at _MAX_UNDO_DEPTH so a very long
        session's history doesn't grow unbounded; the oldest snapshot is
        dropped first."""
        self._undo_stack.append(copy.deepcopy(self.buffer.lines))
        if len(self._undo_stack) > _MAX_UNDO_DEPTH:
            self._undo_stack.pop(0)
        self._redo_stack.clear()


# ---------------------------------------------------------------------------
# Dot-command implementations
# ---------------------------------------------------------------------------

async def _cmd_abort(editor: 'Editor', arg: str) -> Optional[str]:
    """Setting editor.result ends run_editor()'s dispatch loop; the buffer
    is simply discarded (not returned) -- see run_editor()'s own docstring."""
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
    rendered = render_lines(buffer.lines, editor.ctx, editor.column_width)
    out = [f'{i + 1:3}: {rendered[i]}' for i in buffer.line_slice(line_range)]
    await editor.ctx.send(out)
    return None


async def _cmd_read(editor: 'Editor', arg: str) -> Optional[str]:
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.ALL_LINES)
    rendered = render_lines(buffer.lines, editor.ctx, editor.column_width)
    out = [rendered[i] for i in buffer.line_slice(line_range)]
    await editor.ctx.send(out)
    return None


async def _cmd_delete(editor: 'Editor', arg: str) -> Optional[str]:
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.LAST_LINE)
    indices = list(buffer.line_slice(line_range))
    deletable = [i for i in indices if buffer.lines[i].line_flag == LineFlag.MUTABLE]
    skipped = len(indices) - len(deletable)
    if deletable:
        editor.checkpoint()
    for i in sorted(deletable, reverse=True):
        del buffer.lines[i]
    buffer.current_line = min(buffer.current_line, max(buffer.used_lines, 1))
    msg = f'Deleted {len(deletable)} line(s).'
    if skipped:
        msg += f' ({skipped} immutable line(s) skipped.)'
    await editor.ctx.send(msg)
    return None


_EDIT_SUBCOMMANDS = ('m', 'c', 'l', 'u', 'r', 's')


async def _cmd_edit(editor: 'Editor', arg: str) -> Optional[str]:
    """Any non-MUTABLE line (IMMUTABLE or QUOTE) is skipped entirely, not
    just left unchanged -- QUOTE is what commands/board_reply.py seeds a
    quoted message's lines with when composing a threaded-board reply,
    so the quote can't be edited into something the original poster
    never actually said (see that module and formatting.py's Line for
    the real, wired-up use of this, not just a reserved-for-later flag).

    Subcommands ('.e m'/'c'/'l'/'u'/'r'/'s') are dispatched here rather
    than through DOT_CMD_TABLE itself -- CommandFlags.ACCEPT_SUBCOMMAND
    is documentation only in this port (see that Flag's own docstring),
    not actually branched on by run_editor()'s dispatch loop. A bare
    '.e' (nothing typed after it at all) prompts for which subcommand
    instead of defaulting straight to editing the last line -- Ryan's
    call, so the subcommands are discoverable without needing '.h e'."""
    if not arg.strip():
        prompt = (f'Edit which? [E]dit lines, [M]ove, [C]opy, [L]ist, '
                  f'[U]ndo, [R]edo, [S]how buffers, or {editor.ctx.player.return_key} to abort')
        raw = await editor.ctx.prompt(prompt)
        if not raw:
            return None
        choice = raw.strip().lower()[:1]
        if choice == 'e':
            # No range prompt here -- the fallback edit-lines branch below
            # already defaults a blank range to the last line, same as a
            # plain bare '.e' typed outside this submenu would.
            arg = ''
        elif choice in _EDIT_SUBCOMMANDS:
            # Pass just the subcommand letter; each one prompts for
            # whatever it still needs (range/destination for m/c, nothing
            # more for l/u/r/s) -- see _cmd_edit_move_or_copy()'s own
            # docstring for why that logic lives there, not here.
            arg = choice
        else:
            await editor.ctx.send(f"Unrecognized choice '{raw}'.")
            return None

    parts = arg.strip().split(maxsplit=1)
    first = parts[0].lower() if parts else ''
    if first in _EDIT_SUBCOMMANDS:
        rest = parts[1] if len(parts) > 1 else ''
        if first == 'l':
            return await _cmd_list(editor, rest)
        if first == 'u':
            return await _cmd_edit_undo(editor)
        if first == 'r':
            return await _cmd_edit_redo(editor)
        if first == 's':
            return await _cmd_edit_show_buffers(editor)
        return await _cmd_edit_move_or_copy(editor, rest, move=(first == 'm'))

    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.LAST_LINE)
    await editor.ctx.send("Enter new text for each line. Blank leaves it unchanged; '.' alone stops.")
    checkpointed = False
    for i in buffer.line_slice(line_range):
        line = buffer.lines[i]
        if line.line_flag != LineFlag.MUTABLE:
            await editor.ctx.send(f'Line {i + 1} is immutable, skipping.')
            continue
        raw = await editor.ctx.prompt(f'{i + 1}: {line.text}')
        if raw is None or raw.strip() == '.':
            break
        if raw != '':
            if not checkpointed:
                editor.checkpoint()  # once per .E session, not per line
                checkpointed = True
            line.text = raw
    return None


async def _cmd_edit_move_or_copy(editor: 'Editor', rest: str, move: bool) -> Optional[str]:
    """Shared implementation for '.E m'ove and '.E c'opy: <range>
    <destination>, destination being the line number to insert before
    (1 to used_lines+1, the latter meaning "at the very end"). Move
    removes the source lines (skipping any non-MUTABLE ones, same as .D
    Delete); copy duplicates them via copy.deepcopy() -- Line and
    Border are both dataclasses, so two Lines must never share one
    mutable Border instance. Prompts interactively for whichever of
    <range>/<destination> wasn't already given on the command line --
    same behavior whether reached via '.e m 4-6 8' typed directly or via
    the bare-'.e' submenu, which just passes the subcommand letter alone."""
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None

    tokens = rest.split()
    range_str = tokens[0] if tokens else None
    dest_str = tokens[1] if len(tokens) > 1 else None

    if range_str is None:
        range_str = await editor.ctx.prompt('Which lines')
        if not range_str:
            return None
    if dest_str is None:
        dest_str = await editor.ctx.prompt('Destination line')
        if not dest_str:
            return None

    line_range = process_line_range_string(range_str, buffer, DefaultLineRange.ALL_LINES)
    try:
        dest = int(dest_str)
    except ValueError:
        await editor.ctx.send(f"Expected a line number, got '{dest_str}'.")
        return None
    dest = max(1, min(dest, buffer.used_lines + 1))

    source_indices = list(buffer.line_slice(line_range))
    if move:
        selected = [i for i in source_indices if buffer.lines[i].line_flag == LineFlag.MUTABLE]
    else:
        selected = source_indices
    skipped = len(source_indices) - len(selected)
    if not selected:
        await editor.ctx.send('Nothing to move.' if move else 'Nothing to copy.')
        return None

    editor.checkpoint()
    if move:
        moved = [buffer.lines[i] for i in selected]
        remaining = [ln for idx, ln in enumerate(buffer.lines) if idx not in selected]
        removed_before_dest = sum(1 for i in selected if i < dest - 1)
        insert_at = max(0, min(dest - 1 - removed_before_dest, len(remaining)))
        remaining[insert_at:insert_at] = moved
        buffer.lines = remaining
    else:
        copied = [copy.deepcopy(buffer.lines[i]) for i in selected]
        insert_at = max(0, min(dest - 1, len(buffer.lines)))
        buffer.lines[insert_at:insert_at] = copied

    buffer.current_line = min(buffer.current_line, max(buffer.used_lines, 1))
    verb = 'Moved' if move else 'Copied'
    msg = f'{verb} {len(selected)} line(s) to before line {dest}.'
    if skipped:
        msg += f' ({skipped} immutable line(s) skipped.)'
    await editor.ctx.send(msg)
    return None


async def _cmd_edit_undo(editor: 'Editor') -> Optional[str]:
    if not editor._undo_stack:
        await editor.ctx.send('Nothing to undo.')
        return None
    editor._redo_stack.append(copy.deepcopy(editor.buffer.lines))
    editor.buffer.lines = editor._undo_stack.pop()
    editor.buffer.current_line = min(editor.buffer.current_line, max(editor.buffer.used_lines, 1))
    await editor.ctx.send(f'Undone. ({len(editor._undo_stack)} more undo step(s) available.)')
    return None


async def _cmd_edit_redo(editor: 'Editor') -> Optional[str]:
    if not editor._redo_stack:
        await editor.ctx.send('Nothing to redo.')
        return None
    editor._undo_stack.append(copy.deepcopy(editor.buffer.lines))
    editor.buffer.lines = editor._redo_stack.pop()
    editor.buffer.current_line = min(editor.buffer.current_line, max(editor.buffer.used_lines, 1))
    await editor.ctx.send(f'Redone. ({len(editor._redo_stack)} more redo step(s) available.)')
    return None


def _buffer_preview(lines: List[Line]) -> str:
    if not lines:
        return '(empty)'
    first = lines[0].text.strip() or '(blank)'
    return f'{len(lines)} line(s), starts: "{first[:40]}"'


async def _cmd_edit_show_buffers(editor: 'Editor') -> Optional[str]:
    """List the undo/redo stacks (most recent first) so a player can see
    how many steps are available and roughly what each one holds, without
    having to undo/redo blindly to find a particular state."""
    out = [f'Current: {_buffer_preview(editor.buffer.lines)}', '']
    out.append(f'Undo history ({len(editor._undo_stack)} step(s), most recent first):')
    if editor._undo_stack:
        out += [f'  {i}: {_buffer_preview(snap)}'
                for i, snap in enumerate(reversed(editor._undo_stack), start=1)]
    else:
        out.append('  (none)')
    out.append('')
    out.append(f'Redo history ({len(editor._redo_stack)} step(s), most recent first):')
    if editor._redo_stack:
        out += [f'  {i}: {_buffer_preview(snap)}'
                for i, snap in enumerate(reversed(editor._redo_stack), start=1)]
    else:
        out.append('  (none)')
    await editor.ctx.send(out)
    return None


async def _cmd_insert(editor: 'Editor', arg: str) -> Optional[str]:
    """The actual line-insertion happens in run_editor()'s own dispatch
    loop, keyed off editor.mode & EditorMode.INSERT -- this function only
    sets buffer.current_line (the insertion point) and toggles the flag."""
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
    """Matched text is wrapped in [brackets] for display so the normal
    ctx.send() highlight-brackets pass colors it (formatting.py's
    highlight_brackets()) -- the buffer's actual .text is untouched, this
    is purely a display transform on the search results."""
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    line_range = process_line_range_string(arg, buffer, DefaultLineRange.ALL_LINES)
    search = await editor.ctx.prompt('Find what')
    if not search:
        await editor.ctx.send('Aborted.')
        return None
    pattern = re.compile(re.escape(search))
    hits = []
    for i in buffer.line_slice(line_range):
        text = buffer.lines[i].text
        if search in text:
            hits.append(f'{i + 1}:')
            hits.append(pattern.sub(lambda m: f'[{m.group(0)}]', text))
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
        if line.line_flag != LineFlag.MUTABLE or search not in line.text:
            continue
        count += line.text.count(search)
        line.text = line.text.replace(search, replacement)
    await editor.ctx.send(f"Replaced {count} occurrence{'s' if count != 1 else ''}.")
    return None


async def _cmd_justify(editor: 'Editor', arg: str) -> Optional[str]:
    """l/c/r/e set a persistent Line.justification style; p(ack)/i(ndent)/
    u(n-indent) are one-time text mutations instead -- there's nothing to
    "un-expand" since expand is never baked into .text to begin with."""
    parts = arg.strip().split(maxsplit=1)
    if not parts:
        await editor.ctx.send('Usage: .j <l|c|r|e|p|i|u> [[range]]')
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
    indices = [i for i in buffer.line_slice(line_range) if buffer.lines[i].line_flag == LineFlag.MUTABLE]

    if mode == Justification.PACK:
        for i in indices:
            buffer.lines[i].text = ' '.join(buffer.lines[i].text.split())
    elif mode == Justification.INDENT:
        raw = await editor.ctx.prompt(f'Indent by how many spaces? [[{_DEFAULT_INDENT}]]')
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


# [DONE 7/22/26] .B's inverse is now .U (_cmd_unborder, below _cmd_border).
#
# TODO(Ryan, 7/18/26, see TODO.md): .J with no range only sets the
# default justification for *future* typed lines (see _cmd_justify below),
# not whatever's on screen -- typing '.j c' right after '.b' to center the
# box you just made does nothing visible. Justification of already-boxed
# lines itself is correct (verified: render_lines() justifies
# each content Line at the box's inner width before boxing it) -- this is
# a real gap in .J's no-range default, not a rendering bug.
async def _cmd_border(editor: 'Editor', arg: str) -> Optional[str]:
    """Tags lines with a Border rather than baking box-drawing characters
    into .text (same reasoning as Justification: a box's width should
    track whoever's *viewing* it, not whatever column width was active
    when .B was typed). See render_lines() for how a None-char
    Border routes through formatting.make_box() for real terminal-aware
    glyphs, vs. Line._render_bordered()'s plain-ASCII fallback for an
    explicit character."""
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None
    parts = arg.strip().split(maxsplit=1)
    border_char = None
    range_str = arg.strip()
    if parts and len(parts[0]) == 1 and not parts[0].isdigit():
        border_char = parts[0]
        range_str = parts[1] if len(parts) > 1 else ''

    line_range = process_line_range_string(range_str, buffer, DefaultLineRange.ALL_LINES)
    indices = list(buffer.line_slice(line_range))
    if not indices:
        return None

    for i in indices:
        buffer.lines[i].border = Border(char=border_char, role=BorderRole.CONTENT)

    bottom = Line(border=Border(char=border_char, role=BorderRole.BOTTOM))
    top = Line(border=Border(char=border_char, role=BorderRole.TOP))
    buffer.lines.insert(indices[-1] + 1, bottom)  # after last content line
    buffer.lines.insert(indices[0], top)          # before first -- shifts
                                                    # everything from here
                                                    # on (incl. `bottom`)
                                                    # down by one, which is
                                                    # exactly where it
                                                    # should end up

    rendered = render_lines(buffer.lines, editor.ctx, editor.column_width)
    preview = range(indices[0], indices[0] + len(indices) + 2)
    await editor.ctx.send([rendered[i] for i in preview])
    return None


async def _cmd_unborder(editor: 'Editor', arg: str) -> Optional[str]:
    """Inverse of .B: clears the Border tag off a range's content lines
    and removes the adjacent synthetic TOP/BOTTOM marker lines .B
    inserted, but only once they're no longer guarding any bordered
    content -- see _is_role()'s use below.

    Un-bordering only *part* of a box (its first, last, or a middle
    line) leaves the rest of the box's TOP/BOTTOM markers in place,
    since some of its content is still bordered; only a full-range
    unborder (the common case, and .U's default with no range) actually
    removes the box outline.
    """
    buffer = editor.buffer
    if not buffer.lines:
        await editor.ctx.send('(buffer is empty)')
        return None

    line_range = process_line_range_string(arg.strip(), buffer, DefaultLineRange.ALL_LINES)
    indices = list(buffer.line_slice(line_range))
    if not indices:
        return None

    bordered = [i for i in indices
                if buffer.lines[i].border is not None
                and buffer.lines[i].border.role == BorderRole.CONTENT]
    if not bordered:
        await editor.ctx.send('(no bordered lines in that range)')
        return None

    editor.checkpoint()

    # Determine before clearing anything -- clearing .border on the
    # content lines would otherwise change what "adjacent bordered
    # content" means for this same check.
    #
    # A marker is only orphaned -- safe to remove -- if the range being
    # cleared reaches all the way to it AND there's no bordered content
    # left on the *other* side still relying on it. Un-boxing just the
    # first line of a multi-line box, for example, sits right up against
    # the real TOP marker, but the box's remaining (still-bordered)
    # content past `after` still needs that TOP -- checking only "is
    # `before` a TOP marker" without also checking `after` would remove
    # it anyway and leave that remaining content orphaned instead.
    before = bordered[0] - 1
    after  = bordered[-1] + 1

    def _is_role(i: int, role: BorderRole) -> bool:
        return 0 <= i < len(buffer.lines) and buffer.lines[i].border is not None \
            and buffer.lines[i].border.role == role

    remove_top    = _is_role(before, BorderRole.TOP) and not _is_role(after, BorderRole.CONTENT)
    remove_bottom = _is_role(after, BorderRole.BOTTOM) and not _is_role(before, BorderRole.CONTENT)

    for i in bordered:
        buffer.lines[i].border = None

    # Render at the still-current indices before any deletion shifts them
    # -- removing `before` (lower than every index in `bordered`) would
    # otherwise invalidate them for the send() below.
    rendered = [buffer.lines[i].render(editor.column_width) for i in bordered]

    # Highest index first so removing one doesn't shift the other's index.
    if remove_bottom:
        del buffer.lines[after]
    if remove_top:
        del buffer.lines[before]

    buffer.current_line = min(buffer.current_line, max(buffer.used_lines, 1))
    await editor.ctx.send(rendered)
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
        editor.checkpoint()
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
    out = [_format_help_line(match.command_key, match.command_text, editor.screen_width), '']
    out += _format_help_text(match.help_text)
    await editor.ctx.send(out)
    return None


def _format_help_text(help_text: str) -> List[str]:
    """Split a DotCommand's help_text into display lines: paragraphs
    (separated by a blank line in the source) get their own soft line
    breaks collapsed into one flowing line -- they're wrapped to fit
    this source file, not a player's screen, and ctx.send() word-wraps
    to the actual screen width on its own. An "Examples:" block is left
    exactly as authored (one example per line) instead, since those line
    breaks are deliberate, not source-wrapping."""
    if not help_text:
        return ['(no help available)']
    out: List[str] = []
    for i, paragraph in enumerate(help_text.split('\n\n')):
        if i > 0:
            out.append('')
        if paragraph.lstrip().startswith('Examples:'):
            out.extend(paragraph.split('\n'))
        else:
            out.append(' '.join(paragraph.split()))
    return out


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
    editor.checkpoint()
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
    text = '\n'.join(render_lines(buffer.lines, editor.ctx, editor.column_width))
    path.write_text(text + '\n')
    await editor.ctx.send(f'Saved to {safe_name}.')
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# Recovery files carry the writing session's activity_id/activity_label
# (set via run_editor()'s own params -- see each call site: mail.py,
# news.py, board.py, board_reply.py) so a later EDIT command or login-time
# prompt can say what the player was doing, not just that *something* was
# lost. There's no dispatch back into the original mail/post/reply flow
# yet (Ryan: "how to recover the session is to be determined") -- EDIT
# just hands the recovered text back to the player to resume or re-paste
# themselves.
def _recovery_dir() -> Path:
    import net_common
    base = getattr(net_common, 'run_server_dir', None) or Path('run') / 'server'
    directory = Path(base) / 'editor_recovery'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _user_files_dir(player_name: str) -> Path:
    """Per-player storage for EDIT <filename> (a general-purpose text
    file editor open to any player -- unlike .G/.P Get/Put's shared,
    admin-only run/server/editor_files/)."""
    import net_common
    base = getattr(net_common, 'run_server_dir', None) or Path('run') / 'server'
    safe_name = _sanitize_filename(player_name) or 'unknown'
    directory = Path(base) / 'user_files' / safe_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_recovery_file(ctx: 'GameContext', editor: 'Editor') -> Path:
    """Dump *editor*'s current (unsaved) buffer to a timestamped file
    under _recovery_dir(), structurally (formatting.serialize_lines()'s
    output -- same shape news.py/board.py store, so EDIT can reuse
    deserialize_lines()/render_lines() to show it back per-viewer).
    Called from simple_server.py's Server.graceful_shutdown() for any
    player caught mid-edit when a scheduled/immediate SHUTDOWN fires --
    their session is about to be torn down with no chance to '.s' Save
    themselves.
    """
    import datetime
    import json

    player_name = getattr(getattr(ctx, 'player', None), 'name', 'unknown')
    safe_name   = _sanitize_filename(player_name) or 'unknown'
    stamp       = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    path        = _recovery_dir() / f'{safe_name}-{stamp}.json'

    path.write_text(json.dumps({
        'player':         player_name,
        'saved_at':       datetime.datetime.now().isoformat(),
        'internal_id':    getattr(editor, 'activity_id', None),
        'activity_label': getattr(editor, 'activity_label', None),
        'lines':          serialize_lines(editor.buffer.lines),
    }, indent=2))
    return path


def find_recovery_file(player_name: str) -> Optional[Path]:
    """Most recent recovery file for *player_name*, if any -- filenames
    are `<safe_name>-<YYYYmmdd_HHMMSS>.json`, so lexical order is
    chronological order. Used by EDIT (bare, no filename) and the
    login-time "you were doing X -- resume?" prompt."""
    safe_name = _sanitize_filename(player_name) or 'unknown'
    matches = sorted(_recovery_dir().glob(f'{safe_name}-*.json'))
    return matches[-1] if matches else None


def delete_recovery_file(path: Path) -> None:
    """Discard a recovery file once its content has been resumed/handled."""
    path.unlink(missing_ok=True)


def load_recovery_file(path: Path) -> dict:
    """Parse a recovery file written by save_recovery_file()."""
    import json
    return json.loads(path.read_text())


async def run_editor(ctx: 'GameContext',
                      initial_lines: Optional[List[Union[str, Line]]] = None,
                      activity_id: Optional[str] = None,
                      activity_label: Optional[str] = None) -> Optional[List[dict]]:
    """Run an editing session. Returns the final buffer as a list of
    serialized Line dicts (formatting.serialize_lines()'s output --
    possibly empty, if the player deleted everything; Justification/Border
    are NOT baked into flat text, see the module docstring) on .S Save, or
    None on .A Abort or disconnect -- callers should treat None as "leave
    prior content untouched," matching commands/news.py's edit flow.

    `initial_lines` may be plain strings, pre-built Line objects (e.g.
    LineFlag.IMMUTABLE for content the player shouldn't be able to edit --
    see the module docstring's note on the not-yet-built reply-quoting
    feature), or formatting.deserialize_lines()'s output (a caller reloading
    previously-saved, serialized content -- deserialize it first).

    `activity_id`/`activity_label` identify what this session IS (e.g.
    'news_post' / 'posting news', 'mail_compose:Bob' / 'writing mail to
    Bob') -- stamped into a recovery file if the server goes down mid-edit
    (see save_recovery_file()) so EDIT or the login-time prompt can tell
    the player what they were doing, not just that something was lost.
    Callers that don't pass these just get an unlabeled recovery file.

    Typed lines that aren't a recognized dot-command (don't start with '.'
    or '/', or have no letter after it) are appended to the buffer --
    or, while .I Insert mode is on, inserted at the current insertion
    point instead. Classic ed/Image-BBS append-mode-by-default behavior.
    """
    editor = Editor(ctx, initial_lines)
    editor.activity_id = activity_id
    editor.activity_label = activity_label
    await ctx.send([
        "Line editor -- type text to add lines; commands start with '.' or '/'.",
        "'.h' for help, '.s' to save, '.a' to abort.",
    ])

    # WHEREAT (commands/whereat.py) reads ctx.client.virtual_location --
    # same convention as commands/news.py's 'Reading news' and
    # commands/new_player.py's 'Creating a character' -- restored via
    # finally so a disconnect or an exception mid-edit doesn't leave a
    # stale 'Editing Text' behind for whoever looks the player up next.
    previous_location = getattr(ctx.client, 'virtual_location', None)
    ctx.client.virtual_location = 'Editing Text'
    # Lets Server.graceful_shutdown() reach in and recovery-save this
    # session's live buffer if the process goes down mid-edit -- see
    # save_recovery_file() above.
    ctx.client.active_editor = editor
    try:
        return await _run_editor_loop(ctx, editor)
    finally:
        ctx.client.virtual_location = previous_location
        ctx.client.active_editor = None


async def _run_editor_loop(ctx: 'GameContext', editor: 'Editor') -> Optional[List[dict]]:
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
            # Disconnected mid-edit -- same unsaved-work-loss risk as a
            # server SHUTDOWN catching them (see save_recovery_file()),
            # just via a different trigger. There's no one left to notify
            # (the connection is already gone), so just persist quietly;
            # EDIT/the login-time prompt tell them about it next time in.
            if editor.buffer.lines:
                try:
                    save_recovery_file(ctx, editor)
                except Exception:
                    logging.exception('run_editor: failed to save recovery file on disconnect')
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
                return serialize_lines(editor.buffer.lines)
            if editor.result == 'abort':
                return None
            continue

        editor.checkpoint()
        new_line = Line(text=raw, justification=editor.justification, line_flag=LineFlag.MUTABLE)
        if editor.mode & EditorMode.INSERT:
            pos = max(1, min(buffer.current_line, buffer.used_lines + 1))
            buffer.lines.insert(pos - 1, new_line)
            buffer.current_line = pos + 1
        else:
            buffer.lines.append(new_line)
            buffer.current_line = buffer.used_lines
