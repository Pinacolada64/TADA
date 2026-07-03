"""tests/test_allies_guild_movement_hook.py

Unit tests for the Allys Guild's hardcoded level/room/direction interception
in commands/movement.py (mirrors SPUR.MAIN.S: "if cl=4 if cr=42 if di=3 ...").

Coverage:
  - level 4, room 42, moving east -> triggers the Allys Guild, no normal move
  - wrong level, wrong room, or wrong direction -> falls through to normal movement

Run with:
    python -m pytest tests/test_allies_guild_movement_hook.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.movement import MoveCommand


def _make_ctx(map_level=1, room=1):
    ctx = MagicMock()
    ctx.player = MagicMock()
    ctx.player.map_level = map_level
    ctx.client = MagicMock()
    ctx.client.room = room
    ctx.server = MagicMock()
    ctx.server.game_map = MagicMock()
    ctx.server.game_map.rooms = {}
    ctx.server._move = AsyncMock()
    ctx.server._show_room = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestAllyGuildMovementHook(unittest.IsolatedAsyncioTestCase):

    async def test_level4_room42_east_triggers_guild(self):
        ctx = _make_ctx(map_level=4, room=42)
        with patch('bar.allies_guild.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'e')
        mock_main.assert_awaited_once_with(ctx)
        ctx.server._move.assert_not_awaited()

    async def test_wrong_level_falls_through(self):
        ctx = _make_ctx(map_level=1, room=42)
        with patch('bar.allies_guild.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'e')
        mock_main.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'e')

    async def test_wrong_room_falls_through(self):
        ctx = _make_ctx(map_level=4, room=1)
        with patch('bar.allies_guild.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'e')
        mock_main.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'e')

    async def test_wrong_direction_falls_through(self):
        ctx = _make_ctx(map_level=4, room=42)
        with patch('bar.allies_guild.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'n')
        mock_main.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
