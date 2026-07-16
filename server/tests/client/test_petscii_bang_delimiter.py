"""tests/client/test_petscii_bang_delimiter.py

'|' needs Shift+- on a real Commodore keyboard -- cumbersome enough that
Ryan asked for an easier-to-type substitute for PETSCII clients specifically:
'!' now works the same as '|' in petscii_encode() (and, for the 'tab' entity,
in _expand_tab_tokens() when the target codec is PETSCIICodec), including the
doubled-delimiter escape (!!token!! -> literal !token!, matching ||token|| ->
|token|). '|' still works everywhere it always has -- this is additive, not
a replacement -- and ANSI/plain encoding are deliberately left untouched
since '!' is common in ordinary game text there ("Welcome, Alice!") in a way
it isn't a concern for PETSCII, where the whole point is avoiding an awkward
keystroke.
"""
from __future__ import annotations

import unittest

from formatting import (
    ansi_encode, plain_encode, petscii_encode, format_lines,
    _expand_tab_tokens, PETSCIICodec, ANSICodec, PETSCII_CONTROL_CODES,
)
from terminal import ClientSettings, TabSettings


def _settings(has_tab_key: bool = False, tab_width: int = 4) -> ClientSettings:
    cs = ClientSettings()
    cs.tab_settings = TabSettings()
    cs.tab_settings.has_tab_key = has_tab_key
    if has_tab_key:
        cs.tab_settings.tab_output = '\t'
    else:
        cs.tab_settings.tab_width  = tab_width
        cs.tab_settings.tab_output = ' ' * tab_width
    return cs


class TestPetsciiEncodeBangDelimiter(unittest.TestCase):

    def test_bang_color_token_matches_pipe_color_token(self):
        self.assertEqual(petscii_encode('!red!Hi!reset!'),
                         petscii_encode('|red|Hi|reset|'))

    def test_bang_control_code_byte_is_correct(self):
        self.assertEqual(petscii_encode('!red!'),
                         bytes([PETSCII_CONTROL_CODES['red']]))

    def test_bang_count_repeats_control_byte(self):
        self.assertEqual(petscii_encode('!red:3!'),
                         bytes([PETSCII_CONTROL_CODES['red']]) * 3)

    def test_pipe_still_works_unchanged(self):
        self.assertEqual(petscii_encode('|red|'),
                         bytes([PETSCII_CONTROL_CODES['red']]))

    def test_mixed_delimiters_do_not_match_as_a_token(self):
        """'|red!' is not a token -- opening and closing delimiters must
        match (enforced via regex backreference)."""
        result = petscii_encode('|red!')
        # Neither delimiter alone forms a valid pair, so the red control
        # byte must NOT appear -- it should fall through as literal text.
        self.assertNotIn(bytes([PETSCII_CONTROL_CODES['red']]), result)

    def test_bang_escape_does_not_apply_color(self):
        """!!red!! is the escape (mirrors ||red||) -- literal !red!, no
        control byte."""
        result = petscii_encode('!!red!!')
        self.assertNotIn(bytes([PETSCII_CONTROL_CODES['red']]), result)

    def test_bang_escape_preserves_bang_delimiter_in_literal_output(self):
        """The escape's literal output keeps whichever delimiter was
        actually typed -- !!red!! collapses to !red!, not |red|."""
        result = petscii_encode('!!red!!')
        # '!' round-trips through the PETSCII charset; 'RED' is
        # case-swapped by the codec, but the bang delimiters must survive.
        self.assertEqual(result.count(b'!'), 2)

    def test_unknown_bang_token_left_as_literal(self):
        result = petscii_encode('!bogus!')
        self.assertNotIn(bytes([PETSCII_CONTROL_CODES['red']]), result)
        # Falls through as literal text -- doesn't raise or vanish.
        self.assertGreater(len(result), 0)


class TestAnsiPlainRemainPipeOnly(unittest.TestCase):
    """'!' must NOT become a delimiter for ANSI/plain clients -- unlike
    '|', it's common in ordinary game text ("Welcome, Alice!")."""

    def test_ansi_encode_bang_token_stays_literal(self):
        self.assertEqual(ansi_encode('!red!Hi!reset!'), '!red!Hi!reset!')

    def test_ansi_encode_pipe_token_still_applies(self):
        self.assertNotEqual(ansi_encode('|red|Hi|reset|'), '|red|Hi|reset|')

    def test_plain_encode_bang_token_stays_literal(self):
        self.assertEqual(plain_encode('!red!Hi!reset!'), '!red!Hi!reset!')

    def test_ordinary_exclamations_unaffected(self):
        text = 'Welcome, Alice! You win!'
        self.assertEqual(ansi_encode(text), text)
        self.assertEqual(plain_encode(text), text)


class TestExpandTabTokensBangDelimiter(unittest.TestCase):

    def test_bang_tab_expands_when_codec_is_petscii(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A!tab!B', cs, PETSCIICodec()), 'A    B')

    def test_bang_tab_count_expands_when_codec_is_petscii(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A!tab:2!B', cs, PETSCIICodec()), 'A        B')

    def test_pipe_tab_still_expands_under_petscii_codec(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A|tab|B', cs, PETSCIICodec()), 'A    B')

    def test_bang_tab_escape_left_untouched_at_expand_stage(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A!!tab!!B', cs, PETSCIICodec()), 'A!!tab!!B')

    def test_bang_tab_not_expanded_for_ansi_codec(self):
        """Scoped to PETSCII only -- an ANSI client typing '!tab!' just
        gets literal text, not a real tab."""
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A!tab!B', cs, ANSICodec()), 'A!tab!B')

    def test_bang_tab_not_expanded_with_no_codec(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        self.assertEqual(_expand_tab_tokens('A!tab!B', cs, None), 'A!tab!B')

    def test_format_lines_expands_bang_tab_for_petscii(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        lines = format_lines(['A!tab!B!tab:2!C'], cs, PETSCIICodec())
        self.assertEqual(lines, ['A    B        C'])

    def test_full_pipeline_bang_tab_survives_to_petscii_bytes(self):
        cs = _settings(has_tab_key=False, tab_width=4)
        lines = format_lines(['A!tab!B'], cs, PETSCIICodec())
        self.assertEqual(petscii_encode(lines[0]), petscii_encode('A    B'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
