"""tests/ship/test_main.py

Covers ship/main.py -- the Ship's Stores menu loop (SPUR.SHIP.S). Wizard,
Pawn Shop, and Clan/Guild are disabled here with their own in-theme
refusal text rather than omitted from the menu; SALVAGE and TR are
full-text commands routed to ship/salvage_bay.py and ship/transporter.py.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from flags import PlayerFlags
from player import Player
from ship.main import main as ship_main


def _new_player(name: str) -> Player:
    player = Player(name=name)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    return player


class _FakeClient:
    def __init__(self):
        self.room = 1
        self.virtual_location = None


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.client = _FakeClient()
        self.server = SimpleNamespace(clients={}, items=[])

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestShipMenuDisabledFacilities(unittest.IsolatedAsyncioTestCase):
    async def test_wizard_is_disabled(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['w', 'x'], player)
        await ship_main(ctx)
        self.assertIn('(No magic shop on the ship..)', ctx._flat())

    async def test_pawn_shop_is_disabled(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['v', 'x'], player)
        await ship_main(ctx)
        self.assertIn('(Pawn shop not active here)', ctx._flat())

    async def test_clan_is_disabled(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['c', 'x'], player)
        await ship_main(ctx)
        self.assertIn('(Join not active here)', ctx._flat())


class TestShipMenuDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_salvage_routes_to_salvage_bay(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['salvage', 'x'], player)
        with patch('ship.salvage_bay.main', new=AsyncMock()) as mocked:
            await ship_main(ctx)
        mocked.assert_awaited_once_with(ctx)

    async def test_tr_routes_to_transporter_and_ends_session_on_success(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['tr'], player)
        with patch('ship.transporter.main', new=AsyncMock(return_value=True)) as mocked:
            await ship_main(ctx)
        mocked.assert_awaited_once_with(ctx)

    async def test_tr_stays_in_ship_menu_when_cancelled(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['tr', 'x'], player)
        with patch('ship.transporter.main', new=AsyncMock(return_value=False)) as mocked:
            await ship_main(ctx)
        mocked.assert_awaited_once_with(ctx)
        self.assertIn('You climb back up through the manhole.', ctx._flat())

    async def test_x_leaves_the_ship(self):
        player = _new_player('Rulan')
        ctx = _FakeCtx(['x'], player)
        await ship_main(ctx)
        self.assertIn('You climb back up through the manhole.', ctx._flat())


if __name__ == '__main__':
    unittest.main()
