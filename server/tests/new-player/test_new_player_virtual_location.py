"""tests/test_new_player_virtual_location.py

Regression test: WHEREAT (commands/whereat.py) reads ctx.client.
virtual_location to show what an online player is doing. Character
creation didn't set it at all, so a player mid-chargen just showed up
by room/'(unknown)' like anyone else instead of "Creating a character".

main_flow() now sets it for the duration of the flow and restores
whatever was there before on every exit path (finished, abandoned, or
paused for resume) -- same pattern as commands/news.py's "Reading news".
"""
from __future__ import annotations

import types
import unittest
from unittest.mock import patch

from commands.new_player import main_flow


class _Ctx:
    def __init__(self, responses, virtual_location=None):
        self._q = list(responses)
        self.sent: list = []
        self.client = types.SimpleNamespace(virtual_location=virtual_location)
        from player import Player
        self.player = Player()

    async def send(self, *args):
        self.sent.extend(args)

    async def prompt(self, prompt_text='', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None


class TestVirtualLocationDuringChargen(unittest.IsolatedAsyncioTestCase):
    async def test_set_during_creation(self):
        """Capture virtual_location mid-flow via a patched step."""
        from player import Player
        ctx = _Ctx([])
        seen = {}

        async def fake_choose_name(c):
            seen['during'] = c.client.virtual_location
            return False  # abandon immediately after capturing

        with patch('commands.new_player._choose_name', fake_choose_name):
            await main_flow(ctx, player=Player())

        self.assertEqual(seen['during'], 'Creating a character')

    async def test_restored_after_abandon(self):
        from player import Player
        ctx = _Ctx([])

        async def fake_choose_name(c):
            return False  # abandon immediately

        with patch('commands.new_player._choose_name', fake_choose_name):
            await main_flow(ctx, player=Player())

        self.assertIsNone(ctx.client.virtual_location)

    async def test_restores_previous_location_not_just_none(self):
        """If something upstream had already set a virtual location, that
        value comes back afterward instead of being clobbered to None."""
        from player import Player
        ctx = _Ctx([], virtual_location='Reading news')

        async def fake_choose_name(c):
            return False

        with patch('commands.new_player._choose_name', fake_choose_name):
            await main_flow(ctx, player=Player())

        self.assertEqual(ctx.client.virtual_location, 'Reading news')

    async def test_missing_client_attribute_is_a_noop(self):
        """Test doubles / edge cases without a .client shouldn't crash."""
        from player import Player

        class _NoClientCtx:
            def __init__(self):
                self.player = Player()

            async def send(self, *args):
                pass

            async def prompt(self, prompt_text='', preamble_lines=None):
                return None

        ctx = _NoClientCtx()

        async def fake_choose_name(c):
            return False

        with patch('commands.new_player._choose_name', fake_choose_name):
            result = await main_flow(ctx, player=Player())
        self.assertFalse(result.success)


if __name__ == '__main__':
    unittest.main()
