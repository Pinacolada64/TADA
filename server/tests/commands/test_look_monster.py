"""tests/commands/test_look_monster.py

Covers commands/look.py's monster-lookup branch: LOOK <monster name>
during an active fight shows monsters.json's "description" field (plain
text, no substitute_tokens() -- monster dicts don't carry gender/pronoun
attributes the way Ally/Player do), falling back to a generic
"You see the X." line for a monster with no description set.
"""
from __future__ import annotations

import asyncio
import unittest

from commands.look import LookCommand
from inventory import Inventory
from player import Player


class _FakeClient:
    room = 1


class _FakeSession:
    def __init__(self, monster: dict, done: bool = False):
        self.monster = monster
        self._done = asyncio.Event()
        if done:
            self._done.set()


class _FakeServer:
    game_map = None

    def __init__(self, session=None, room=1):
        self.active_combats = {room: session} if session else {}


class _FakeCtx:
    def __init__(self, player, server=None):
        self.player = player
        self.client = _FakeClient()
        self.server = server or _FakeServer()
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def send_room(self, *args, **kwargs):
        pass


def _bare_player() -> Player:
    p = Player(name='Rulan')
    p.inventory = Inventory(capacity=10)
    return p


class TestLookAtCombatMonster(unittest.IsolatedAsyncioTestCase):

    async def test_shows_monster_description(self):
        monster = {'number': 3, 'name': 'TROLL', 'flags': {},
                   'description': 'A troll looms overhead, warty green hide crisscrossed with old scars.'}
        session = _FakeSession(monster)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        result = await LookCommand().execute(ctx, 'TROLL')

        self.assertTrue(result.success)
        self.assertIn(
            'A troll looms overhead, warty green hide crisscrossed with old scars.',
            ctx.sent,
        )

    async def test_matches_case_insensitive_substring(self):
        monster = {'number': 3, 'name': 'TROLL', 'flags': {}, 'description': 'A troll.'}
        session = _FakeSession(monster)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        await LookCommand().execute(ctx, 'troll')

        self.assertIn('A troll.', ctx.sent)

    async def test_falls_back_to_generic_line_with_no_description(self):
        monster = {'number': 99, 'name': 'GRUE', 'flags': {}, 'description': None}
        session = _FakeSession(monster)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        await LookCommand().execute(ctx, 'GRUE')

        self.assertIn('You see the GRUE.', ctx.sent)

    async def test_no_article_flag_omits_the(self):
        monster = {'number': 13, 'name': 'DRACULA', 'flags': {'no_article': True},
                   'description': None}
        session = _FakeSession(monster)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        await LookCommand().execute(ctx, 'DRACULA')

        self.assertIn('You see DRACULA.', ctx.sent)

    async def test_finished_combat_session_is_ignored(self):
        monster = {'number': 3, 'name': 'TROLL', 'flags': {}, 'description': 'A troll.'}
        session = _FakeSession(monster, done=True)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        result = await LookCommand().execute(ctx, 'TROLL')

        self.assertTrue(result.success)
        self.assertNotIn('A troll.', ctx.sent)
        self.assertIn("You don't see any 'troll' here.", ctx.sent)

    async def test_no_match_falls_through_to_not_here(self):
        monster = {'number': 3, 'name': 'TROLL', 'flags': {}, 'description': 'A troll.'}
        session = _FakeSession(monster)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        result = await LookCommand().execute(ctx, 'dragon')

        self.assertTrue(result.success)
        self.assertIn("You don't see any 'dragon' here.", ctx.sent)


if __name__ == '__main__':
    unittest.main()
