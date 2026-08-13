"""tests/commands/test_use_communicator.py — unit tests for commands/
use.py's communicator branch (USE communicator).

Ported from SPUR.USE.S's 'comm' label (~lines 128-140) and 'malfunction'
label (~lines 221-232), traced from source, not invented:

  - A level-6 "no signal" room (RoomFlag.NO_COMM_SIGNAL, the raw 'FR'
    token -- Land of Oz sub-zone) always says "only static", no roll,
    no state change.
  - Otherwise a 1-10 roll: a flat ~10% malfunction chance (roll==3) the
    first time; ~40% (roll<5 or ==3) every attempt after, once the
    once_per_day 'CM*' token is set -- which happens as soon as the
    player reaches the confirm prompt, even if they then cancel.
  - Malfunction: communicator (#66) swapped for broken communicator
    (#141), teleported to a random level/room instead of level 6 room 1.
  - Success + confirmed: teleported to level 6 room 1 via
    Server._teleport_to().
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.use import UseCommand
from inventory import Inventory
from items import Item, ItemCategory


def _communicator() -> Item:
    return Item(id_number=66, name='communicator', category=ItemCategory.ITEM)


def _make_player(once_per_day=None, map_level=6, map_room=1):
    player = MagicMock()
    player.inventory = Inventory()
    player.inventory.add(_communicator())
    player.once_per_day = once_per_day if once_per_day is not None else []
    player.map_level = map_level
    player.map_room = map_room
    player.unsaved_changes = False
    return player


def _room(flags=None):
    room = MagicMock()
    room.flags = flags or []
    return room


class _FakeCtx:
    def __init__(self, player, room=None, room_no=1, confirm='y'):
        self.player = player
        self.client = MagicMock()
        self.client.room = room_no
        self.server = MagicMock()
        self.server.items = [
            {'number': 141, 'name': 'broken communicator', 'type': 'misc', 'price': 1},
        ]
        self.server.game_map.get_room = MagicMock(return_value=room)
        self.server.game_map.levels = {n: {1: MagicMock()} for n in range(1, 8)}
        self.server._teleport_to = AsyncMock()
        self.sent: list = []
        self.send = AsyncMock(side_effect=self._record)
        self.prompt = AsyncMock(return_value=confirm)

    async def _record(self, msg, **kwargs):
        if isinstance(msg, list):
            self.sent.extend(msg)
        else:
            self.sent.append(msg)

    def flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestNoCommSignalRoom(unittest.IsolatedAsyncioTestCase):

    async def test_only_static_no_roll_no_state_change(self):
        player = _make_player()
        room = _room(['no_comm_signal'])
        ctx = _FakeCtx(player, room=room)

        with patch('commands.use.random.randint') as mock_roll:
            await UseCommand().execute(ctx, 'communicator')
            mock_roll.assert_not_called()

        self.assertIn('You hear only static from the communicator..', ctx.flat())
        ctx.server._teleport_to.assert_not_awaited()
        self.assertEqual(len(player.inventory.find(item_id=66)), 1)


class TestSuccessfulBeamAboard(unittest.IsolatedAsyncioTestCase):

    async def test_confirmed_use_teleports_to_level_6_room_1(self):
        player = _make_player()
        ctx = _FakeCtx(player, room=_room(), confirm='y')

        with patch('commands.use.random.randint', return_value=7):
            await UseCommand().execute(ctx, 'communicator')

        ctx.server._teleport_to.assert_awaited_once_with(ctx, 6, 1)
        self.assertIn('The device hums strangely!', ctx.flat())
        self.assertIn("Standby to beam aboard", ctx.flat())

    async def test_declining_confirm_prompt_does_not_teleport(self):
        player = _make_player()
        ctx = _FakeCtx(player, room=_room(), confirm='n')

        with patch('commands.use.random.randint', return_value=7):
            await UseCommand().execute(ctx, 'communicator')

        ctx.server._teleport_to.assert_not_awaited()

    async def test_first_attempt_sets_once_per_day_token_even_if_cancelled(self):
        # Matches SPUR's own ys$=ys$+"CM*" placement -- set before the
        # confirm prompt is even asked, regardless of the answer.
        player = _make_player()
        ctx = _FakeCtx(player, room=_room(), confirm='n')

        with patch('commands.use.random.randint', return_value=7):
            await UseCommand().execute(ctx, 'communicator')

        self.assertIn('CM*', player.once_per_day)


class TestMalfunctionRisk(unittest.IsolatedAsyncioTestCase):

    async def test_roll_of_3_always_malfunctions_on_first_attempt(self):
        player = _make_player()
        ctx = _FakeCtx(player, room=_room())

        with patch('commands.use.random.randint') as mock_random:
            mock_random.side_effect = [3, 1]  # comm roll, then target-level roll
            await UseCommand().execute(ctx, 'communicator')

        ctx.server._teleport_to.assert_awaited_once()
        args = ctx.server._teleport_to.call_args.args
        self.assertNotEqual((args[1], args[2]), (6, 1))

    async def test_first_attempt_only_malfunctions_on_exactly_3(self):
        player = _make_player()
        ctx = _FakeCtx(player, room=_room())

        with patch('commands.use.random.randint', return_value=1):
            await UseCommand().execute(ctx, 'communicator')

        # roll=1 < threshold(0) is False, and 1 != 3 -- no malfunction.
        ctx.server._teleport_to.assert_awaited_once_with(ctx, 6, 1)

    async def test_after_first_use_roll_below_5_also_malfunctions(self):
        player = _make_player(once_per_day=['CM*'])
        ctx = _FakeCtx(player, room=_room())

        with patch('commands.use.random.randint') as mock_random:
            mock_random.side_effect = [4, 1]  # comm roll (<5 -> malfunction), then level roll
            await UseCommand().execute(ctx, 'communicator')

        args = ctx.server._teleport_to.call_args.args
        self.assertNotEqual((args[1], args[2]), (6, 1))

    async def test_malfunction_swaps_communicator_for_broken_one(self):
        player = _make_player()
        ctx = _FakeCtx(player, room=_room())

        with patch('commands.use.random.randint', side_effect=[3, 1]):
            await UseCommand().execute(ctx, 'communicator')

        self.assertEqual(len(player.inventory.find(item_id=66)), 0)
        broken = player.inventory.find(item_id=141)
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0].item.name, 'broken communicator')

    async def test_malfunction_message_shown(self):
        player = _make_player()
        ctx = _FakeCtx(player, room=_room())

        with patch('commands.use.random.randint', side_effect=[3, 1]):
            await UseCommand().execute(ctx, 'communicator')

        flat = ctx.flat()
        self.assertIn('A strange buzzing comes from the communicator!!', flat)
        self.assertIn('MALFUNCTION', flat)

    async def test_malfunction_does_not_prompt_for_confirmation(self):
        player = _make_player()
        ctx = _FakeCtx(player, room=_room())

        with patch('commands.use.random.randint', side_effect=[3, 1]):
            await UseCommand().execute(ctx, 'communicator')

        ctx.prompt.assert_not_awaited()


class TestRealLevel6Data(unittest.TestCase):
    """RoomFlag.NO_COMM_SIGNAL against the actual converted game data --
    99 "Land of Oz" sub-zone rooms (Dark Woods/Witches Coven/Emerald
    City/etc.), confirmed real via the raw 'FR' token in every level 6
    Msg file and absent from every other level."""

    def test_dark_woods_room_has_no_comm_signal_flag(self):
        from simple_server import Server
        server = Server('127.0.0.1', 0)
        room = server.game_map.get_room(6, 494)
        self.assertIsNotNone(room)
        self.assertEqual(room.name, 'Dark Woods')
        self.assertIn('no_comm_signal', room.flags)

    def test_ordinary_level_6_room_has_no_such_flag(self):
        from simple_server import Server
        server = Server('127.0.0.1', 0)
        room = server.game_map.get_room(6, 1)
        self.assertIsNotNone(room)
        self.assertNotIn('no_comm_signal', room.flags or [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
