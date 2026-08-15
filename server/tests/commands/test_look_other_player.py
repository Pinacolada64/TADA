"""tests/commands/test_look_other_player.py

Covers commands/look.py's new player-lookup branch (Ryan's request,
8/14/26): "look <player>" mirrors "x <player>" -- both resolve through
commands/examine.py's _examine_player()/_room_players(), so a LOOKed
player gets the same tier/race/class/health/purse/shield/armor/weapons
line EXAMINE already gives.
"""
from __future__ import annotations

import unittest

from base_classes import PlayerClass, PlayerMoneyTypes, PlayerRace
from commands.look import LookCommand
from inventory import Inventory
from player import Player


class _FakeServer:
    game_map = None

    def __init__(self):
        self.clients = {}


class _FakeClient:
    def __init__(self, room, ctx):
        self.room = room
        self.ctx = ctx


class _FakeCtx:
    def __init__(self, player, server):
        self.player = player
        self.server = server
        self.client = None
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def send_room(self, *args, **kwargs):
        pass


def _player(name='Rulan') -> Player:
    p = Player(name=name)
    p.inventory = Inventory(capacity=10)
    return p


def _room_setup(looker_player, target_player, room=1):
    server = _FakeServer()

    target_ctx = _FakeCtx(target_player, server)
    target_ctx.client = _FakeClient(room=room, ctx=target_ctx)
    server.clients['target'] = target_ctx.client

    looker_ctx = _FakeCtx(looker_player, server)
    looker_ctx.client = _FakeClient(room=room, ctx=looker_ctx)
    server.clients['looker'] = looker_ctx.client
    return looker_ctx


class TestLookAtOtherPlayer(unittest.IsolatedAsyncioTestCase):

    def _make_target(self, name='Legolas', xp_level=5, hit_points=40):
        target = _player(name)
        target.xp_level = xp_level
        target.hit_points = hit_points
        target.char_race = PlayerRace.ELF
        target.char_class = PlayerClass.RANGER
        return target

    async def test_look_shows_same_line_as_examine(self):
        target = self._make_target()
        ctx = _room_setup(_player(), target)

        result = await LookCommand().execute(ctx, 'Legolas')

        self.assertTrue(result.success)
        joined = '\n'.join(ctx.sent)
        self.assertIn('Legolas looks like an elite male Elf Ranger in excellent health,', joined)

    async def test_case_insensitive_substring_match(self):
        target = self._make_target(name='Gareth')
        ctx = _room_setup(_player(), target)

        await LookCommand().execute(ctx, 'gare')

        joined = '\n'.join(ctx.sent)
        self.assertIn('Gareth looks like', joined)

    async def test_ignores_players_in_a_different_room(self):
        target = self._make_target(name='Legolas')
        ctx = _room_setup(_player(), target, room=1)
        ctx.client.room = 1
        ctx.server.clients['target'].room = 2

        await LookCommand().execute(ctx, 'Legolas')

        self.assertIn("You don't see any 'legolas' here.", ctx.sent)

    async def test_no_match_falls_through_to_not_here(self):
        ctx = _room_setup(_player(), self._make_target(name='Legolas'))

        await LookCommand().execute(ctx, 'nobody')

        self.assertIn("You don't see any 'nobody' here.", ctx.sent)


if __name__ == '__main__':
    unittest.main()
