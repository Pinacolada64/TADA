"""tests/combat/test_monsters_killed_credit.py

Unit tests for CombatSession._monster_dies() crediting dead_monsters to
EVERY attacker in the fight, not just whoever landed the killing blow.

dead_monsters is the per-kill log (one entry per kill, not deduplicated);
player.monsters_killed (a @property on Player, not exercised by this fake-
player test) is just len(dead_monsters), the kill-count stat. dead_monsters
is also this port's own "have I already fought this monster" gate (no SPUR
precedent) -- combat/engine.py's _check_tactical_ambush() skips the ambush
roll for any monster number already in it, and MECHANICS.md documents it
as the equivalent of SPUR's xm$. Before this change, only the ctx passed to
_monster_dies() (the killer) ever got its own dead_monsters updated -- a
bystander who fought the whole battle alongside them got no credit, and
would still be eligible for a tactical ambush against that same monster
next encounter despite having already fought it. Ryan's request; distinct
from weapon battle-exp (vp), which IS deliberately killer-only -- see
test_battle_experience.py's docstring.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from combat.engine import CombatSession


class _FakePlayer:
    def __init__(self, name):
        self.name = name
        self.hit_points = 30
        self.unsaved_changes = False
        self.stats = {'Wisdom': 10}
        self.shield = 0
        self.armor = 0
        self.map_level = 1
        self.readied_weapon = None
        self.weapon_experience = {}
        self.dead_monsters = []


class _FakeClient:
    room = 1


class _FakeServer:
    def __init__(self):
        self.clients = {}
        self.active_combats = {}
        self.game_map = None


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self.client = _FakeClient()
        self.server = _FakeServer()
        self._sent: list[str] = []

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        pass


def _session():
    return CombatSession({'name': 'GOBLIN', 'number': 42, 'strength': 0, 'flags': {}}, room_no=1)


async def _kill(ctx, session, *, attackers=()):
    session.attackers = list(attackers)
    with patch.object(session, '_recover_ammo', new=AsyncMock()), \
         patch.object(session, '_reveal_hidden_exit', new=AsyncMock()), \
         patch('combat.engine._give_silver'), \
         patch('combat.rewards.gold_from_monster', return_value=0):
        await session._monster_dies(ctx, player_killed=True)


class TestMonstersKilledCreditsEveryAttacker(unittest.IsolatedAsyncioTestCase):

    async def test_killer_gets_credit(self):
        killer = _FakePlayer('Rulan')
        ctx = _FakeCtx(killer)
        await _kill(ctx, _session(), attackers=[ctx])
        self.assertIn(42, killer.dead_monsters)

    async def test_bystander_also_gets_credit(self):
        killer     = _FakePlayer('Rulan')
        bystander  = _FakePlayer('Wanderer')
        kctx = _FakeCtx(killer)
        bctx = _FakeCtx(bystander)
        await _kill(kctx, _session(), attackers=[kctx, bctx])
        self.assertIn(42, killer.dead_monsters)
        self.assertIn(42, bystander.dead_monsters)

    async def test_multiple_bystanders_all_credited(self):
        killer = _FakePlayer('Rulan')
        others = [_FakePlayer(f'Bystander{i}') for i in range(3)]
        kctx = _FakeCtx(killer)
        octxs = [_FakeCtx(p) for p in others]
        await _kill(kctx, _session(), attackers=[kctx, *octxs])
        for p in others:
            self.assertIn(42, p.dead_monsters)

    async def test_killing_the_same_monster_again_adds_another_entry(self):
        """dead_monsters is an append-only kill log, not deduplicated --
        killing the same monster type a second time over a career counts
        again (Ryan's request). monsters_killed (len(dead_monsters)) is
        the kill-count stat this feeds."""
        killer = _FakePlayer('Rulan')
        killer.dead_monsters = [42]
        ctx = _FakeCtx(killer)
        await _kill(ctx, _session(), attackers=[ctx])
        self.assertEqual(killer.dead_monsters.count(42), 2)

    async def test_someone_not_in_attackers_gets_no_credit(self):
        """A player who was never part of this fight (e.g. someone in a
        different room's session) must not be touched."""
        killer      = _FakePlayer('Rulan')
        uninvolved  = _FakePlayer('Elsewhere')
        ctx = _FakeCtx(killer)
        await _kill(ctx, _session(), attackers=[ctx])
        self.assertNotIn(42, uninvolved.dead_monsters)


if __name__ == '__main__':
    unittest.main(verbosity=2)
