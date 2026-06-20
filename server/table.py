"""table.py

Lightweight plain-text table generator.

Returns ``list[str]`` so output slots directly into ``ctx.send()``:

    t = Table(headers=["Name", "Class", "Level"])
    t.add_row(["Aldric", "Fighter", "5"])
    t.add_row(["Rhiannon", "Mage", "12"])
    await ctx.send(*t.render(width=ctx.player.client_settings.screen_columns))

Or without a ctx (defaults to 78 columns):

    for line in t.render():
        print(line)

Features
--------
- Optimal column widths: each column is as wide as its widest cell, then
  columns are widened proportionally when there is spare terminal space.
- Cell wrapping: content wider than the column width wraps within the cell;
  the logical row expands to as many visual lines as the tallest cell needs.
- Per-column alignment: LEFT (default), CENTER, RIGHT.
- Optional table title centred above the border.
- Optional footer row (e.g. "12 records").
- Pure Python, no external dependencies.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterable, List, Optional, Sequence

# Strip |pipe-token| color markers before measuring visible width.
_TOKEN_RE = re.compile(r'\|[a-z_]+\|')

def _visible_len(text: str) -> int:
    return len(_TOKEN_RE.sub('', text))


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class Align(Enum):
    LEFT   = auto()
    CENTER = auto()
    RIGHT  = auto()


@dataclass
class Border:
    """Line-drawing characters for table borders.

    Use one of the provided presets (``ASCII``, ``SINGLE``, ``DOUBLE``) or
    construct your own::

        b = Border(top_left="╒", top_right="╕", ...)
    """
    top_left:  str = "+"
    top_mid:   str = "+"
    top_right: str = "+"
    mid_left:  str = "+"
    cross:     str = "+"
    mid_right: str = "+"
    bot_left:  str = "+"
    bot_mid:   str = "+"
    bot_right: str = "+"
    h:         str = "-"
    v:         str = "|"


ASCII = Border()

SINGLE = Border(
    top_left="┌", top_mid="┬", top_right="┐",
    mid_left="├", cross="┼",   mid_right="┤",
    bot_left="└", bot_mid="┴", bot_right="┘",
    h="─", v="│",
)

DOUBLE = Border(
    top_left="╔", top_mid="╦", top_right="╗",
    mid_left="╠", cross="╬",   mid_right="╣",
    bot_left="╚", bot_mid="╩", bot_right="╝",
    h="═", v="║",
)

# PETSCII line-drawing characters.
# Use Unicode box-drawing chars (U+2500 block) — cbmcodecs2 maps these to
# the correct PETSCII graphics bytes (e.g. '┌' → byte 240, '─' → byte 192).
PETSCII = Border(
    top_left='┌', top_mid='┬', top_right='┐',
    mid_left='├', cross='┼',   mid_right='┤',
    bot_left='└', bot_mid='┴', bot_right='┘',
    h='─', v='│',
)

_BORDER_BY_NAME: dict = {
    'ascii':   ASCII,
    'single':  SINGLE,
    'double':  DOUBLE,
    'petscii': PETSCII,
}


@dataclass
class Column:
    """Header + display options for one column."""
    header:    str
    align:     Align = Align.LEFT
    min_width: int   = 1        # never narrower than this, even when squeezing
    max_width: int   = 0        # 0 = no cap


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fit(text: str, width: int, align: Align) -> str:
    """Pad/truncate *text* to exactly *width* visible characters.

    Token sequences (|yellow|…|reset|) are zero-width on screen, so padding
    is calculated from the visible length rather than len().
    """
    vis = _visible_len(text)
    if vis > width:
        # Strip tokens first so we can truncate visible chars cleanly.
        text = _TOKEN_RE.sub('', text)
        text = text[: max(width - 1, 0)] + ("…" if width > 1 else "")
        vis  = len(text)
    pad = width - vis
    if align == Align.RIGHT:
        return ' ' * pad + text
    if align == Align.CENTER:
        left_pad = pad // 2
        return ' ' * left_pad + text + ' ' * (pad - left_pad)
    return text + ' ' * pad


def _wrap_cell(text: str, width: int) -> list[str]:
    """Word-wrap *text* into lines of at most *width* visible chars."""
    if width <= 0:
        return [""]
    if not text:
        return [""]
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if paragraph == "":
            lines.append("")
        elif _visible_len(paragraph) <= width:
            # Visible content fits — don't wrap (tokens inflate len() artificially).
            lines.append(paragraph)
        else:
            lines.extend(textwrap.wrap(paragraph, width=width) or [""])
    return lines


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------

class Table:
    """Plain-text table with optional title, wrapping cells, per-column alignment.

    Parameters
    ----------
    headers : list of str  or  list of Column
        Column definitions.  Plain strings use default (left) alignment.
    title : str, optional
        Displayed centred above the table border.
    show_header : bool
        Whether to render the header row (default True).
    border : bool
        Whether to draw ``+--+`` borders (default True).
    padding : int
        Spaces of padding inside each cell on left and right (default 1).

    Example
    -------
    >>> t = Table(["Name", "HP", "Class"])
    >>> t.add_row(["Aldric",   "45", "Fighter"])
    >>> t.add_row(["Rhiannon", "72", "Mage"])
    >>> print("\\n".join(t.render(width=60)))
    +----------+----+---------+
    | Name     | HP | Class   |
    +----------+----+---------+
    | Aldric   | 45 | Fighter |
    | Rhiannon | 72 | Mage    |
    +----------+----+---------+
    """

    def __init__(
        self,
        headers:      Sequence[str | Column],
        title:        str    = "",
        show_header:  bool   = True,
        border:       bool   = True,
        border_style: Border = ASCII,
        padding:      int    = 1,
    ):
        self._columns: list[Column] = [
            c if isinstance(c, Column) else Column(header=c)
            for c in headers
        ]
        self._rows:    list[list[str]] = []
        self.title        = title
        self.show_header  = show_header
        self.border       = border
        self.border_style = (
            _BORDER_BY_NAME.get(border_style.lower(), ASCII)
            if isinstance(border_style, str) else border_style
        )
        self.padding      = max(0, padding)
        self._footer: str = ""

    # ------------------------------------------------------------------
    # Data API
    # ------------------------------------------------------------------

    def add_row(self, row: Iterable[str]) -> None:
        """Append a data row.  Extra cells are ignored; missing cells become ''."""
        cells = list(row)
        n     = len(self._columns)
        cells = (cells + [""] * n)[:n]
        self._rows.append(cells)

    def set_footer(self, text: str) -> None:
        """Set an optional footer line shown below the last data row."""
        self._footer = text

    def clear(self) -> None:
        """Remove all data rows."""
        self._rows.clear()
        self._footer = ""

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------

    def render(self, width: int = 78) -> list[str]:
        """Render the table to a list of strings, each at most *width* chars.

        Parameters
        ----------
        width : int
            Total available terminal width.  Column widths are calculated to
            fit within this budget.  Defaults to 78.
        """
        if not self._columns:
            return []

        col_widths = self._compute_widths(width)
        pad        = " " * self.padding
        bs         = self.border_style
        lines: list[str] = []

        def h_border(left: str, mid: str, right: str) -> str:
            segs = [bs.h * (w + self.padding * 2) for w in col_widths]
            return left + mid.join(segs) + right

        top_border = h_border(bs.top_left, bs.top_mid, bs.top_right) if self.border else ""
        mid_border = h_border(bs.mid_left, bs.cross,   bs.mid_right) if self.border else ""
        bot_border = h_border(bs.bot_left, bs.bot_mid, bs.bot_right) if self.border else ""

        total_width = len(top_border) if top_border else (
            sum(col_widths) + (len(col_widths) - 1) * (1 + self.padding * 2)
        )

        # Title
        if self.title:
            lines.append(self.title.center(total_width))

        # Top border
        if self.border:
            lines.append(top_border)

        # Header
        if self.show_header:
            header_cells  = [col.header for col in self._columns]
            header_aligns = [col.align  for col in self._columns]
            lines.extend(
                self._render_logical_row(header_cells, col_widths,
                                         header_aligns, pad)
            )
            if self.border:
                lines.append(mid_border)

        # Data rows
        aligns = [col.align for col in self._columns]
        for row in self._rows:
            lines.extend(
                self._render_logical_row(row, col_widths, aligns, pad)
            )

        # Bottom border
        if self.border:
            lines.append(bot_border)

        # Footer
        if self._footer:
            lines.append(self._footer.center(total_width))

        return lines

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render_logical_row(
        self,
        cells:      list[str],
        col_widths: list[int],
        aligns:     list[Align],
        pad:        str,
    ) -> list[str]:
        """Wrap each cell and emit as many visual lines as the tallest needs."""
        wrapped = [
            _wrap_cell(cells[i], col_widths[i])
            for i in range(len(self._columns))
        ]
        height = max(len(w) for w in wrapped)
        visual_lines: list[str] = []
        for line_idx in range(height):
            row_cells = [
                w[line_idx] if line_idx < len(w) else ""
                for w in wrapped
            ]
            v = self.border_style.v
            visual_lines.append(
                v + v.join(
                    pad + _fit(c, col_widths[i], aligns[i]) + pad
                    for i, c in enumerate(row_cells)
                ) + v
                if self.border else
                (" " * self.padding).join(
                    _fit(c, col_widths[i], aligns[i])
                    for i, c in enumerate(row_cells)
                )
            )
        return visual_lines

    def _compute_widths(self, total_width: int) -> list[int]:
        """Calculate per-column character widths to fit within *total_width*.

        Strategy
        --------
        1. Start with the minimum width needed to display every header and
           cell without wrapping (the "natural" width), capped by Column.max_width.
        2. Calculate the overhead: borders + padding consume
           ``(ncols + 1) * (1 + 2*padding)`` characters (with border)
           or ``(ncols - 1) * padding * 2`` (without).
        3. If natural widths fit, distribute any leftover space proportionally
           to columns that are narrower than their natural width.
        4. If natural widths overflow, shrink the widest columns first until
           everything fits, respecting Column.min_width.
        """
        n = len(self._columns)

        # Overhead characters consumed by borders + padding
        if self.border:
            # e.g. "| col | col |" → n+1 pipes + n*2*padding spaces
            overhead = (n + 1) + n * self.padding * 2
        else:
            overhead = (n - 1) * self.padding * 2

        available = max(total_width - overhead, n)  # at least 1 char per column

        # Natural (unwrapped) content width per column
        natural = []
        for i, col in enumerate(self._columns):
            col_cells = [row[i] for row in self._rows] if self._rows else []
            w = max(
                len(col.header),
                max((_visible_len(c) for c in col_cells), default=0),
                col.min_width,
            )
            if col.max_width > 0:
                w = min(w, col.max_width)
            natural.append(w)

        total_natural = sum(natural)

        if total_natural <= available:
            # Distribute surplus proportionally to natural widths
            surplus = available - total_natural
            widths  = list(natural)
            if surplus > 0 and total_natural > 0:
                for i in range(n):
                    share = int(surplus * natural[i] / total_natural)
                    if self._columns[i].max_width > 0:
                        cap    = self._columns[i].max_width - widths[i]
                        share  = min(share, cap)
                    widths[i] += share
                # Assign any remaining 1-char scraps to columns left-to-right
                remainder = available - sum(widths)
                for i in range(n):
                    if remainder <= 0:
                        break
                    if self._columns[i].max_width == 0 or \
                            widths[i] < self._columns[i].max_width:
                        widths[i] += 1
                        remainder -= 1
            return widths
        else:
            # Shrink: repeatedly trim 1 char from the current widest column
            # that still has room to shrink, until we fit.
            widths = list(natural)
            while sum(widths) > available:
                # Find widest shrinkable column
                idx = max(
                    (i for i in range(n)
                     if widths[i] > self._columns[i].min_width),
                    key=lambda i: widths[i],
                    default=None,
                )
                if idx is None:
                    break   # can't shrink further; accept overflow
                widths[idx] -= 1
            return widths


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def make_table(
    headers: Sequence[str | Column],
    rows:    Sequence[Sequence[str]],
    title:   str  = "",
    width:   int  = 78,
    **kwargs,
) -> list[str]:
    """One-shot helper: build a table and return rendered lines immediately.

    Example
    -------
    >>> lines = make_table(
    ...     ["Name", "HP"],
    ...     [["Aldric", "45"], ["Rhiannon", "72"]],
    ...     width=40,
    ... )
    >>> await ctx.send(*lines)
    """
    t = Table(headers, title=title, **kwargs)
    for row in rows:
        t.add_row(row)
    return t.render(width=width)
