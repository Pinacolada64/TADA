"""tests/combat/test_shared_monster_kill.py

Two parties fighting one monster: when one side lands the kill, the other
must not be able to open a second, fresh full-HP fight against the same
monster. Bystanders swing once per ATTACK (CombatSession.join()), so an
ATTACK landing just after the kill used to find no active session and
fall through to enter_combat() -- commands/attack.py's _monster_in_room()
had no "already dead" gate (tools/bot_epic_battle.py documented the race
and worked around it). Now:

  - combat.engine.monster_gone_for() checks dead_monsters, fled/charmed,
    and player.slain_here (a re_animates kill, never added to
    dead_monsters, stays dead until the player leaves the room);
  - _monster_dies() sets slain_here for every credited participant;
  - ATTACK and LURK refuse a monster that's gone for the player.

Run with:
    .venv/bin/python3 -m pytest tests/combat/test_shared_monster_kill.py -v
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from combat.engine import CombatSession, monster_gone_for

_TROLL = {'number': 3, 'name': 'TROLL', 'to_hit': 4, 'strength': 10, 'flags': {}}
_WRAITH = {'number': 70, 'name': 'RINGWRAITH', 'to_hit': 4, 'strength': 10,
           'flags': {'re_animates': True}}


def _player(name):
    return SimpleNamespace(
        name=name, map_level=1, hit_points=30, is_expert=True, stats={},
        dead_monsters=[], fled_monsters=[], charmed_monsters=[], kill_log=[],
        slain_here=None, readied_weapon=None, unsaved_changes=False, party=[],
        query_flag=lambda flag: False,
    )


def _ctx(name, monster, room_no=13, active_combats=None):
    room = SimpleNamespace(monster=monster['number'], flags=[], exits={})
    ctx = MagicMock()
    ctx.player = _player(name)
    ctx.client = SimpleNamespace(room=room_no)
    ctx.server = SimpleNamespace(
        monsters=[monster], active_combats=active_combats if active_combats is not None else {},
        game_map=SimpleNamespace(get_room=lambda level, n: room if n == room_no else None),
    )
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


def _sent(ctx) -> str:
    return '\n'.join(str(c.args[0]) for c in ctx.send.call_args_list if c.args)


class TestMonsterGoneFor(unittest.TestCase):

    def test_states(self):
        p = _player('Rulan')
        self.assertIsNone(monster_gone_for(p, 3, level=1, room_no=13))
        p.dead_monsters = [3]
        self.assertEqual(monster_gone_for(p, 3, level=1, room_no=13), 'dead')
        p.dead_monsters = []
        p.fled_monsters = [3]
        self.assertEqual(monster_gone_for(p, 3, level=1, room_no=13), 'fled')
        p.fled_monsters = []
        p.charmed_monsters = [3]
        self.assertEqual(monster_gone_for(p, 3, level=1, room_no=13), 'charmed')

    def test_slain_here_only_counts_in_that_room(self):
        p = _player('Rulan')
        p.slain_here = (1, 13, 70)
        self.assertEqual(monster_gone_for(p, 70, level=1, room_no=13), 'dead')
        self.assertIsNone(monster_gone_for(p, 70, level=1, room_no=14))
        self.assertIsNone(monster_gone_for(p, 70, level=2, room_no=13))


class TestKillMarksEveryParticipant(unittest.IsolatedAsyncioTestCase):

    async def _kill(self, monster):
        leader = _ctx('Rulan', monster)
        bystander = _ctx('Frodo', monster)
        session = CombatSession(monster, room_no=13)
        session.attackers = [leader, bystander]
        with patch('combat.engine.gold_from_monster', return_value=0), \
             patch('encounters.droid_salvage.apply', new=AsyncMock()), \
             patch('encounters.monster.try_shadow_ally', new=AsyncMock()), \
             patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch.object(session, '_reveal_hidden_exit', new=AsyncMock()):
            await session._monster_dies(leader)
        return leader, bystander

    async def test_both_parties_have_it_dead_and_the_bystander_is_told(self):
        leader, bystander = await self._kill(_TROLL)
        for c in (leader, bystander):
            self.assertIn(3, c.player.dead_monsters)
            self.assertEqual(c.player.slain_here, (1, 13, 3))
        self.assertIn('TROLL is slain!', _sent(bystander))

    async def test_re_animates_kill_is_dead_for_the_visit_only(self):
        leader, bystander = await self._kill(_WRAITH)
        for c in (leader, bystander):
            self.assertNotIn(70, c.player.dead_monsters)   # re-encounterable later
            self.assertEqual(monster_gone_for(c.player, 70, level=1, room_no=13), 'dead')


class TestLateAttackAfterTheKill(unittest.IsolatedAsyncioTestCase):

    async def _late(self, command_cls, monster, *, slain=True):
        """The other party's ATTACK/LURK arriving after the fight ended:
        the session is gone from active_combats, the monster is still in
        room.monster (shared), and this player was credited with the kill."""
        ctx = _ctx('Frodo', monster)
        if slain:
            ctx.player.slain_here = (1, 13, monster['number'])
        ctx.player.party = [MagicMock(hit_points=10, status=None)]
        with patch('combat.enter_combat', new=AsyncMock()) as enter, \
             patch('combat.lurk.has_living_ally', return_value=True):
            result = await command_cls().execute(ctx)
        return ctx, result, enter

    async def test_attack_does_not_open_a_second_fight(self):
        from commands.attack import AttackCommand
        ctx, result, enter = await self._late(AttackCommand, _TROLL)
        enter.assert_not_awaited()
        self.assertFalse(result.success)
        self.assertIn('The TROLL is already dead.', _sent(ctx))

    async def test_re_animates_monster_too(self):
        from commands.attack import AttackCommand
        ctx, result, enter = await self._late(AttackCommand, _WRAITH)
        enter.assert_not_awaited()

    async def test_lurk_does_not_open_a_second_fight(self):
        from commands.lurk import LurkCommand
        ctx, result, enter = await self._late(LurkCommand, _TROLL)
        enter.assert_not_awaited()
        self.assertIn('already dead', _sent(ctx))

    async def test_a_live_monster_still_starts_a_fight(self):
        from commands.attack import AttackCommand
        ctx, result, enter = await self._late(AttackCommand, _TROLL, slain=False)
        enter.assert_awaited_once()


class TestLeavingTheRoomClearsSlainHere(unittest.IsolatedAsyncioTestCase):

    async def test_teleport_clears_it(self):
        from simple_server import Server
        server = MagicMock()
        ctx = _ctx('Rulan', _WRAITH)
        ctx.player.slain_here = (1, 13, 70)
        server._show_room_then_encounter = AsyncMock()
        server._monster_engages = AsyncMock()
        with patch('visited_rooms.mark_visited'), \
             patch('shoppe.elevator.level_name', return_value=None), \
             patch('encounters.desert.try_desert_sweat', new=AsyncMock()), \
             patch('ally_events.try_ally_find_silver', new=AsyncMock()), \
             patch('wild_horse_events.try_wandering_horse_encounter', new=AsyncMock()), \
             patch('encounters.dwarf.maybe_relocate'), \
             patch('encounters.dwarf.try_steal', new=AsyncMock()), \
             patch('encounters.little_girl.try_encounter', new=AsyncMock()), \
             patch('encounters.meteor.try_encounter', new=AsyncMock()), \
             patch('encounters.ringwraith.try_wraith_stalks', new=AsyncMock()), \
             patch('encounters.galadriel.try_encounter', new=AsyncMock()), \
             patch('encounters.djinn_sighting.try_encounter', new=AsyncMock()), \
             patch('ally_events.starvation.try_encounter', new=AsyncMock()):
            await Server._teleport_to(server, ctx, 2, 5)
        self.assertIsNone(ctx.player.slain_here)


if __name__ == '__main__':
    unittest.main()
