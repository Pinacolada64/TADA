"""tests/commands/test_usage_string_bracket_escaping.py

Ryan: several commands' inline "Usage: ..." reminder strings (sent via a
raw ctx.send(), not through commands.help.format_help(), which
auto-escapes every free-text field of a Help object -- usage/examples/
admin_examples (both columns) and notes/admin_notes/petscii_notes -- via
commands.help._auto_escape()) used unescaped [optional] bracket notation
like '<name[,name2]>'. Any [bracketed] text sent to a player goes through
formatting.highlight_brackets(), which treats a single [...] as a
highlight span and *drops the literal brackets* -- '<name[,name2]>' would
render as '<name,name2>' with ',name2' highlighted, silently destroying
the intended optional-argument notation. Fixed by escaping with [[..]]
(highlight_brackets' literal-bracket escape) in commands/page.py,
whisper.py, mail.py, teleport.py, and connect.py.

TestFormatHelpAutoEscaping below covers the opposite failure mode: a
Help() author manually adding [[..]] to a field that _auto_escape()
already covers, over-escaping it into visibly-wrong doubled-bracket
'[[name]]' output instead of the intended '[name]' (this happened for
real in commands/groups.py's usage and commands/map.py's notes/
admin_notes -- both fixed).
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


class TestFormatHelpAutoEscaping(unittest.TestCase):
    """commands.help.format_help() auto-escapes [optional] syntax in every
    Help field it renders (via _auto_escape()), covering both the
    left *and* right column of usage/examples/admin_examples, plus
    notes/admin_notes/petscii_notes -- a Help() author should write plain
    single brackets everywhere in these fields and never need [[..]] by
    hand (description/summary are the one exception -- see Help's class
    docstring)."""

    def _rendered(self, help_obj, **kw):
        from commands.help import format_help
        lines = format_help(help_obj, 'test', **kw)
        return '\n'.join(highlight_brackets(l, PlainCodec()) for l in lines)

    def test_usage_left_column_renders_literal_brackets(self):
        from commands.help import Help
        text = self._rendered(Help(usage=[('test [<name>]', 'desc')]))
        self.assertIn('test [<name>]', text)

    def test_usage_right_column_renders_literal_brackets(self):
        from commands.help import Help
        text = self._rendered(Help(usage=[('test', 'takes [<name>] optionally')]))
        self.assertIn('takes [<name>] optionally', text)

    def test_examples_both_columns_render_literal_brackets(self):
        from commands.help import Help
        text = self._rendered(Help(examples=[('test [<name>]', 'set [<name>] if given')]))
        self.assertIn('test [<name>]', text)
        self.assertIn('set [<name>] if given', text)

    def test_notes_render_literal_brackets(self):
        from commands.help import Help
        text = self._rendered(Help(notes=['Use test [<name>] to try it.']))
        self.assertIn('test [<name>] to try it', text)

    def test_admin_notes_render_literal_brackets(self):
        from commands.help import Help
        text = self._rendered(
            Help(admin_notes=['Admins can use test [<name>] too.']),
            is_privileged=True,
        )
        self.assertIn('test [<name>] too', text)

    def test_admin_examples_render_literal_brackets(self):
        from commands.help import Help
        text = self._rendered(
            Help(admin_examples=[('test [<name>]', 'admin-only example')]),
            is_privileged=True,
        )
        self.assertIn('test [<name>]', text)

    def test_manually_double_bracketing_a_usage_entry_is_a_mistake(self):
        # Regression guard for the exact bug this session found in
        # commands/groups.py: writing [[..]] in a usage entry (already
        # auto-escaped by _auto_escape()) produces visibly-wrong doubled
        # brackets in the final output, not the intended single-bracket
        # '[<name>]' display -- a Help() author should always write plain
        # single brackets and let format_help() do the escaping.
        from commands.help import Help
        text = self._rendered(Help(usage=[('test [[<name>]]', 'desc')]))
        self.assertNotIn('test [<name>]', text)
        self.assertIn('test [[<name>]]', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
