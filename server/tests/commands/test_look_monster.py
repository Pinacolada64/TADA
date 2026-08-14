"""tests/commands/test_look_monster.py

Covers commands/look.py's monster-lookup branches:

  1. A monster mid-fight (active CombatSession in the room).
  2. The room's own static monster (room.monster), matched any time it's
     present -- not just mid-fight (Ryan's request: LOOK should work on
     a monster whenever it's in the room).

Both show monsters.json's "description" field (plain text, no
substitute_tokens() -- monster dicts don't carry gender/pronoun
attributes the way Ally/Player do) when the monster is alive, falling
back to a generic "You see the X." line for a monster with no
description set. A monster this player has already killed (in
player.dead_monsters) reports as dead instead of using its
alive-flavored description (Ryan's request -- most flavor text assumes
the monster is still up and fighting).
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


class _FakeRoom:
    def __init__(self, monster: int = 0):
        self.monster = monster


class _FakeGameMap:
    def __init__(self, room: _FakeRoom | None):
        self._room = room

    def get_room(self, level, room_no):
        return self._room


class _FakeServer:
    game_map = None
    items = []
    weapons = []
    rations = []
    room_items: dict = {}

    def __init__(self, session=None, room=1, monsters=None, room_monster=None):
        self.active_combats = {room: session} if session else {}
        self.monsters = monsters or []
        if room_monster is not None:
            self.game_map = _FakeGameMap(_FakeRoom(monster=room_monster))


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
        monster = {'number': 3, 'name': 'TROLL', 'strength': 20, 'flags': {},
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
        monster = {'number': 3, 'name': 'TROLL', 'strength': 20, 'flags': {}, 'description': 'A troll.'}
        session = _FakeSession(monster)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        await LookCommand().execute(ctx, 'troll')

        self.assertIn('A troll.', ctx.sent)

    async def test_falls_back_to_generic_line_with_no_description(self):
        monster = {'number': 99, 'name': 'GRUE', 'strength': 5, 'flags': {}, 'description': None}
        session = _FakeSession(monster)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        await LookCommand().execute(ctx, 'GRUE')

        self.assertIn('You see the GRUE.', ctx.sent)

    async def test_no_article_flag_omits_the(self):
        monster = {'number': 13, 'name': 'DRACULA', 'strength': 10,
                   'flags': {'no_article': True}, 'description': None}
        session = _FakeSession(monster)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        await LookCommand().execute(ctx, 'DRACULA')

        self.assertIn('You see DRACULA.', ctx.sent)

    async def test_finished_combat_session_falls_back_to_room_monster(self):
        # No room.monster configured in this server -- so once the session
        # is done, LOOK genuinely finds nothing.
        monster = {'number': 3, 'name': 'TROLL', 'strength': 20, 'flags': {}, 'description': 'A troll.'}
        session = _FakeSession(monster, done=True)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        result = await LookCommand().execute(ctx, 'TROLL')

        self.assertTrue(result.success)
        self.assertNotIn('A troll.', ctx.sent)
        self.assertIn("You don't see any 'troll' here.", ctx.sent)

    async def test_no_match_falls_through_to_not_here(self):
        monster = {'number': 3, 'name': 'TROLL', 'strength': 20, 'flags': {}, 'description': 'A troll.'}
        session = _FakeSession(monster)
        ctx = _FakeCtx(_bare_player(), _FakeServer(session))

        result = await LookCommand().execute(ctx, 'dragon')

        self.assertTrue(result.success)
        self.assertIn("You don't see any 'dragon' here.", ctx.sent)


class TestLookAtRoomMonsterOutsideCombat(unittest.IsolatedAsyncioTestCase):
    """No active CombatSession -- just the room's own monster.json entry,
    same as what a player sees in "There is X here" on room entry."""

    def _server(self, monster: dict, room_monster_number: int = None):
        return _FakeServer(monsters=[monster], room_monster=room_monster_number or monster['number'])

    async def test_shows_description_before_any_fight_starts(self):
        monster = {'number': 19, 'name': 'MEDUSA', 'strength': 40, 'flags': {},
                   'description': 'Medusa turns her head slowly, and you look away just in time.'}
        ctx = _FakeCtx(_bare_player(), self._server(monster))

        result = await LookCommand().execute(ctx, 'medusa')

        self.assertTrue(result.success)
        self.assertIn(
            'Medusa turns her head slowly, and you look away just in time.',
            ctx.sent,
        )

    async def test_already_killed_monster_reports_dead_instead_of_flavor_text(self):
        monster = {'number': 19, 'name': 'MEDUSA', 'strength': 40, 'flags': {},
                   'description': 'Medusa turns her head slowly, and you look away just in time.'}
        player = _bare_player()
        player.dead_monsters = [19]
        ctx = _FakeCtx(player, self._server(monster))

        await LookCommand().execute(ctx, 'medusa')

        self.assertIn('You see a dead MEDUSA here.', ctx.sent)
        self.assertNotIn(
            'Medusa turns her head slowly, and you look away just in time.',
            ctx.sent,
        )

    async def test_dead_mechanical_monster_shows_wrecked_remains(self):
        monster = {'number': 107, 'name': 'GUARD DROID', 'strength': 15,
                   'flags': {'mechanical': True}, 'description': 'A guard droid pivots toward you.'}
        player = _bare_player()
        player.dead_monsters = [107]
        ctx = _FakeCtx(player, self._server(monster))

        await LookCommand().execute(ctx, 'guard droid')

        self.assertIn('The wrecked remains of GUARD DROID lie here.', ctx.sent)

    async def test_charmed_and_recruited_monster_is_gone_from_the_room(self):
        monster = {'number': 21, 'name': 'PIXIE', 'strength': 5, 'flags': {},
                   'description': 'A pixie hovers just out of reach.'}
        player = _bare_player()
        player.charmed_monsters = [21]
        ctx = _FakeCtx(player, self._server(monster))

        result = await LookCommand().execute(ctx, 'pixie')

        self.assertTrue(result.success)
        self.assertIn("You don't see any 'pixie' here.", ctx.sent)

    async def test_no_room_monster_falls_through(self):
        ctx = _FakeCtx(_bare_player(), _FakeServer())

        result = await LookCommand().execute(ctx, 'anything')

        self.assertTrue(result.success)
        self.assertIn("You don't see any 'anything' here.", ctx.sent)


if __name__ == '__main__':
    unittest.main()
