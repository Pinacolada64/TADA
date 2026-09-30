"""tests/movement/test_room_notices_actions.py

The room hears about the menu-driven places (the Shoppe elevator, the
Ship's Stores, Bubba's Allies' Guild, Jake's Stable, a guild hall) going
in and coming back out, about the player heading into the Wall Bar &
Grill (from the street room they left -- bar/main.py tells the bar
itself), and about a dead player's respawn (the room they died in, then
room 1). See room_notices.py.

Run with:
    python -m pytest tests/movement/test_room_notices_actions.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands import movement
from player import Player
from simple_server import Server


def _ctx(room=20, name='Ryan'):
    """A ctx whose send_room records (room at the time, line)."""
    ctx = MagicMock()
    ctx.player = Player(name=name)
    ctx.client.room = room
    ctx.send = AsyncMock()
    ctx.server._show_room = AsyncMock()
    ctx.said = []

    async def send_room(line, exclude_self=False):
        assert exclude_self, 'room notices never go to the actor'
        ctx.said.append((ctx.client.room, line))
    ctx.send_room = send_room
    return ctx


class TestBuildings(unittest.IsolatedAsyncioTestCase):

    async def _visit(self, enter, target, *args):
        ctx = _ctx()
        with patch(target, new=AsyncMock()) as menu:
            await enter(ctx, *args)
        menu.assert_awaited_once()
        return [line for _, line in ctx.said]

    async def test_shoppe(self):
        self.assertEqual(await self._visit(movement._enter_shoppe, 'shoppe.main.main'), [
            'Ryan takes the elevator down to the Shoppe.',
            'Ryan steps out of the elevator.'])

    async def test_ship_stores(self):
        self.assertEqual(await self._visit(movement._enter_ship_stores, 'ship.main.main'), [
            "Ryan climbs down the manhole into the Ship's Stores.",
            'Ryan climbs back up out of the manhole.'])

    async def test_allies_guild(self):
        self.assertEqual(
            await self._visit(movement._enter_allies_guild, 'street.allies_guild.main'), [
                "Ryan heads down the alley to Bubba's Allies' Guild.",
                'Ryan comes back up the alley.'])

    async def test_jakes_stable(self):
        self.assertEqual(await self._visit(movement._enter_jakes_stable, 'street.jakes.main'), [
            "Ryan heads into Jake's Stable.",
            "Ryan comes back out of Jake's Stable."])

    async def test_guild_hall(self):
        self.assertEqual(
            await self._visit(movement._enter_guild_hq, 'guild_hq.main.main', 'thieves'), [
                'Ryan enters the guild hall.',
                'Ryan comes back out of the guild hall.'])

    async def test_bar_tells_the_street_room_before_the_move(self):
        ctx = _ctx(room=36)
        with patch('bar.main.enter_bar', new=AsyncMock()):
            await movement._enter_bar(ctx)
        self.assertEqual(ctx.said, [(36, 'Ryan heads into the Wall Bar & Grill.')])
        self.assertEqual(ctx.client.room, movement._BAR_ROOM)


class TestRespawn(unittest.IsolatedAsyncioTestCase):

    async def test_room_of_death_then_room_1(self):
        server = Server('127.0.0.1', 0)
        ctx = _ctx(room=5, name='Rulan')
        ctx.player.hit_points = 0
        with patch.object(Server, '_show_room', new=AsyncMock()):
            await server._player_dies(ctx)
        self.assertEqual(ctx.said, [
            (5, "Rulan's body fades away."),
            (1, 'Rulan staggers in, confused but alive.'),
        ])


if __name__ == '__main__':
    unittest.main()
