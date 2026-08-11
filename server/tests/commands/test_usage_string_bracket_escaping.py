"""tests/commands/test_usage_string_bracket_escaping.py

Ryan: several commands' inline "Usage: ..." reminder strings (sent via a
raw ctx.send(), not through commands.help.format_help()'s auto-escaping
of Help.usage's left column) used unescaped [optional] bracket notation
like '<name[,name2]>'. Any [bracketed] text sent to a player goes through
formatting.highlight_brackets(), which treats a single [...] as a
highlight span and *drops the literal brackets* -- '<name[,name2]>' would
render as '<name,name2>' with ',name2' highlighted, silently destroying
the intended optional-argument notation. Fixed by escaping with [[..]]
(highlight_brackets' literal-bracket escape) in commands/page.py,
whisper.py, mail.py, teleport.py, and connect.py.
"""
from __future__ import annotations

import unittest

from formatting import highlight_brackets, PlainCodec


class TestUsageStringsSurviveBracketHighlighting(unittest.TestCase):
    """Each of these strings is sent verbatim via ctx.send() from a real
    command's error/usage-reminder path -- confirm the optional-argument
    brackets survive highlight_brackets() as literal text instead of
    being consumed as highlight markup."""

    def _renders_literally(self, text: str, expected_substring: str):
        rendered = highlight_brackets(text, PlainCodec())
        self.assertIn(expected_substring, rendered,
                       f'{text!r} rendered as {rendered!r}, expected to contain {expected_substring!r}')

    def test_page_usage_string(self):
        self._renders_literally(
            'Usage: page <name[[,name2]]>=<message>',
            '<name[,name2]>=<message>',
        )

    def test_whisper_usage_string(self):
        self._renders_literally(
            'Usage: whisper <name[[,name2]]>=<message>',
            '<name[,name2]>=<message>',
        )

    def test_mail_usage_string(self):
        self._renders_literally(
            'Usage: mail <target[[,target2]]>=<message>',
            '<target[,target2]>=<message>',
        )

    def test_teleport_learn_usage_string(self):
        self._renders_literally(
            'Usage: teleport #learn [[<name>]] -- current room has no name to fall back on.',
            '#learn [<name>]',
        )

    def test_teleport_forget_usage_string(self):
        self._renders_literally(
            'Usage: teleport #forget [[<alias>]] -- current room has no name to fall back on.',
            '#forget [<alias>]',
        )

    def test_connect_usage_string(self):
        self._renders_literally(
            'Usage:  connect <username> [[<password>]]',
            '<username> [<password>]',
        )

    def test_unescaped_bracket_would_have_been_mangled(self):
        # Sanity check the failure mode this guards against: without the
        # [[..]] escape, the comma+content inside a single [...] gets
        # swallowed as highlight markup and the brackets vanish.
        broken = highlight_brackets('Usage: page <name[,name2]>=<message>', PlainCodec())
        self.assertNotIn('[,name2]', broken)
        self.assertIn('<name,name2>', broken)


if __name__ == '__main__':
    unittest.main(verbosity=2)
