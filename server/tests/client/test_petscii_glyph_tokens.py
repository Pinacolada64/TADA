"""tests/client/test_petscii_glyph_tokens.py

Ryan's idea: PETSCII art files (graphics/banner-petscii.txt and friends)
need a way to embed a raw screen/graphics character code that has no
|token| equivalent -- PETSCII_CONTROL_CODES is for control codes/colors,
not arbitrary character-set glyphs (a box-drawing line, a specific
graphics-mode character used to draw a sword, etc).

New {glyph} syntax in formatting.py, parallel to |token|/!token!:
  {$c0}       -- raw byte 0xC0 (hex, 1-2 digits)
  {192}       -- raw byte 192  (decimal, 0-255)
  {LEFT_TEE}  -- named glyph, from terminal.CommodoreGraphicsChars
  {$c0:38}    -- any of the above + ':N' repeats the byte N times
  {{literal}} -- escape, renders as the literal '{literal}'
"""
from __future__ import annotations

import unittest

from formatting import petscii_encode, _visible_len, wrap_text, NAMED_PETSCII_GLYPHS
from terminal import CommodoreGraphicsChars


class TestGlyphTokenByteValues(unittest.TestCase):

    def test_hex_byte_literal(self):
        self.assertEqual(petscii_encode('{$c0}'), bytes([0xC0]))

    def test_hex_byte_literal_single_digit(self):
        self.assertEqual(petscii_encode('{$5}'), bytes([0x5]))

    def test_hex_byte_literal_uppercase(self):
        self.assertEqual(petscii_encode('{$C0}'), bytes([0xC0]))

    def test_decimal_byte_literal(self):
        self.assertEqual(petscii_encode('{192}'), bytes([192]))

    def test_decimal_byte_literal_out_of_range_falls_back_to_literal_text(self):
        # No valid byte > 255 -- left as literal text, same as an unknown
        # |token| falls back to literal text in petscii_encode().
        result = petscii_encode('{999}')
        self.assertNotEqual(result, bytes([999 % 256]))

    def test_named_glyph_resolves_to_enum_byte_value(self):
        expected = ord(str(CommodoreGraphicsChars.LEFT_TEE.value))
        self.assertEqual(petscii_encode('{LEFT_TEE}'), bytes([expected]))

    def test_named_glyph_registry_matches_enum(self):
        for member in CommodoreGraphicsChars:
            self.assertEqual(NAMED_PETSCII_GLYPHS[member.name], ord(str(member.value)))

    def test_unknown_named_glyph_falls_back_to_literal_text(self):
        # Falls back to encoding the whole '{NOT_A_REAL_GLYPH}' span as
        # ordinary text (same length, same treatment as any other
        # plain-text segment), not a resolved single raw byte.
        result = petscii_encode('{NOT_A_REAL_GLYPH}')
        self.assertEqual(len(result), len('{NOT_A_REAL_GLYPH}'))


class TestGlyphTokenRepeatCount(unittest.TestCase):

    def test_hex_repeat_count(self):
        self.assertEqual(petscii_encode('{$c0:5}'), bytes([0xC0]) * 5)

    def test_decimal_repeat_count(self):
        self.assertEqual(petscii_encode('{192:5}'), bytes([192]) * 5)

    def test_named_glyph_repeat_count(self):
        expected = ord(str(CommodoreGraphicsChars.LEFT_TEE.value))
        self.assertEqual(petscii_encode('{LEFT_TEE:3}'), bytes([expected]) * 3)

    def test_no_count_means_one(self):
        self.assertEqual(len(petscii_encode('{$c0}')), 1)


class TestGlyphTokenSurroundingText(unittest.TestCase):

    def test_plain_text_around_glyph_token_is_encoded_normally(self):
        result = petscii_encode('AB{$c0:2}CD')
        # cbmcodecs2-encoded 'AB', then two raw 0xC0 bytes, then 'CD'.
        self.assertEqual(result[2:4], bytes([0xC0, 0xC0]))

    def test_glyph_token_mixed_with_color_token(self):
        from formatting import PETSCII_CONTROL_CODES
        result = petscii_encode('|red|{$c0:3}|reset|')
        self.assertEqual(
            result,
            bytes([PETSCII_CONTROL_CODES['red']]) + bytes([0xC0]) * 3
            + bytes([PETSCII_CONTROL_CODES['reset']]),
        )


class TestGlyphTokenEscape(unittest.TestCase):

    def test_double_brace_escape_renders_literal(self):
        result = petscii_encode('{{$c0}}')
        self.assertNotEqual(result, bytes([0xC0]))
        # Encodes the whole literal '{$c0}' span as ordinary text (same
        # length as any other plain-text segment), not a resolved byte.
        self.assertEqual(len(result), len('{$c0}'))


class TestGlyphTokenVisibleWidth(unittest.TestCase):
    """{glyph} tokens render real on-screen characters -- unlike a
    zero-width |token| color code, their visible width must count
    towards word-wrap/line-fill math (menu rules, banner art, etc)."""

    def test_visible_len_counts_repeat_as_width(self):
        self.assertEqual(_visible_len('{$c0:38}'), 38)

    def test_visible_len_single_glyph_is_one(self):
        self.assertEqual(_visible_len('{LEFT_TEE}'), 1)

    def test_visible_len_ignores_color_tokens_but_counts_glyphs(self):
        self.assertEqual(_visible_len('|red|{$c0:10}|reset|'), 10)

    def test_wrap_text_does_not_split_a_wide_glyph_token_early(self):
        # A single 38-wide glyph token plus 'AB' fits under 41 but not 40.
        lines = wrap_text('AB {$c0:38}', 41)
        self.assertEqual(len(lines), 1)


if __name__ == '__main__':
    unittest.main()
