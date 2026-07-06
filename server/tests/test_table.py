#!/usr/bin/env python3
"""tests/test_table.py

Unit tests for table.py.

Run with:
    python -m pytest tests/test_table.py -v
    python -m unittest tests.test_table
"""

from __future__ import annotations

import os
import sys
import unittest

import cbmcodecs2  # noqa: F401 -- registers the petscii_c64en_lc codec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from table import Table, Column, Align, make_table, Border, ASCII, SINGLE, DOUBLE, PETSCII


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lines(table: Table, width: int = 78) -> list[str]:
    return table.render(width=width)


def _joined(table: Table, width: int = 78) -> str:
    return "\n".join(_lines(table, width))


def _col_count(line: str) -> int:
    """Count data cells in a bordered row (pipes minus outer two)."""
    return line.count("|") - 1


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

class TestBasicStructure(unittest.TestCase):

    def setUp(self):
        self.t = Table(["Name", "HP", "Class"])
        self.t.add_row(["Aldric",   "45", "Fighter"])
        self.t.add_row(["Rhiannon", "72", "Mage"])

    def test_returns_list_of_strings(self):
        result = _lines(self.t)
        self.assertIsInstance(result, list)
        for line in result:
            self.assertIsInstance(line, str)

    def test_border_lines_present(self):
        lines = _lines(self.t)
        border_lines = [l for l in lines if l.startswith("+")]
        # top border, header separator, bottom border
        self.assertEqual(len(border_lines), 3)

    def test_header_row_present(self):
        out = _joined(self.t)
        self.assertIn("Name", out)
        self.assertIn("HP",   out)
        self.assertIn("Class", out)

    def test_data_rows_present(self):
        out = _joined(self.t)
        self.assertIn("Aldric",   out)
        self.assertIn("Rhiannon", out)
        self.assertIn("Fighter",  out)
        self.assertIn("Mage",     out)

    def test_correct_number_of_output_lines(self):
        # top border + header row + sep border + 2 data rows + bottom border = 6
        lines = _lines(self.t)
        self.assertEqual(len(lines), 6)

    def test_all_lines_same_width(self):
        lines = _lines(self.t, width=60)
        widths = {len(l) for l in lines}
        self.assertEqual(len(widths), 1, f"Inconsistent line widths: {widths}")

    def test_no_line_exceeds_requested_width(self):
        for w in (40, 60, 78, 120):
            for line in _lines(self.t, width=w):
                self.assertLessEqual(
                    len(line), w,
                    f"Line too long at width={w}: {line!r}"
                )


# ---------------------------------------------------------------------------
# Empty table / edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):

    def test_no_columns_returns_empty(self):
        t = Table([])
        self.assertEqual(t.render(), [])

    def test_no_rows_renders_header_only(self):
        t   = Table(["A", "B"])
        out = _joined(t)
        self.assertIn("A", out)
        self.assertIn("B", out)
        # only top border, header row, sep, bottom border = 4 lines
        self.assertEqual(len(_lines(t)), 4)

    def test_single_column(self):
        t = Table(["Item"])
        t.add_row(["Sword"])
        t.add_row(["Shield"])
        lines = _lines(t)
        self.assertTrue(all(l.startswith("|") or l.startswith("+") for l in lines))

    def test_single_row(self):
        t = Table(["X", "Y"])
        t.add_row(["1", "2"])
        out = _joined(t)
        self.assertIn("1", out)
        self.assertIn("2", out)

    def test_empty_cell_renders_without_error(self):
        t = Table(["A", "B", "C"])
        t.add_row(["", "middle", ""])
        lines = _lines(t)
        self.assertTrue(len(lines) > 0)

    def test_missing_cells_padded_with_empty(self):
        t = Table(["A", "B", "C"])
        t.add_row(["only_one"])   # only one cell for three columns
        out = _joined(t)
        self.assertIn("only_one", out)

    def test_extra_cells_ignored(self):
        t = Table(["A", "B"])
        t.add_row(["1", "2", "3", "4"])   # too many cells
        lines = _lines(t)
        self.assertTrue(len(lines) > 0)


# ---------------------------------------------------------------------------
# Title and footer
# ---------------------------------------------------------------------------

