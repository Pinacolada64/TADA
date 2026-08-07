"""tests/test_battle_experience.py

Unit tests for weapon-specific battle experience (SPUR's `vp`).

SPUR.MISC.S:384 (`p.a3`, the monster-just-died cleanup routine) is the
ONLY place `vp` is ever incremented anywhere in the SPUR source -- checked
by grepping every .S file (master and skip branches) for `vp=vp+1`. This
port deliberately diverges from SPUR (Ryan's request, no SPUR precedent):
battle experience now grows for every human attacker in the fight
(CombatSession.attackers), scaled by how many blows *that* attacker
personally landed (session._hits_landed) -- not a flat +1 reserved for
whoever delivers the killing blow. It's still only awarded once, at
death, in _monster_dies() (see _award_hit_based_skill()) -- a swing that
hits but doesn't kill still doesn't grant anything until the fight ends,
per TestNonLethalSwingGrantsNoBattleExperience below.

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
        session = _session()
        session._hits_landed = {player.name: 1}
        await self._kill(ctx, session)
        self.assertEqual(player.weapon_experience.get('42'), 1)

    async def test_no_hits_landed_awards_nothing(self):
        """Player didn't land a hit this fight (e.g. an ally solo-killed
        it) -- no landed blows means no skill, regardless of player_killed."""
        weapon = _FakeWeapon(id_number=42)
        player = _FakePlayer(readied_weapon=weapon)
        ctx = _FakeCtx(player)
        await self._kill(ctx, _session(), player_killed=False)
        self.assertEqual(player.weapon_experience, {})

    async def test_no_readied_weapon_does_not_raise(self):
        player = _FakePlayer(readied_weapon=None)
        ctx = _FakeCtx(player)
        session = _session()
        session._hits_landed = {player.name: 1}
        await self._kill(ctx, session)   # should not raise
        self.assertEqual(player.weapon_experience, {})

    async def test_accumulates_across_multiple_kills(self):
        weapon = _FakeWeapon(id_number=7)
        player = _FakePlayer(readied_weapon=weapon, weapon_experience={'7': 5})
        ctx = _FakeCtx(player)
        session = _session()
        session._hits_landed = {player.name: 1}
        await self._kill(ctx, session)
        self.assertEqual(player.weapon_experience['7'], 6)

    async def test_caps_at_99(self):
        weapon = _FakeWeapon(id_number=7)
        player = _FakePlayer(readied_weapon=weapon, weapon_experience={'7': 99})
        ctx = _FakeCtx(player)
        session = _session()
        session._hits_landed = {player.name: 1}
        await self._kill(ctx, session)
        self.assertEqual(player.weapon_experience['7'], 99)

    async def test_different_weapons_track_separately(self):
        sword = _FakeWeapon(id_number=1)
        player = _FakePlayer(readied_weapon=sword, weapon_experience={'1': 3, '2': 50})
        ctx = _FakeCtx(player)
        session = _session()
        session._hits_landed = {player.name: 1}
        await self._kill(ctx, session)
        self.assertEqual(player.weapon_experience['1'], 4)
        self.assertEqual(player.weapon_experience['2'], 50)   # untouched

    async def test_multiple_hits_scale_skill_award(self):
        """Landing 3 blows this fight awards 3 points, not a flat 1."""
        weapon = _FakeWeapon(id_number=7)
        player = _FakePlayer(readied_weapon=weapon)
        ctx = _FakeCtx(player)
        session = _session()
        session._hits_landed = {player.name: 3}
        await self._kill(ctx, session)
        self.assertEqual(player.weapon_experience['7'], 3)


class TestMonsterDiesWithUnhashableContext(unittest.IsolatedAsyncioTestCase):
    """Regression coverage: _monster_dies() used to key its skill_notes dict
    by the ctx object itself. The real GameContext/PETSCIINetworkContext is a
    plain @dataclass (eq=True with no explicit __hash__), which Python makes
    unhashable -- so that dict comprehension raised "TypeError: unhashable
    type" on every real kill, aborting _monster_dies() partway through
    (before it ever reached the Dwarf's room.monster=0 cleanup or the "You
    have slain" message). Ryan's report: an ally-killed Dwarf stayed fully
    healed in the room for the next `attack`. Reproduced here with a
    dataclass ctx, matching the real class's unhashability, instead of the
    file's plain-class _FakeCtx (which is hashable by default and would
    silently miss this bug)."""

    async def test_ally_kill_with_unhashable_ctx_does_not_raise(self):
        from dataclasses import dataclass, field

        @dataclass
        class _UnhashableClient:
            room: int = 1

        @dataclass
        class _UnhashableServer:
            clients: dict = field(default_factory=dict)
            active_combats: dict = field(default_factory=dict)
            game_map: object = None

        @dataclass
        class _UnhashableCtx:
            player: object
            client: object = field(default_factory=_UnhashableClient)
            server: object = field(default_factory=_UnhashableServer)
            sent: list = field(default_factory=list)

            async def send(self, msg, **kwargs):
                self.sent.append(str(msg))

            async def send_room(self, *args, **kwargs):
                pass

        weapon = _FakeWeapon(id_number=42)
        player = _FakePlayer(readied_weapon=weapon)
        ctx = _UnhashableCtx(player=player)
        with self.assertRaises(TypeError):
            hash(ctx)   # sanity: this ctx really does mirror the real bug

        session = _session()
        session._hits_landed = {'KING ARTHUR': 1}
        with patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch.object(session, '_reveal_hidden_exit', new=AsyncMock()), \
             patch('combat.engine._record_kill'), \
             patch('combat.engine._give_silver'), \
             patch('combat.rewards.gold_from_monster', return_value=0):
            await session._monster_dies(ctx, player_killed=False)   # should not raise

        self.assertTrue(any('has slain' in line for line in ctx.sent))


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
