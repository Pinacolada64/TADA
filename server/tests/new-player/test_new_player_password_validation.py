"""tests/new-player/test_new_player_password_validation.py

Regression coverage for commands/new_player.py's _validate_password():
a password containing a character network_context.py's
_petscii_input_to_ascii() can't decode from a real C64 keyboard (brackets,
backslash, backtick, braces, pipe, tilde) hashes differently depending on
whether it was set from a PETSCII client or a JSON/ANSI one, so it must be
rejected at creation time -- see net_common.petscii_unsafe_password_chars().

Run with:
    python -m pytest tests/new-player/test_new_player_password_validation.py -v
"""
from __future__ import annotations

import unittest

from commands.new_player import _choose_password, _validate_password


class _FakeCtx:
    def __init__(self, responses):
        self._q = list(responses)
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        out = []
        for item in self.sent:
            if isinstance(item, (list, tuple)):
                out.extend(str(x) for x in item)
            else:
                out.append(str(item))
        return '\n'.join(out)


class TestValidatePassword(unittest.IsolatedAsyncioTestCase):

    async def test_safe_password_passes(self):
        ctx = _FakeCtx([])
        self.assertTrue(await _validate_password(ctx, 'Fescue123'))
        self.assertEqual(ctx.sent, [])

    async def test_too_short_rejected(self):
        ctx = _FakeCtx([])
        self.assertFalse(await _validate_password(ctx, 'abc'))
        self.assertIn('at least 4 characters', ctx._flat())

    async def test_unsafe_char_rejected(self):
        ctx = _FakeCtx([])
        self.assertFalse(await _validate_password(ctx, 'se[cr]et'))
        self.assertIn("can't contain: []", ctx._flat())

    async def test_backtick_brace_pipe_tilde_rejected(self):
        ctx = _FakeCtx([])
        self.assertFalse(await _validate_password(ctx, 'a{b}c|d~e`f'))
        self.assertIn("can't contain:", ctx._flat())


class TestChoosePasswordReprompts(unittest.IsolatedAsyncioTestCase):

    async def test_unsafe_password_reprompts_then_accepts_safe_one(self):
        ctx = _FakeCtx(['se[cr]et', 'safepw123', 'safepw123'])
        result = await _choose_password(ctx)
        self.assertEqual(result, 'safepw123')
        self.assertIn("can't contain: []", ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