class TestTitleAndFooter(unittest.TestCase):

    def test_title_appears_above_table(self):
        t = Table(["X"], title="My Table")
        t.add_row(["val"])
        lines = _lines(t)
        self.assertIn("My Table", lines[0])

    def test_title_is_centred(self):
        t = Table(["X"], title="Hi")
        lines = _lines(t, width=40)
        title_line = lines[0]
        left_spaces  = len(title_line) - len(title_line.lstrip())
        right_spaces = len(title_line) - len(title_line.rstrip())
        # centred → roughly equal padding each side (within 1)
        self.assertAlmostEqual(left_spaces, right_spaces, delta=1)

    def test_footer_appears_below_table(self):
        t = Table(["X"])
        t.add_row(["val"])
        t.set_footer("1 record")
        lines = _lines(t)
        self.assertIn("1 record", lines[-1])


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

class TestAlignment(unittest.TestCase):

    def _data_rows(self, lines: list[str]) -> list[str]:
        """Return only the data rows (not borders or header)."""
        return [l for l in lines if l.startswith("|") and "Name" not in l
                and "---" not in l]

    def test_left_alignment_default(self):
        t = Table([Column("Name", align=Align.LEFT)])
        t.add_row(["Hi"])
        lines = _lines(t, width=30)
        data = [l for l in lines if "Hi" in l][0]
        # content should be left-padded (space after pipe, then text, then spaces)
        inner = data.strip("|").strip()
        self.assertTrue(inner.startswith("Hi"))

    def test_right_alignment(self):
        t = Table([Column("Num", align=Align.RIGHT)])
        t.add_row(["42"])
        lines = _lines(t, width=30)
        data = [l for l in lines if "42" in l][0]
        inner = data.strip("|")
        self.assertTrue(inner.rstrip().endswith("42"))

    def test_center_alignment(self):
        t = Table([Column("X", align=Align.CENTER)])
        t.add_row(["hi"])
        lines = _lines(t, width=30)
        data = [l for l in lines if "hi" in l][0]
        inner = data[1:-1]  # strip outer pipes
        left  = len(inner) - len(inner.lstrip())
        right = len(inner) - len(inner.rstrip())
        self.assertAlmostEqual(left, right, delta=1)

    def test_mixed_alignment_per_column(self):
        t = Table([
            Column("Left",   align=Align.LEFT),
            Column("Center", align=Align.CENTER),
            Column("Right",  align=Align.RIGHT),
        ])
        t.add_row(["aaa", "bbb", "ccc"])
        lines = _lines(t, width=60)
        # Should render without error and contain all values
        out = "\n".join(lines)
        for val in ("aaa", "bbb", "ccc"):
            self.assertIn(val, out)


# ---------------------------------------------------------------------------
# Cell wrapping
# ---------------------------------------------------------------------------

class TestCellWrapping(unittest.TestCase):

    def test_long_content_wraps_within_cell(self):
        t = Table(["Description"])
        t.add_row(["This is a very long description that definitely will not fit in a narrow column"])
        lines = _lines(t, width=40)
        # Should produce more than one data line for the single row
        data_lines = [l for l in lines if l.startswith("|") and "Description" not in l]
        self.assertGreater(len(data_lines), 1)

    def test_wrapped_lines_do_not_exceed_width(self):
        t = Table(["Col A", "Col B"])
        t.add_row([
            "Short",
            "This is a much longer piece of text that needs to be wrapped properly",
        ])
        for line in _lines(t, width=40):
            self.assertLessEqual(len(line), 40)

    def test_multiline_cells_align_columns(self):
        """All visual lines in a logical row must have the same total width."""
        t = Table(["Short", "Long"])
        t.add_row(["a", "word " * 20])
        lines = _lines(t, width=50)
        data_lines = [l for l in lines if l.startswith("|")]
        widths = {len(l) for l in data_lines}
        self.assertEqual(len(widths), 1, f"Inconsistent widths: {widths}")

    def test_newlines_in_cell_content(self):
        t = Table(["Notes"])
        t.add_row(["Line one\nLine two\nLine three"])
        lines = _lines(t, width=40)
        out = "\n".join(lines)
        self.assertIn("Line one",   out)
        self.assertIn("Line two",   out)
        self.assertIn("Line three", out)


# ---------------------------------------------------------------------------
# Column width constraints
# ---------------------------------------------------------------------------

