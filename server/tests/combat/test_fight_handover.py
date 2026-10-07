"""tests/combat/test_fight_handover.py

Multi-party fights (combat/engine.py), three gaps left by the
shared-monster-kill fix:

  1. A player who joins someone else's fight (CombatSession.join()) now
     brings their own allies in too -- before, only the leader's party
     ever swung.
  2. When the fight's leader leaves it -- flees, dies, is petrified,
     disconnects -- while others are still fighting, the fight carries on:
     it stays in active_combats with no leader, and the next fighter to
     ATTACK/LURK takes over (join_or_lead() -> take_over()) against the
     same wounded monster. Before, it was dropped (or ended outright), so
     their next ATTACK opened a fresh full-HP fight.
  3. A guild follower moved along by its leader gets player.slain_here
     cleared, the same as the leader's own move.

Run with:
    .venv/bin/python3 -m pytest tests/combat/test_fight_handover.py -v
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from combat.engine import CombatSession, join_or_lead, release_leader
from combat.resolution import AttackResult


def _ctx(name, *, active=None, party=None):
    player = SimpleNamespace(name=name, hit_points=50, stats={}, readied_weapon=None,
                             party=party or [], map_level=1, unsaved_changes=False,
                             ammo_rounds=0, return_key='Enter', is_expert=True,
                             query_flag=lambda flag: False)
    ctx = MagicMock()
    ctx.player = player
    ctx.server = SimpleNamespace(active_combats=active if active is not None else {})
    ctx.client = SimpleNamespace(room=1)
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


def _session(hp=30):
    return CombatSession({'name': 'TROLL', 'number': 3, 'strength': hp, 'to_hit': 4}, room_no=1)


# ---------------------------------------------------------------------------
# 1. A joining player's allies swing too
# ---------------------------------------------------------------------------

class TestJoiningPlayersAlliesSwing(unittest.IsolatedAsyncioTestCase):

    async def _join(self, *, damage=0, ally_damage=0, is_lurking=False, lurk_fires=True):
        session = _session(hp=10)
        leader, joiner = _ctx('Leader'), _ctx('Joiner')
        session.leader = leader
        session.attackers = [leader]

        async def ally_swings(ctx):
            from combat.engine import _monster_hp, _set_monster_hp
            _set_monster_hp(session.monster, _monster_hp(session.monster) - ally_damage)
        session._ally_swings = AsyncMock(side_effect=ally_swings)
        session._try_class_tame = AsyncMock(return_value=False)
        session._narrate_player_swing = AsyncMock()
        session._monster_dies = AsyncMock()
        with patch.object(session, '_swing', return_value=AttackResult(hit=damage > 0, damage=damage)), \
             patch('combat.engine._add_exp', new=AsyncMock()), \
             patch('combat.engine.lurk.has_living_ally', return_value=True), \
             patch('combat.engine.lurk.resolve_swing', new=AsyncMock(return_value=lurk_fires)):
            await session.join(joiner, is_lurking=is_lurking)
        return session, joiner

    async def test_joiners_allies_swing_after_their_own_swing(self):
        session, joiner = await self._join(damage=1)
        session._ally_swings.assert_awaited_once_with(joiner)

    async def test_ally_landing_the_kill_ends_the_fight(self):
        session, joiner = await self._join(damage=1, ally_damage=20)
        session._monster_dies.assert_awaited_once_with(joiner, player_killed=False)

    async def test_lurk_that_doesnt_fire_still_sends_the_allies_in(self):
        session, joiner = await self._join(is_lurking=True, lurk_fires=False)
        session._ally_swings.assert_awaited_once_with(joiner)

    async def test_joiners_own_kill_skips_the_ally_swings(self):
        session, joiner = await self._join(damage=50)
        session._monster_dies.assert_awaited_once_with(joiner)
        session._ally_swings.assert_not_awaited()


# ---------------------------------------------------------------------------
# 2. The leader leaving doesn't reset the monster
# ---------------------------------------------------------------------------

class TestLeaderLeavesTheFight(unittest.IsolatedAsyncioTestCase):

    def _two_fighters(self, hp=30):
        active = {}
        session = _session(hp=hp)
        leader, other = _ctx('Leader', active=active), _ctx('Other', active=active)
        session.leader = leader
        session.attackers = [leader, other]
        active[1] = session
        return session, leader, other, active

    async def test_leader_death_takes_only_the_leader_out(self):
        session, leader, other, _ = self._two_fighters()
        await session._player_dies(leader)
        self.assertFalse(session._done.is_set())
        self.assertEqual(session.attackers, [other])

    async def test_leader_petrified_takes_only_the_leader_out(self):
        session, leader, other, _ = self._two_fighters()
        with patch('combat.engine._record_statue'):
            await session._player_petrified(leader)
        self.assertFalse(session._done.is_set())
        self.assertEqual(session.attackers, [other])

    async def test_last_fighter_dying_still_ends_it(self):
        session, leader, other, _ = self._two_fighters()
        session.attackers = [leader]
        await session._player_dies(leader)
        self.assertTrue(session._done.is_set())

    async def test_disconnect_at_the_prompt_leaves_the_fight(self):
        session, leader, other, _ = self._two_fighters()
        leader.prompt = AsyncMock(return_value=None)
        session._try_class_tame = AsyncMock(return_value=False)
        session._monster_turn = AsyncMock(return_value=False)
        await session._lead_rounds(leader)
        self.assertEqual(session.attackers, [other])
        self.assertFalse(session._done.is_set())

    def test_unfinished_fight_stays_registered_without_a_leader(self):
        session, leader, other, active = self._two_fighters()
        session._leave_fight(leader)               # e.g. fled
        release_leader(leader, session)
        self.assertIs(active.get(1), session)
        self.assertIsNone(session.leader)

    def test_finished_fight_comes_out_of_active_combats(self):
        session, leader, other, active = self._two_fighters()
        session._done.set()
        release_leader(leader, session)
        self.assertNotIn(1, active)

    def test_leader_who_left_some_other_way_is_taken_out(self):
        session, leader, other, active = self._two_fighters()
        release_leader(leader, session)            # still listed, e.g. an exception
        self.assertEqual(session.attackers, [other])
        self.assertIs(active.get(1), session)

    async def test_next_attack_takes_over_the_same_wounded_monster(self):
        session, leader, other, active = self._two_fighters(hp=7)
        session._leave_fight(leader)
        release_leader(leader, session)

        seen = {}

        async def lead(ctx, *, resumed=False):
            seen['resumed'] = resumed
            seen['hp'] = session.monster['strength']
            seen['leader'] = session.leader
        session._run_loop = AsyncMock(side_effect=lead)
        session.join = AsyncMock()
        await join_or_lead(other, session)

        session.join.assert_not_awaited()
        self.assertEqual(seen, {'resumed': True, 'hp': 7, 'leader': other})
        self.assertIsNone(session.leader)          # released again afterwards
        # The (mocked) round loop returned with the new leader still listed,
        # so release_leader() takes them out too -- the last one, so the
        # fight ends and comes out of active_combats.
        self.assertTrue(session._done.is_set())
        self.assertNotIn(1, active)

    async def test_fight_with_a_leader_is_joined_as_before(self):
        session, leader, other, _ = self._two_fighters()
        session.join = AsyncMock()
        session.take_over = AsyncMock()
        await join_or_lead(other, session, is_lurking=True)
        session.join.assert_awaited_once_with(other, is_lurking=True)
        session.take_over.assert_not_awaited()

    def test_last_fighter_walking_away_ends_a_leaderless_fight(self):
        from simple_server import Server
        session, leader, other, active = self._two_fighters()
        session._leave_fight(leader)
        release_leader(leader, session)
        server = Server.__new__(Server)
        server.active_combats = active
        Server._leave_combat_on_move(server, other, 1)
        self.assertTrue(session._done.is_set())
        self.assertNotIn(1, active)


# ---------------------------------------------------------------------------
# 3. Guild followers moved by their leader
# ---------------------------------------------------------------------------

class TestFollowerSlainHereCleared(unittest.TestCase):

    def test_relocated_follower_forgets_the_kill_left_behind(self):
        import guild_follow
        follower = _ctx('Frodo')
        follower.player.slain_here = (1, 13, 3)
        follower.player.map_room = 13
        follower.client = SimpleNamespace(room=13, map_level=1)
        leader = _ctx('Rulan')
        leader.server = SimpleNamespace(_leave_combat_on_move=lambda c, r: None)
        group = SimpleNamespace(moving=[follower])
        with patch('visited_rooms.mark_visited'):
            guild_follow.relocate_followers(leader, group, from_room=13, to_level=1, to_room=1)
        self.assertIsNone(follower.player.slain_here)
        self.assertEqual(follower.client.room, 1)


if __name__ == '__main__':
    unittest.main()
