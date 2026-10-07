"""tests/commands/test_cast_travel_aura.py

Covers commands/cast.py's second pass: ELEVATOR UP/DOWN (U/L), TRANSPORT
TO SHOPPE (R) and the Aura spells (DISPEL POISON, APPLE A DAY, DRUID
HEALTH, WIZARD'S GLOW) -- SPUR.MISC3.S's cst.uplv/cst.dnlv/cst.shop/
cst.aura -- plus Wizard's Glow's knock-on effects in monster combat
(combat/resolution.py, combat/engine.py), duels (combat/duel.py) and at
login (dissipate_wizard_glow()).
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import spellbook
from base_classes import PlayerClass, PlayerMoneyTypes, PlayerStat
from combat.engine import CombatSession
from commands.cast import WIZARD_GLOW_ROUNDS, CastCommand, dissipate_wizard_glow
from flags import PlayerFlags
from inventory import Inventory
from items import Spell
from player import Player

_SUCCESS  = {'return_value': 1}              # roll well under any threshold
_BACKFIRE = {'side_effect': [10000, 1]}      # miss, then the <5 backfire roll


def _new_player(char_class=PlayerClass.WIZARD, intelligence=20, level=3, room=7) -> Player:
    player = Player(name='Rulan', char_class=char_class)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.inventory = Inventory(capacity=14)
    player.stats[PlayerStat.INT] = intelligence
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 0)
    player.map_level = level
    player.map_room = room
    return player


def _spell(name, effect_type, magnitude=7, cast_chance=90):
    return Spell(id_number=1, name=name, cast_chance=cast_chance,
                 effect_type=effect_type, effect_magnitude=magnitude,
                 charges=1, max_charges=1)


class _FakeMap:
    """levels: {level: {room_no: room}} -- room numbers 1..rooms_per_level."""

    def __init__(self, rooms_per_level=None, flags=None):
        rooms_per_level = rooms_per_level or {n: 10 for n in range(1, 9)}
        self.levels = {
            lvl: {n: SimpleNamespace(number=n, flags=list((flags or {}).get((lvl, n), [])),
                                     monster=0, exits={})
                  for n in range(1, count + 1)}
            for lvl, count in rooms_per_level.items()
        }

    def get_room(self, level, room_no):
        return self.levels.get(level, {}).get(room_no)


def _grid_map(level, *, width, numbers):
    """A _FakeMap whose *level* holds only *numbers*, laid out on a
    *width*-wide grid (south exits N -> N+width wherever both exist)."""
    game_map = _FakeMap({1: 10, 3: 50})
    game_map.levels[level] = {
        n: SimpleNamespace(number=n, flags=[], monster=0,
                           exits={'south': n + width} if n + width in numbers else {})
        for n in numbers
    }
    return game_map


class _FakeCtx:
    def __init__(self, player, *, game_map=None, active_combats=None):
        self.player = player
        self.sent: list = []
        self.room_said: list = []
        self.client = SimpleNamespace(room=player.map_room)
        self.server = SimpleNamespace(
            active_combats=active_combats or {},
            game_map=game_map or _FakeMap(),
            _teleport_to=AsyncMock(side_effect=self._teleport_to),
        )
        self._q = ['1']

    async def _teleport_to(self, ctx, level, room):
        self.player.map_level = level
        self.player.map_room = room
        self.client.room = room

    async def send(self, *args):
        for a in args:
            self.sent.extend(a if isinstance(a, list) else [a])

    async def send_room(self, line, exclude_self=False):
        self.room_said.append(line)

    async def prompt(self, prompt_text='', preamble_lines=None):
        return self._q.pop(0) if self._q else None

    def flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


async def _cast(player, spell, roll, **ctx_kwargs) -> _FakeCtx:
    spellbook.ensure_spellbook(player).contents.add(spell)
    ctx = _FakeCtx(player, **ctx_kwargs)
    with patch('commands.cast.random.randint', **roll):
        await CastCommand().execute(ctx)
    return ctx


def _monster(flags=None):
    return {'name': 'GOBLIN', 'number': 42, 'strength': 20, 'flags': flags or {}}


# ---------------------------------------------------------------------------
# ELEVATOR UP / ELEVATOR DOWN
# ---------------------------------------------------------------------------

class TestElevatorSpells(unittest.IsolatedAsyncioTestCase):
    async def test_elevator_up_moves_one_level_up_same_room(self):
        player = _new_player(level=3, room=7)
        ctx = await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS)
        self.assertEqual((player.map_level, player.map_room), (2, 7))
        self.assertIn('Spell successful!', ctx.flat())
        self.assertEqual(spellbook.spell_entries(player), [])

    async def test_bystanders_see_the_caster_go(self):
        player = _new_player(level=3)
        ctx = await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS)
        self.assertIn('Rulan shimmers and fades away!', ctx.room_said)

    async def test_elevator_up_backfire_sends_you_down(self):
        player = _new_player(level=3)
        ctx = await _cast(player, _spell('ELEVATOR UP', 'U'), _BACKFIRE)
        self.assertEqual(player.map_level, 4)
        self.assertIn('Spell backfired!', ctx.flat())

    async def test_elevator_up_fizzles_on_level_one(self):
        player = _new_player(level=1)
        ctx = await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS)
        self.assertEqual(player.map_level, 1)
        self.assertIn('Your spell fizzles...', ctx.flat())
        self.assertEqual(spellbook.spell_entries(player), [])  # still spent

    async def test_elevator_up_fizzles_on_the_ship_level(self):
        player = _new_player(level=6)
        ctx = await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS)
        self.assertEqual(player.map_level, 6)
        ctx.server._teleport_to.assert_not_awaited()

    async def test_elevator_down_moves_one_level_down(self):
        player = _new_player(level=4)
        await _cast(player, _spell('ELEVATOR DOWN', 'L'), _SUCCESS)
        self.assertEqual(player.map_level, 5)

    async def test_elevator_down_fizzles_below_level_four(self):
        player = _new_player(level=5)
        ctx = await _cast(player, _spell('ELEVATOR DOWN', 'L'), _SUCCESS)
        self.assertEqual(player.map_level, 5)
        self.assertIn('Your spell fizzles...', ctx.flat())

    async def test_elevator_down_backfire_sends_you_up(self):
        player = _new_player(level=2)
        await _cast(player, _spell('ELEVATOR DOWN', 'L'), _BACKFIRE)
        self.assertEqual(player.map_level, 1)

    async def test_elevator_fizzles_on_level_eight(self):
        player = _new_player(level=8)
        await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS)
        self.assertEqual(player.map_level, 8)

    async def test_missing_room_lands_in_the_nearest_room_on_the_new_grid(self):
        # Level 2 is a 5-wide grid holding rooms 1-11 and 19. Room 16 (col 0,
        # row 3) doesn't exist there: room 11 (col 0, row 2) is one step
        # away on the map, while 19 (col 3, row 3) is three -- even though
        # 19 is nearer by number.
        player = _new_player(level=3, room=16)
        await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS,
                    game_map=_grid_map(2, width=5, numbers=[*range(1, 12), 19]))
        self.assertEqual((player.map_level, player.map_room), (2, 11))

    async def test_nearest_room_ties_go_to_the_lower_number(self):
        # Room 8 (col 2, row 1) missing, and so are 3 and 13 above and below
        # it: 7 and 9 are both one step away.
        player = _new_player(level=3, room=8)
        await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS,
                    game_map=_grid_map(2, width=5, numbers=[1, 2, 4, 6, 7, 9, 10]))
        self.assertEqual(player.map_room, 7)

    async def test_without_a_grid_lands_in_the_nearest_room_number(self):
        player = _new_player(level=3, room=40)
        await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS,
                    game_map=_FakeMap({2: 10, 3: 50}))  # no south exits to vote with
        self.assertEqual((player.map_level, player.map_room), (2, 10))

    async def test_no_flee_room_blocks_it(self):
        player = _new_player(level=3, room=7)
        game_map = _FakeMap(flags={(3, 7): ['no_flee']})
        await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS, game_map=game_map)
        self.assertEqual(player.map_level, 3)

    async def test_tough_monster_blocks_it(self):
        player = _new_player(level=3, room=7)
        session = CombatSession(_monster({'tough': True}), room_no=7)
        await _cast(player, _spell('ELEVATOR UP', 'U'), _SUCCESS, active_combats={7: session})
        self.assertEqual(player.map_level, 3)

    async def test_escapes_an_ordinary_fight(self):
        player = _new_player(level=3, room=7)
        session = CombatSession(_monster(), room_no=7)
        ctx = _FakeCtx(player)
        session.attackers.append(ctx)
        ctx.server.active_combats[7] = session
        spellbook.ensure_spellbook(player).contents.add(_spell('ELEVATOR UP', 'U'))
        with patch('commands.cast.random.randint', return_value=1):
            await CastCommand().execute(ctx)
        self.assertEqual(player.map_level, 2)
        self.assertNotIn(ctx, session.attackers)
        self.assertTrue(session._done.is_set())


# ---------------------------------------------------------------------------
# TRANSPORT TO SHOPPE
# ---------------------------------------------------------------------------

class TestTransportToShoppe(unittest.IsolatedAsyncioTestCase):
    async def test_success_puts_you_in_room_one_and_into_the_shoppe(self):
        player = _new_player(level=2, room=9)
        with patch('commands.movement._enter_shoppe', new=AsyncMock()) as shoppe:
            ctx = await _cast(player, _spell('TRANSPORT TO SHOPPE', 'R'), _SUCCESS)
        shoppe.assert_awaited_once()
        self.assertEqual((player.map_level, player.map_room, ctx.client.room), (2, 1, 1))
        self.assertIn('Spell successful!', ctx.flat())

    async def test_level_six_goes_to_the_ships_stores(self):
        player = _new_player(level=6, room=9)
        with patch('commands.movement._enter_ship_stores', new=AsyncMock()) as stores, \
             patch('commands.movement._enter_shoppe', new=AsyncMock()) as shoppe:
            await _cast(player, _spell('TRANSPORT TO SHOPPE', 'R'), _SUCCESS)
        stores.assert_awaited_once()
        shoppe.assert_not_awaited()

    async def test_ordinary_monster_looks_puzzled(self):
        player = _new_player(level=2, room=9)
        session = CombatSession(_monster(), room_no=9)
        with patch('commands.movement._enter_shoppe', new=AsyncMock()):
            ctx = await _cast(player, _spell('TRANSPORT TO SHOPPE', 'R'), _SUCCESS,
                              active_combats={9: session})
        self.assertIn('The goblin looks puzzled as you fade from view.'.lower(), ctx.flat().lower())

    async def test_tough_monster_freezes_you(self):
        player = _new_player(level=2, room=9)
        session = CombatSession(_monster({'tough': True}), room_no=9)
        with patch('commands.movement._enter_shoppe', new=AsyncMock()) as shoppe:
            ctx = await _cast(player, _spell('TRANSPORT TO SHOPPE', 'R'), _SUCCESS,
                              active_combats={9: session})
        shoppe.assert_not_awaited()
        self.assertIn("'Freeze Adventurer' spell!", ctx.flat())
        self.assertIn('Your spell fizzles...', ctx.flat())
        self.assertEqual(player.map_room, 9)

    async def test_backfire_drops_you_somewhere_random_on_this_level(self):
        player = _new_player(level=2, room=9)
        ctx = await _cast(player, _spell('TRANSPORT TO SHOPPE', 'R'),
                          {'side_effect': [10000, 1, 4]})  # miss, backfire, room choice
        self.assertIn('Spell backfired!', ctx.flat())
        self.assertEqual(player.map_level, 2)
        ctx.server._teleport_to.assert_awaited_once()


# ---------------------------------------------------------------------------
# Aura spells
# ---------------------------------------------------------------------------

class TestAuraSpells(unittest.IsolatedAsyncioTestCase):
    async def test_dispel_poison_cures_poison(self):
        from survival import apply_poison
        player = _new_player()
        apply_poison(player)
        ctx = await _cast(player, _spell('DISPEL POISON', 'A'), _SUCCESS)
        self.assertFalse(player.poisoned)
        self.assertFalse(player.query_flag(PlayerFlags.POISON))
        self.assertIn('Poison.. gone!', ctx.flat())

    async def test_dispel_poison_fizzles_when_not_poisoned(self):
        player = _new_player()
        ctx = await _cast(player, _spell('DISPEL POISON', 'A'), _SUCCESS)
        self.assertIn("Why? You weren't poisoned!", ctx.flat())
        self.assertIn('Your spell fizzles...', ctx.flat())
        self.assertEqual(spellbook.spell_entries(player), [])

    async def test_aura_never_backfires(self):
        from survival import apply_poison
        player = _new_player()
        apply_poison(player)
        ctx = await _cast(player, _spell('DISPEL POISON', 'A'), _BACKFIRE)
        self.assertFalse(player.poisoned)
        self.assertIn('Spell successful!', ctx.flat())
        self.assertNotIn('backfired', ctx.flat())

    async def test_apple_a_day_cures_disease(self):
        from survival import apply_disease
        player = _new_player()
        apply_disease(player)
        ctx = await _cast(player, _spell('APPLE A DAY', 'A'), _SUCCESS)
        self.assertFalse(player.diseased)
        self.assertIn('You feel much better!', ctx.flat())

    async def test_apple_a_day_fizzles_when_healthy(self):
        player = _new_player()
        ctx = await _cast(player, _spell('APPLE A DAY', 'A'), _SUCCESS)
        self.assertIn("Why, you don't have a disease!", ctx.flat())

    async def test_druid_health_restores_everything(self):
        from survival import apply_disease, apply_poison
        player = _new_player(char_class=PlayerClass.DRUID)
        player.hit_points = 5
        player.stats[PlayerStat.STR] = 8
        player.stats[PlayerStat.EGY] = 22   # already above the floor: untouched
        player.stats[PlayerStat.CON] = 3
        apply_poison(player)
        apply_disease(player)
        ctx = await _cast(player, _spell('DRUID HEALTH', 'A'), _SUCCESS)
        self.assertEqual(player.hit_points, 25)
        self.assertEqual(player.stats[PlayerStat.STR], 20)
        self.assertEqual(player.stats[PlayerStat.EGY], 22)
        self.assertEqual(player.stats[PlayerStat.CON], 20)
        self.assertFalse(player.poisoned or player.diseased)
        for line in ('A blue glow surrounds you!', 'Hit points return', 'Strength returns',
                     'Health returns', 'Poison gone!', 'Disease gone!'):
            self.assertIn(line, ctx.flat())
        self.assertNotIn('Energy returns', ctx.flat())

    async def test_wizards_glow_starts_the_aura(self):
        player = _new_player()
        ctx = await _cast(player, _spell("WIZARD'S GLOW", 'A'), _SUCCESS)
        self.assertEqual(player.wizard_glow, WIZARD_GLOW_ROUNDS)
        self.assertIn('A shimmering glow surrounds you!', ctx.flat())

    async def test_wizards_glow_already_active_fizzles(self):
        player = _new_player()
        player.wizard_glow = 3
        ctx = await _cast(player, _spell("WIZARD'S GLOW", 'A'), _SUCCESS)
        self.assertEqual(player.wizard_glow, 3)
        self.assertIn('Spell already in effect!', ctx.flat())


# ---------------------------------------------------------------------------
# Wizard's Glow effects outside CAST
# ---------------------------------------------------------------------------

class TestWizardGlowInMonsterCombat(unittest.TestCase):
    def _attack(self, glow):
        from combat.resolution import monster_attacks
        player = _new_player()
        player.wizard_glow = glow
        player.shield = 0
        player.armor = 0
        monster = {'name': 'GOBLIN', 'strength': 5, 'size': 5, 'flags': {}}
        with patch('combat.resolution.random.randint', return_value=1), \
             patch('logon_events.birthday.is_birthday_today', return_value=False):
            return monster_attacks(monster, player)

    def test_glow_takes_two_off_a_hit(self):
        plain, glowing = self._attack(None), self._attack(5)
        self.assertTrue(plain.hit and glowing.hit)
        self.assertEqual(glowing.glow_absorbed, 2)
        self.assertEqual(glowing.damage, plain.damage - 2)

    def test_no_glow_absorbs_nothing(self):
        self.assertEqual(self._attack(None).glow_absorbed, 0)


class TestWizardGlowRoundsSpent(unittest.TestCase):
    def _apply(self, rounds):
        from combat.resolution import MonsterAttackResult
        player = _new_player()
        player.wizard_glow = rounds
        session = CombatSession(_monster(), room_no=1)
        ctx = SimpleNamespace(player=player)
        session._apply_monster_damage(ctx, MonsterAttackResult(hit=True, damage=1, glow_absorbed=2))
        return player

    def test_each_absorbed_hit_spends_a_round(self):
        self.assertEqual(self._apply(5).wizard_glow, 4)

    def test_last_round_ends_the_glow(self):
        self.assertIsNone(self._apply(1).wizard_glow)


class TestWizardGlowInDuels(unittest.TestCase):
    def test_glow_adds_twenty_to_the_duel_shield(self):
        from combat.duel import _duel_shield
        player = _new_player()
        player.shield = 30
        self.assertEqual(_duel_shield(player), 30)
        player.wizard_glow = 4
        self.assertEqual(_duel_shield(player), 50)

    def test_glow_only_block_never_wears_down_a_missing_shield(self):
        from combat.duel import _absorb_shield_armor
        attacker, defender = _new_player(), _new_player()
        defender.shield, defender.armor, defender.wizard_glow = 0, 0, 4
        with patch('combat.duel.random.randint', return_value=0):
            result = _absorb_shield_armor(10.0, attacker, defender)
        _remaining, shield_blocked, _ab, shield_degraded, _ad, shield_destroyed, _ax = result
        self.assertGreater(shield_blocked, 0)
        self.assertEqual(shield_degraded, 0)
        self.assertFalse(shield_destroyed)


class TestWizardGlowAtLogin(unittest.TestCase):
    def test_an_active_glow_dissipates(self):
        player = _new_player()
        player.wizard_glow = 7
        self.assertTrue(dissipate_wizard_glow(player))
        self.assertIsNone(player.wizard_glow)

    def test_nothing_to_dissipate(self):
        player = _new_player()
        player.wizard_glow = None
        self.assertFalse(dissipate_wizard_glow(player))


if __name__ == '__main__':
    unittest.main()