class TestColumnWidths(unittest.TestCase):

    def test_min_width_respected(self):
        t = Table([Column("X", min_width=10)])
        t.add_row(["hi"])
        lines = _lines(t, width=78)
        data = [l for l in lines if "hi" in l][0]
        # inner content between pipes (minus padding) should be >= 10
        inner = data[2:-2]  # strip "| " and " |"
        self.assertGreaterEqual(len(inner), 10)

    def test_max_width_respected(self):
        t = Table([Column("Notes", max_width=10)])
        t.add_row(["short"])
        lines = _lines(t, width=78)
        data = [l for l in lines if "short" in l][0]
        inner = data[2:-2]
        self.assertLessEqual(len(inner), 10)

    def test_natural_widths_at_narrow_terminal(self):
        """At very narrow width the table still renders without crashing."""
        t = Table(["A", "B", "C"])
        t.add_row(["hello", "world", "!"])
        lines = _lines(t, width=20)
        self.assertTrue(len(lines) > 0)

    def test_wide_terminal_distributes_extra_space(self):
        """Extra terminal width is distributed — lines should be full-width."""
        t = Table(["Name", "Value"])
        t.add_row(["x", "y"])
        lines = _lines(t, width=100)
        border = [l for l in lines if l.startswith("+")][0]
        self.assertEqual(len(border), 100)


# ---------------------------------------------------------------------------
# No-border mode
# ---------------------------------------------------------------------------

class TestNoBorder(unittest.TestCase):

    def test_no_border_no_plus_lines(self):
        t = Table(["A", "B"], border=False)
        t.add_row(["1", "2"])
        lines = _lines(t)
        self.assertFalse(any(l.startswith("+") for l in lines))

    def test_no_border_no_pipe_chars(self):
        t = Table(["A", "B"], border=False)
        t.add_row(["hello", "world"])
        for line in _lines(t):
            self.assertNotIn("|", line)


# ---------------------------------------------------------------------------
# Border styles
# ---------------------------------------------------------------------------

class TestBorderStyles(unittest.TestCase):

    def _make(self, border_style=ASCII):
        t = Table(["Name", "HP", "Class"], title="Party", border_style=border_style)
        t.add_row(["Aldric",   "45", "Fighter"])
        t.add_row(["Rhiannon", "72", "Mage"])
        return t

    def _border_lines(self, lines: list[str], first_char: str) -> list[str]:
        return [l for l in lines if l.startswith(first_char)]

    def test_ascii_default_corners(self):
        lines = self._make(ASCII).render(width=40)
        self.assertTrue(lines[1].startswith("+"))   # top
        self.assertTrue(lines[-1].startswith("+"))  # bottom

    def test_single_top_corner(self):
        lines = self._make(SINGLE).render(width=40)
        self.assertTrue(lines[1].startswith("┌"))

    def test_single_mid_corner(self):
        # header separator uses ├, not ┌ or └
        lines = self._make(SINGLE).render(width=40)
        header_sep = lines[3]
        self.assertTrue(header_sep.startswith("├"))
        self.assertTrue(header_sep.endswith("┤"))

    def test_single_bot_corner(self):
        lines = self._make(SINGLE).render(width=40)
        self.assertTrue(lines[-1].startswith("└"))

    def test_double_top_corner(self):
        lines = self._make(DOUBLE).render(width=40)
        self.assertTrue(lines[1].startswith("╔"))

    def test_double_mid_corner(self):
        lines = self._make(DOUBLE).render(width=40)
        header_sep = lines[3]
        self.assertTrue(header_sep.startswith("╠"))
        self.assertTrue(header_sep.endswith("╣"))

    def test_double_bot_corner(self):
        lines = self._make(DOUBLE).render(width=40)
        self.assertTrue(lines[-1].startswith("╚"))

    def test_petscii_top_corner(self):
        # Table.render() returns Unicode box-drawing chars even for PETSCII
        # style -- cbmcodecs2 maps them to real PETSCII graphics bytes only
        # at wire-encode time (see table.py's PETSCII Border comment), so
        # the actual byte value has to be checked through that codec, not
        # assumed. '┌' encodes to byte 240, not chr(176).
        lines = self._make(PETSCII).render(width=40)
        self.assertTrue(lines[1].startswith('┌'))
        self.assertEqual(lines[1][0].encode('petscii_c64en_lc'), bytes([240]))

    def test_petscii_bot_corner(self):
        # '└' encodes to byte 237, not chr(173).
        lines = self._make(PETSCII).render(width=40)
        self.assertTrue(lines[-1].startswith('└'))
        self.assertEqual(lines[-1][0].encode('petscii_c64en_lc'), bytes([237]))

    def test_all_styles_consistent_line_width(self):
        for style in (ASCII, SINGLE, DOUBLE, PETSCII):
            with self.subTest(style=style):
                lines = self._make(style).render(width=40)
                widths = {len(l) for l in lines}
                self.assertEqual(len(widths), 1, f"Inconsistent widths for {style}: {widths}")

    def test_custom_border(self):
        custom = Border(
            top_left="A", top_mid="B", top_right="C",
            mid_left="D", cross="E",   mid_right="F",
            bot_left="G", bot_mid="H", bot_right="I",
            h="-", v="|",
        )
        t = Table(["X", "Y"], border_style=custom)
        t.add_row(["1", "2"])
        lines = t.render(width=30)
        self.assertTrue(lines[0].startswith("A"))
        self.assertTrue(lines[0].endswith("C"))
        self.assertTrue(lines[-1].startswith("G"))
        self.assertTrue(lines[-1].endswith("I"))


