"""tests/movement/test_room_notices_actions.py

The menu-driven places (the Shoppe, the Ship's Stores, Bubba's Allies'
Guild, Jake's Stable, a guild hall) announce themselves through
presence.py, so movement.py adds nothing for them; nested areas (the
elevator inside the Shoppe) keep their messages inside the enclosing
area. The street room hears the player head into the Wall Bar & Grill
(bar/main.py tells the bar itself), and a dead player's respawn is heard
in the room they died in, then room 1. See room_notices.py/presence.py.

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
    """The shops and guilds announce themselves to the open room through
    presence.py (e.g. the Shoppe's "follows the sloping passageway
    downward..." / "steps out of the Shoppe."), so commands/movement.py
    must add nothing of its own -- it used to, and the lobby heard every
    trip twice, the first time as a bogus elevator ride."""

    async def _visit(self, enter, target, *args):
        ctx = _ctx()
        with patch(target, new=AsyncMock()) as menu:
            await enter(ctx, *args)
        menu.assert_awaited_once()
        return ctx.said

    async def test_shoppe(self):
        self.assertEqual(await self._visit(movement._enter_shoppe, 'shoppe.main.main'), [])

    async def test_ship_stores(self):
        self.assertEqual(await self._visit(movement._enter_ship_stores, 'ship.main.main'), [])

    async def test_allies_guild(self):
        self.assertEqual(
            await self._visit(movement._enter_allies_guild, 'street.allies_guild.main'), [])

    async def test_jakes_stable(self):
        self.assertEqual(await self._visit(movement._enter_jakes_stable, 'street.jakes.main'), [])

    async def test_guild_hall(self):
        self.assertEqual(
            await self._visit(movement._enter_guild_hq, 'guild_hq.main.main', 'thieves'), [])

    async def test_bar_tells_the_street_room_before_the_move(self):
        ctx = _ctx(room=36)
        with patch('bar.main.enter_bar', new=AsyncMock()):
            await movement._enter_bar(ctx)
        self.assertEqual(ctx.said, [(36, 'Ryan heads into the Wall Bar & Grill.')])
        self.assertEqual(ctx.client.room, movement._BAR_ROOM)


def _presence_client(room, level, name, area=None):
    from types import SimpleNamespace
    player = SimpleNamespace(name=name, map_level=level)
    ctx = SimpleNamespace(player=player, send=AsyncMock())
    client = SimpleNamespace(room=room, virtual_location=area, ctx=ctx)
    ctx.client = client
    return client


class TestPresenceNesting(unittest.IsolatedAsyncioTestCase):
    """The elevator is an area inside the Shoppe (another area)."""

    def _world(self):
        from types import SimpleNamespace
        rider = _presence_client(1, 1, 'Ryan', area='Shoppe')
        shopper = _presence_client(1, 1, 'Ann', area='Shoppe')
        lobby = _presence_client(1, 1, 'Bob')          # room 1, open room
        other_level = _presence_client(1, 2, 'Cid')    # room 1, level 2
        server = SimpleNamespace(clients={'r': rider, 's': shopper,
                                          'l': lobby, 'o': other_level})
        rider.ctx.server = server
        return rider, shopper, lobby, other_level

    async def test_elevator_stays_inside_the_shoppe(self):
        from presence import broadcast_nearby, enter_area, leave_area
        rider, shopper, lobby, other_level = self._world()
        ctx = rider.ctx
        await broadcast_nearby(ctx, 'Ryan steps up to the elevator.')
        await enter_area(ctx, 'Elevator')
        self.assertEqual(rider.virtual_location, 'Elevator')
        await leave_area(ctx, 'Elevator')
        self.assertEqual(rider.virtual_location, 'Shoppe')   # back, not None
        heard = [c.args[0] for c in shopper.ctx.send.await_args_list]
        self.assertEqual(heard, ['Ryan steps up to the elevator.',
                                 'Ryan steps out of the Elevator.'])
        lobby.ctx.send.assert_not_called()
        other_level.ctx.send.assert_not_called()

    async def test_leaving_the_outermost_area_tells_this_levels_open_room(self):
        from presence import enter_area, leave_area
        rider, shopper, lobby, other_level = self._world()
        rider.virtual_location = None
        await enter_area(rider.ctx, 'Shoppe')
        await leave_area(rider.ctx, 'Shoppe')
        self.assertIsNone(rider.virtual_location)
        lobby.ctx.send.assert_awaited_once_with('Ryan steps out of the Shoppe.')
        other_level.ctx.send.assert_not_called()

    async def test_area_names_read_naturally(self):
        from presence import enter_area, leave_area
        for area, heard in (("Jake's Stable", "Ryan steps out of Jake's Stable."),
                            ("Allies' Guild", "Ryan steps out of the Allies' Guild.")):
            rider, shopper, lobby, other_level = self._world()
            rider.virtual_location = None
            await enter_area(rider.ctx, area)
            await leave_area(rider.ctx, area)
            lobby.ctx.send.assert_awaited_once_with(heard)


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
