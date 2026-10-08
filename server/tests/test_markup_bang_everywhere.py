"""'!' works like '|' as a markup delimiter on every terminal -- but only
around a real token name (markup_tokens.py)."""
import unittest

import formatting
import markup_tokens
import table


class TestTokenNames(unittest.TestCase):

    def test_names_match_the_encoders(self):
        self.assertEqual(markup_tokens.TOKEN_NAMES,
                         set(formatting.ANSI_COLOR_CODES)
                         | set(formatting.PETSCII_CONTROL_CODES) | {'tab'})


class TestBangEverywhere(unittest.TestCase):

    def test_same_bytes_as_pipe_on_every_codec(self):
        for enc in (formatting.ansi_encode, formatting.plain_encode, formatting.petscii_encode):
            with self.subTest(encoder=enc.__name__):
                self.assertEqual(enc('!light_red!Hi!reset!'), enc('|light_red|Hi|reset|'))

    def test_counts_work_with_bang(self):
        self.assertEqual(formatting.ansi_encode('!red:2!x'), formatting.ansi_encode('|red:2|x'))

    def test_ordinary_text_untouched_without_warnings(self):
        samples = ['Welcome, Alice!', 'PILLAGE!', 'Wow!great!', 'Hey!!wow!!',
                   'It works!tab-wise', '!redx!', 'Go!Go!Go!']
        for text in samples:
            with self.subTest(text=text), self.assertNoLogs('root', level='WARNING'):
                self.assertEqual(formatting.ansi_encode(text), text)
                self.assertEqual(formatting.plain_encode(text), text)
                self.assertEqual(formatting._visible_len(text), len(text))

    def test_mixed_delimiters_are_not_a_token(self):
        self.assertEqual(formatting.plain_encode('|red!x!reset|'), '|red!x!reset|')

    def test_visible_len_and_table_agree(self):
        for text in ('!red!Hi!reset!', '!!red!!Hi', '||red||Hi', 'Hi!'):
            with self.subTest(text=text):
                self.assertEqual(formatting._visible_len(text), table._visible_len(text))

    def test_table_wrap_keeps_bang_tokens_whole(self):
        lines = table._wrap_cell('!red!Danger!reset! ahead, adventurer', 10)
        self.assertEqual([formatting.plain_encode(l) for l in lines],
                         ['Danger', 'ahead,', 'adventurer'])


if __name__ == '__main__':
    unittest.main()
