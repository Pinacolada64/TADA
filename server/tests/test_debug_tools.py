"""tests/test_debug_tools.py

Covers debug_tools.py's debug_confirm()/debug_toggle_once_per_day() --
the centralized "if DEBUG_MODE, ask a quick Y/N" helpers, first used by
bar/skip.py's once-per-day debug hook.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from debug_tools import debug_confirm, debug_toggle_once_per_day


def _ctx(debug_mode: bool, prompt_answer):
    ctx = MagicMock()
    ctx.player = MagicMock()
    ctx.player.query_flag = lambda flag: debug_mode
    ctx.player.once_per_day = []
    ctx.player.unsaved_changes = False
    ctx.prompt = AsyncMock(return_value=prompt_answer)
    ctx.send = AsyncMock()
    return ctx


class TestDebugConfirm(unittest.IsolatedAsyncioTestCase):
    async def test_no_prompt_outside_debug_mode(self):
        ctx = _ctx(debug_mode=False, prompt_answer='y')
        result = await debug_confirm(ctx, 'Do the thing?')
        self.assertFalse(result)
        ctx.prompt.assert_not_called()

    async def test_yes_answer_returns_true(self):
        ctx = _ctx(debug_mode=True, prompt_answer='y')
        result = await debug_confirm(ctx, 'Do the thing?')
        self.assertTrue(result)
        ctx.prompt.assert_awaited_once_with('Y/N', preamble_lines=['Do the thing?'])

    async def test_yes_full_word_returns_true(self):
        ctx = _ctx(debug_mode=True, prompt_answer='Yes')
        self.assertTrue(await debug_confirm(ctx, 'Do the thing?'))

    async def test_no_answer_returns_false(self):
        ctx = _ctx(debug_mode=True, prompt_answer='n')
        self.assertFalse(await debug_confirm(ctx, 'Do the thing?'))

    async def test_empty_answer_returns_false(self):
        ctx = _ctx(debug_mode=True, prompt_answer='')
        self.assertFalse(await debug_confirm(ctx, 'Do the thing?'))

    async def test_disconnect_returns_false(self):
        ctx = _ctx(debug_mode=True, prompt_answer=None)
        self.assertFalse(await debug_confirm(ctx, 'Do the thing?'))


class TestDebugToggleOncePerDay(unittest.IsolatedAsyncioTestCase):
    async def test_no_prompt_outside_debug_mode(self):
        ctx = _ctx(debug_mode=False, prompt_answer='y')
        result = await debug_toggle_once_per_day(ctx, 'Skip')
        self.assertFalse(result)
        self.assertNotIn('Skip', ctx.player.once_per_day)
        ctx.prompt.assert_not_called()

    async def test_confirmed_appends_and_returns_true(self):
        ctx = _ctx(debug_mode=True, prompt_answer='y')
        result = await debug_toggle_once_per_day(ctx, 'Skip')
        self.assertTrue(result)
        self.assertIn('Skip', ctx.player.once_per_day)
        self.assertTrue(ctx.player.unsaved_changes)
        ctx.send.assert_awaited_with('Appended.')

    async def test_declined_does_not_append(self):
        ctx = _ctx(debug_mode=True, prompt_answer='n')
        result = await debug_toggle_once_per_day(ctx, 'Skip')
        self.assertFalse(result)
        self.assertNotIn('Skip', ctx.player.once_per_day)

    async def test_already_present_short_circuits_without_prompting(self):
        ctx = _ctx(debug_mode=True, prompt_answer='n')  # would decline if asked
        ctx.player.once_per_day = ['Skip']
        result = await debug_toggle_once_per_day(ctx, 'Skip')
        self.assertTrue(result)
        ctx.prompt.assert_not_called()

    async def test_missing_once_per_day_list_is_created(self):
        ctx = _ctx(debug_mode=True, prompt_answer='y')
        del ctx.player.once_per_day
        ctx.player.once_per_day = None
        result = await debug_toggle_once_per_day(ctx, 'Skip')
        self.assertTrue(result)
        self.assertEqual(ctx.player.once_per_day, ['Skip'])

    async def test_custom_label_used_in_prompt(self):
        ctx = _ctx(debug_mode=True, prompt_answer='n')
        await debug_toggle_once_per_day(ctx, 'internal_key', label='The Pawnbroker')
        ctx.prompt.assert_awaited_once_with(
            'Y/N', preamble_lines=["Add 'The Pawnbroker' to once-per-day activities?"])


if __name__ == '__main__':
    unittest.main(verbosity=2)