# ---------------------------------------------------------------------------
# show_header = False
# ---------------------------------------------------------------------------

class TestNoHeader(unittest.TestCase):

    def test_header_hidden(self):
        t = Table(["Name", "HP"], show_header=False)
        t.add_row(["Aldric", "45"])
        out = _joined(t)
        self.assertNotIn("Name", out)
        self.assertNotIn("HP",   out)
        self.assertIn("Aldric",  out)

    def test_no_header_separator_border(self):
        t = Table(["A", "B"], show_header=False)
        t.add_row(["x", "y"])
        # Without header there should be only top + bottom border = 2 border lines
        lines   = _lines(t)
        borders = [l for l in lines if l.startswith("+")]
        self.assertEqual(len(borders), 2)


# ---------------------------------------------------------------------------
# make_table convenience factory
# ---------------------------------------------------------------------------

class TestMakeTable(unittest.TestCase):

    def test_returns_list_of_strings(self):
        lines = make_table(["A", "B"], [["1", "2"], ["3", "4"]])
        self.assertIsInstance(lines, list)
        self.assertTrue(all(isinstance(l, str) for l in lines))

    def test_content_present(self):
        lines = make_table(["Hero", "Level"], [["Aldric", "5"]], width=50)
        out   = "\n".join(lines)
        self.assertIn("Hero",   out)
        self.assertIn("Aldric", out)
        self.assertIn("Level",  out)
        self.assertIn("5",      out)

    def test_width_respected(self):
        lines = make_table(["X"], [["y"]], width=30)
        for line in lines:
            self.assertLessEqual(len(line), 30)

    def test_title_passed_through(self):
        lines = make_table(["X"], [["y"]], title="My Table", width=40)
        self.assertIn("My Table", lines[0])


# ---------------------------------------------------------------------------
# Column defined via Column() vs plain string
# ---------------------------------------------------------------------------

class TestColumnDefinitions(unittest.TestCase):

    def test_string_headers_work(self):
        t = Table(["A", "B", "C"])
        t.add_row(["1", "2", "3"])
        out = _joined(t)
        self.assertIn("A", out)

    def test_column_object_headers_work(self):
        t = Table([
            Column("Name",  align=Align.LEFT),
            Column("Score", align=Align.RIGHT, min_width=5),
        ])
        t.add_row(["Hero", "9999"])
        out = _joined(t)
        self.assertIn("Hero", out)
        self.assertIn("9999", out)

    def test_mixed_string_and_column(self):
        t = Table(["Name", Column("HP", align=Align.RIGHT)])
        t.add_row(["Aldric", "45"])
        out = _joined(t)
        self.assertIn("Aldric", out)
        self.assertIn("45",     out)


# ---------------------------------------------------------------------------
# Integration — ctx.send() compatible output
# ---------------------------------------------------------------------------

class TestCtxSendCompatibility(unittest.TestCase):
    """Verify the output can be unpacked directly into ctx.send(*lines)."""

    def test_can_unpack_into_send_args(self):
        """simulate: await ctx.send(*t.render())"""
        t = Table(["Cmd", "Description"])
        t.add_row(["look",  "Examine your surroundings."])
        t.add_row(["say",   "Speak to those in your room."])
        t.add_row(["quit",  "Disconnect from the server."])
        lines = t.render(width=60)
        # Unpack should not raise
        try:
            _ = [str(l) for l in lines]
        except Exception as e:
            self.fail(f"Unpacking lines raised: {e}")

    def test_render_at_40_cols_petscii(self):
        """Commodore 64 client width."""
        t = Table(["Name", "HP"])
        t.add_row(["Aldric",   "45"])
        t.add_row(["Rhiannon", "72"])
        lines = t.render(width=40)
        for line in lines:
            self.assertLessEqual(len(line), 40)

    def test_render_at_80_cols_ansi(self):
        """Standard ANSI terminal width."""
        t = Table(["Name", "Class", "Level", "Guild"])
        t.add_row(["Aldric",   "Fighter", "5",  "Iron Fist"])
        t.add_row(["Rhiannon", "Mage",    "12", "Civilian"])
        lines = t.render(width=80)
        for line in lines:
            self.assertLessEqual(len(line), 80)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
