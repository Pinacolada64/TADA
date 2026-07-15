"""tests/combat/test_little_girl.py — encounters/little_girl.py: the
"little girl" random encounter (SPUR.MISC6.S).
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import Map, PlayerClass, Room
from flags import PlayerFlags


def _make_map(room_flags=None, level=1):
    m = Map()
    rooms = {
        1: Room(number=1, name='Room One', desc='', exits={}, monster=0,
                flags=room_flags or []),
        2: Room(number=2, name='Room Two', desc='', exits={}, monster=5),
    }
    m.levels[level] = rooms
    if level == 1:
        m.rooms = rooms
    return m


class _FakeInventoryEntry:
    def __init__(self, item):
        self.item = item


class _FakeItem:
    def __init__(self, id_number, name):
        self.id_number = id_number
        self.name = name


class _FakeInventory:
    def __init__(self, items=()):
        self._entries = [_FakeInventoryEntry(i) for i in items]
        self.removed = []

    def entries(self, category=None):
        return self._entries

    def remove(self, item, quantity=1):
        self._entries = [e for e in self._entries if e.item is not item]
        self.removed.append(item)
        return True


def _make_player(seen=False, items=(), honor=1000, hit_points=30, stats=None,
                  char_class=None, ring_worn=False):
    player = MagicMock()
    player.name = 'Testerson'
    player.once_per_day = ['little_girl_seen'] if seen else []
    player.inventory = _FakeInventory(items)
    player.honor = honor
    player.hit_points = hit_points
    player.stats = stats or {
        'Strength': 10, 'Constitution': 10, 'Intelligence': 10,
        'Energy': 10, 'Wisdom': 10, 'Dexterity': 10,
    }
    player.char_class = char_class
    player.query_flag = MagicMock(
        side_effect=lambda f: ring_worn if f == PlayerFlags.RING_WORN else False
    )
    return player


def _make_ctx(room_no=1, player=None, game_map=None, prompt_returns=None, map_level=1):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player = player or _make_player()
    ctx.player.map_level = map_level
    ctx.server.game_map = game_map or _make_map()
    ctx.server.monsters = [
        {'number': 106, 'name': 'EVILYNN', 'strength': 18},
    ]
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(side_effect=prompt_returns or [])
    return ctx


class TestTryEncounterGating(unittest.IsolatedAsyncioTestCase):
    async def test_no_op_if_already_seen(self):
        from encounters.little_girl import try_encounter
        ctx = _make_ctx(player=_make_player(seen=True))
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.prompt.assert_not_awaited()

    async def test_no_op_if_room_has_monster(self):
        from encounters.little_girl import try_encounter
        ctx = _make_ctx(room_no=2)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.prompt.assert_not_awaited()

    async def test_no_op_when_roll_fails(self):
        from encounters.little_girl import try_encounter
        ctx = _make_ctx()
        with patch('random.uniform', return_value=99.0):
            await try_encounter(ctx)
        ctx.prompt.assert_not_awaited()

    async def test_marks_seen_on_trigger(self):
        from encounters.little_girl import try_encounter
        ctx = _make_ctx(prompt_returns=['I'])
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):  # ignore -> sad path
            await try_encounter(ctx)
        self.assertIn('little_girl_seen', ctx.player.once_per_day)


class TestArrivalFlavor(unittest.IsolatedAsyncioTestCase):
    """SPUR.MISC6.S's boat/spacesuit arrival line -- only in water/vacuum
    rooms, per the skip branch's version (see module docstring for why
    master's unconditional-on-level-6+ version isn't followed)."""

    async def test_no_arrival_line_in_dry_room(self):
        from encounters.little_girl import try_encounter
        game_map = _make_map(room_flags=[])
        ctx = _make_ctx(game_map=game_map, prompt_returns=['I'])
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertNotIn('pulls along', sent)
        self.assertNotIn('pulls alongside', sent)

    async def test_boat_in_water_room_below_level_6(self):
        from encounters.little_girl import try_encounter
        game_map = _make_map(room_flags=['water'])
        player = _make_player()
        player.map_level = 1
        ctx = _make_ctx(game_map=game_map, player=player, prompt_returns=['I'])
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('A little boat pulls alongside you..', sent)

    async def test_spacesuit_in_water_room_level_6_plus(self):
        from encounters.little_girl import try_encounter
        game_map = _make_map(room_flags=['water'], level=6)
        player = _make_player()
        ctx = _make_ctx(game_map=game_map, player=player, prompt_returns=['I'], map_level=6)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('A little spacesuit pulls along side, retro-rockets firing.', sent)


class TestAttackChoice(unittest.IsolatedAsyncioTestCase):
    async def test_attack_deducts_honor_and_enters_combat(self):
        from encounters.little_girl import try_encounter
        player = _make_player(honor=1000)
        ctx = _make_ctx(player=player, prompt_returns=['A'])
        with patch('random.uniform', return_value=0.0), \
             patch('combat.enter_combat', new=AsyncMock()) as mock_combat:
            await try_encounter(ctx)
        self.assertEqual(player.honor, 990)
        mock_combat.assert_awaited_once()
        monster_arg = mock_combat.await_args.args[1]
        self.assertEqual(monster_arg['number'], 106)

    async def test_knight_pays_larger_honor_penalty(self):
        from encounters.little_girl import try_encounter
        player = _make_player(honor=1000, char_class=PlayerClass.KNIGHT)
        ctx = _make_ctx(player=player, prompt_returns=['A'])
        with patch('random.uniform', return_value=0.0), \
             patch('combat.enter_combat', new=AsyncMock()):
            await try_encounter(ctx)
        self.assertEqual(player.honor, 985)


class TestIgnoreChoice(unittest.IsolatedAsyncioTestCase):
    async def test_ignore_can_still_trigger_attack(self):
        from encounters.little_girl import try_encounter
        ctx = _make_ctx(prompt_returns=['I'])
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=10), \
             patch('combat.enter_combat', new=AsyncMock()) as mock_combat:
            await try_encounter(ctx)
        mock_combat.assert_awaited_once()

    async def test_ignore_sad_path_reduces_int_and_wis(self):
        from encounters.little_girl import try_encounter
        player = _make_player(stats={'Intelligence': 10, 'Wisdom': 10})
        ctx = _make_ctx(player=player, prompt_returns=['I'])
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        self.assertEqual(player.stats['Intelligence'], 8)
        self.assertEqual(player.stats['Wisdom'], 7)


class TestGiveChoice(unittest.IsolatedAsyncioTestCase):
    async def test_give_removes_item_and_awards_honor(self):
        from encounters.little_girl import try_encounter
        item = _FakeItem(50, 'a rusty key')
        player = _make_player(items=[item], honor=1000, hit_points=30,
                               stats={'Strength': 10, 'Constitution': 10,
                                      'Intelligence': 10, 'Energy': 10, 'Wisdom': 10})
        ctx = _make_ctx(player=player, prompt_returns=['G', '1'])
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertEqual(player.inventory.removed, [item])
        self.assertEqual(player.honor, 1005)

    async def test_give_refuses_amulet_of_life(self):
        from encounters.little_girl import try_encounter
        item = _FakeItem(76, 'Amulet of Life')
        player = _make_player(items=[item])
        ctx = _make_ctx(player=player, prompt_returns=['G', '1'])
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertEqual(player.inventory.removed, [])
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('refuses to hold it', sent)

    async def test_give_refuses_worn_ring(self):
        from encounters.little_girl import try_encounter
        item = _FakeItem(67, 'ring')
        player = _make_player(items=[item], ring_worn=True)
        ctx = _make_ctx(player=player, prompt_returns=['G', '1'])
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertEqual(player.inventory.removed, [])

    async def test_give_low_stats_triggers_restoration(self):
        from encounters.little_girl import try_encounter
        item = _FakeItem(50, 'a rusty key')
        player = _make_player(
            items=[item], hit_points=5,
            stats={'Strength': 5, 'Constitution': 5, 'Intelligence': 10,
                   'Energy': 5, 'Wisdom': 10},
        )
        ctx = _make_ctx(player=player, prompt_returns=['G', '1'])
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        self.assertEqual(player.hit_points, 15)
        self.assertEqual(player.stats['Strength'], 15)
        self.assertEqual(player.stats['Energy'], 15)
        self.assertEqual(player.stats['Constitution'], 15)

    async def test_give_no_items_sends_message_without_prompt(self):
        from encounters.little_girl import try_encounter
        ctx = _make_ctx(player=_make_player(items=[]), prompt_returns=['G'])
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('No Items!', sent)
        self.assertIn('The girl peers in your sack hopefully..', sent)

    async def test_give_prints_peers_in_sack_line(self):
        from encounters.little_girl import try_encounter
        item = _FakeItem(50, 'a rusty key')
        ctx = _make_ctx(player=_make_player(items=[item]), prompt_returns=['G', '1'])
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('The girl peers in your sack hopefully..', sent)


class TestLoadHints(unittest.TestCase):
    def test_real_file_loads_nonempty(self):
        from encounters.little_girl import load_hints
        hints = load_hints()
        self.assertGreater(len(hints), 0)

    def test_no_typos_survive(self):
        from encounters.little_girl import load_hints
        hints = load_hints()
        joined = ' '.join(hints)
        self.assertNotIn('Gladerial', joined)
        self.assertNotIn('Tuts Treasure', joined)


if __name__ == '__main__':
    unittest.main()
