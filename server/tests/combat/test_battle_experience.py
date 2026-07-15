"""tests/test_battle_experience.py

Unit tests for weapon-specific battle experience (SPUR's `vp`).

SPUR.MISC.S:384 (`p.a3`, the monster-just-died cleanup routine) is the
ONLY place `vp` is ever incremented anywhere in the SPUR source -- checked
by grepping every .S file (master and skip branches) for `vp=vp+1`. There
is no per-swing accrual; that was a bug in this port's earlier version,
which called _award_weapon_exp() after every swing (hit or miss) and even
credited every OTHER attacker in the room for the swinging player's
weapon. Battle experience now only grows for the ctx that actually lands
the killing blow, for whatever weapon it currently has readied
(CombatSession._monster_dies(), gated the same way as the WIS gain right
next to it: player_killed=False when an ally dealt the blow skips both).

`player.experience` (general per-swing character XP, SPUR's `ep`) is a
completely separate counter -- see combat/engine.py's _add_exp() -- and is
untouched by any of this.

Run with:
    python -m pytest tests/test_battle_experience.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from combat.engine import CombatSession


class _FakeWeapon:
    def __init__(self, id_number):
        self.id_number = id_number
        self.name = 'LONG SWORD'


class _FakePlayer:
    def __init__(self, readied_weapon=None, weapon_experience=None):
        self.name = 'Rulan'
        self.hit_points = 30
        self.unsaved_changes = False
        self.stats = {'Wisdom': 10}
        self.shield = 0
        self.armor = 0
        self.map_level = 1
        self.readied_weapon = readied_weapon
        self.weapon_experience = weapon_experience if weapon_experience is not None else {}

    def gain_weapon_experience(self, weapon_id_number: int) -> int:
        """Mirrors the real Player.gain_weapon_experience (player.py)."""
        key = str(weapon_id_number)
        current = int(self.weapon_experience.get(key, 0))
        if current < 99:
            self.weapon_experience[key] = current + 1
            self.unsaved_changes = True
        return int(self.weapon_experience.get(key, current))


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

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _session():
    return CombatSession({'name': 'GOBLIN', 'strength': 0, 'flags': {}}, room_no=1)


class TestBattleExperienceOnKill(unittest.IsolatedAsyncioTestCase):

    async def _kill(self, ctx, session, *, player_killed=True):
        with patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch.object(session, '_reveal_hidden_exit', new=AsyncMock()), \
             patch('combat.engine._record_kill'), \
             patch('combat.engine._give_silver'), \
             patch('combat.rewards.gold_from_monster', return_value=0):
            await session._monster_dies(ctx, player_killed=player_killed)

    async def test_killing_blow_awards_one_point_to_readied_weapon(self):
        weapon = _FakeWeapon(id_number=42)
        player = _FakePlayer(readied_weapon=weapon)
        ctx = _FakeCtx(player)
        await self._kill(ctx, _session())
        self.assertEqual(player.weapon_experience.get('42'), 1)

    async def test_ally_killing_blow_awards_nothing(self):
        weapon = _FakeWeapon(id_number=42)
        player = _FakePlayer(readied_weapon=weapon)
        ctx = _FakeCtx(player)
        await self._kill(ctx, _session(), player_killed=False)
        self.assertEqual(player.weapon_experience, {})

    async def test_no_readied_weapon_does_not_raise(self):
        player = _FakePlayer(readied_weapon=None)
        ctx = _FakeCtx(player)
        await self._kill(ctx, _session())   # should not raise
        self.assertEqual(player.weapon_experience, {})

    async def test_accumulates_across_multiple_kills(self):
        weapon = _FakeWeapon(id_number=7)
        player = _FakePlayer(readied_weapon=weapon, weapon_experience={'7': 5})
        ctx = _FakeCtx(player)
        await self._kill(ctx, _session())
        self.assertEqual(player.weapon_experience['7'], 6)

    async def test_caps_at_99(self):
        weapon = _FakeWeapon(id_number=7)
        player = _FakePlayer(readied_weapon=weapon, weapon_experience={'7': 99})
        ctx = _FakeCtx(player)
        await self._kill(ctx, _session())
        self.assertEqual(player.weapon_experience['7'], 99)

    async def test_different_weapons_track_separately(self):
        sword = _FakeWeapon(id_number=1)
        player = _FakePlayer(readied_weapon=sword, weapon_experience={'1': 3, '2': 50})
        ctx = _FakeCtx(player)
        await self._kill(ctx, _session())
        self.assertEqual(player.weapon_experience['1'], 4)
        self.assertEqual(player.weapon_experience['2'], 50)   # untouched


class TestNonLethalSwingGrantsNoBattleExperience(unittest.IsolatedAsyncioTestCase):
    """Regression coverage for the actual bug: a swing that HITS but doesn't
    kill used to award weapon exp anyway (and even credited every other
    attacker in the room for the swinger's weapon). Neither should happen
    now -- exercised through the real bystander join() path, not just
    _monster_dies() directly, so the fix is proven at the call site too."""

    async def test_bystander_non_lethal_hit_grants_no_weapon_exp(self):
        from combat.resolution import AttackResult

        weapon = _FakeWeapon(id_number=99)
        player = _FakePlayer(readied_weapon=weapon)
        ctx = _FakeCtx(player)
        # High monster HP so this one hit can't possibly be the killing blow.
        session = CombatSession({'name': 'TROLL', 'strength': 1000, 'flags': {}}, room_no=1)
        session.leader = MagicMock()   # pretend someone else is already fighting

        hit = AttackResult(hit=True, damage=1, weapon_id=99)
        with patch.object(session, '_swing', return_value=hit):
            await session.join(ctx)

        self.assertEqual(player.weapon_experience, {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
