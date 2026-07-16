"""tests/commands/test_example_commands.py

Covers 'test #colors' -- folded in from the former standalone 'colors'
command (Ryan). ColorsCommand's name and aliases ('colors'/'color'/
'colour'/'colours') clashed with the 'help colors' concept topic added
alongside the |token| mini-language docs (commands/help.py's
_TOPICS is checked before commands in HelpCommand.execute(), so
'help colors' silently shadowed ColorsCommand's own help). Removing the
standalone command and folding its output under 'test #colors' frees
those names for the help topic instead of fighting over them.
"""
from __future__ import annotations

import unittest

from commands.example_commands import TestCommand
import commands.example_commands as example_commands


class _FakeCtx:
    def __init__(self):
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestColorsFoldedIntoTestCommand(unittest.IsolatedAsyncioTestCase):

    async def test_colors_switch_lists_colors(self):
        ctx = _FakeCtx()
        await TestCommand().execute(ctx, "#colors")
        self.assertIn('Available colors:', ctx._flat())

    async def test_colors_switch_uses_token_syntax(self):
        ctx = _FakeCtx()
        await TestCommand().execute(ctx, "#colors")
        self.assertIn('|reset|', ctx._flat())

    async def test_without_switch_no_color_list(self):
        ctx = _FakeCtx()
        await TestCommand().execute(ctx)
        self.assertNotIn('Available colors:', ctx._flat())

    def test_standalone_colors_command_removed(self):
        self.assertFalse(hasattr(example_commands, 'ColorsCommand'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
