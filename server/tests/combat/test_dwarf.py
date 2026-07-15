"""tests/combat/test_dwarf.py — encounters/dwarf.py: The Dwarf's placement,
per-move theft, and combat-kill payout.
"""
from __future__ import annotations

import datetime
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import Map, PlayerMoneyTypes, PlayerRace, Room, RoomAlignment
from flags import PlayerFlags


def _make_map():
    m = Map()
    rooms = {
        1: Room(number=1, name='Merchant Lobby', desc='', exits={'south': 13, 'rc': 2}),
        2: Room(number=2, name='Free Room A', desc='', exits={}),
        3: Room(number=3, name='Free Room B', desc='', exits={}),
        4: Room(number=4, name='Sword HQ', desc='', exits={},
                alignment=RoomAlignment.SWORD),
        5: Room(number=5, name='Watery Room', desc='', exits={}, flags=['water']),
    }
    m.levels[1] = rooms
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


def _make_player(silver=0, items=(), dwarf_alive=True, mounted=False, race=None):
    player = MagicMock()
    player.name = 'Testerson'
    player.char_race = race
    player.inventory = _FakeInventory(items)
    player._silver = {'IN_HAND': silver}
    player.get_silver = MagicMock(side_effect=lambda kind: player._silver.get('IN_HAND', 0))

    def _set_absolute(kind, amount):
        player._silver['IN_HAND'] = amount
    player.set_silver_absolute = MagicMock(side_effect=_set_absolute)

    flag_state = {PlayerFlags.DWARF_ALIVE: dwarf_alive, PlayerFlags.MOUNTED: mounted}
    player.query_flag = MagicMock(side_effect=lambda f: flag_state.get(f, False))

    def _clear(f, verbose=False):
        flag_state[f] = False
        return False, None
    player.clear_flag = MagicMock(side_effect=_clear)
    return player


def _make_ctx(room_no=2, player=None, game_map=None):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player = player or _make_player()
    ctx.player.map_level = 1
    ctx.server.game_map = game_map or _make_map()
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


def _isolated_state(test_case, tmp_dir):
    import encounters.dwarf as dwarf_mod
    from pathlib import Path
    patcher = patch.object(dwarf_mod, '_STATE_FILE', Path(tmp_dir) / 'dwarf_state.json')
    patcher.start()
    test_case.addCleanup(patcher.stop)


class TestEligibleRooms(unittest.TestCase):
    def test_excludes_shoppe_elevator_and_guild_rooms(self):
        from encounters.dwarf import _eligible_rooms
        eligible = _eligible_rooms(_make_map())
        self.assertNotIn(1, eligible)   # rc == 2, shoppe elevator
        self.assertNotIn(4, eligible)   # sword-aligned guild HQ
        self.assertIn(2, eligible)
        self.assertIn(3, eligible)
        self.assertIn(5, eligible)


class TestRelocate(unittest.TestCase):
    def test_relocate_places_and_persists(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import MONSTER_NUMBER, current_room, relocate
            game_map = _make_map()
            new_room = relocate(game_map)
            self.assertIn(new_room, (2, 3, 5))
            self.assertEqual(current_room(), new_room)
            self.assertEqual(game_map.get_room(1, new_room).monster, MONSTER_NUMBER)

    def test_relocate_clears_previous_room(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import MONSTER_NUMBER, relocate
            game_map = _make_map()
            game_map.get_room(1, 2).monster = MONSTER_NUMBER
            from encounters.dwarf import save_state
            save_state({'room': 2, 'last_moved': None})
            with patch('random.choice', return_value=3):
                relocate(game_map)
            self.assertEqual(game_map.get_room(1, 2).monster, 0)


class TestMaybeRelocate(unittest.TestCase):
    def test_first_placement_when_never_placed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import current_room, maybe_relocate
            ctx = _make_ctx()
            maybe_relocate(ctx)
            self.assertNotEqual(current_room(), 0)

    def test_no_relocation_before_interval_elapses(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import save_state, maybe_relocate
            save_state({'room': 2, 'last_moved': datetime.datetime.utcnow().isoformat()})
            ctx = _make_ctx()
            with patch('encounters.dwarf.relocate') as mock_relocate:
                maybe_relocate(ctx)
            mock_relocate.assert_not_called()

    def test_relocates_after_interval_elapses(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import save_state, maybe_relocate
            old = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
            save_state({'room': 2, 'last_moved': old.isoformat()})
            ctx = _make_ctx()
            with patch('encounters.dwarf.relocate') as mock_relocate:
                maybe_relocate(ctx)
            mock_relocate.assert_called_once()


class TestTrySteal(unittest.IsolatedAsyncioTestCase):
    async def test_no_op_when_not_placed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import try_steal
            ctx = _make_ctx(player=_make_player(silver=100))
            with patch('random.randint', return_value=1):
                await try_steal(ctx)
            self.assertEqual(ctx.player.get_silver('IN_HAND'), 100)

    async def test_steals_all_silver_when_carried(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import save_state, try_steal
            from config import config
            save_state({'room': 2, 'last_moved': datetime.datetime.utcnow().isoformat()})
            starting_hoard = config.dwarf_silver
            player = _make_player(silver=500)
            ctx = _make_ctx(room_no=2, player=player)
            with patch('random.randint', return_value=1):
                await try_steal(ctx)
            self.assertEqual(player.get_silver('IN_HAND'), 0)
            self.assertEqual(config.dwarf_silver, starting_hoard + 500)
            config.dwarf_silver = starting_hoard
            ctx.send_room.assert_awaited_once()
            room_args, room_kwargs = ctx.send_room.await_args
            self.assertIn('Testerson', room_args[0])
            self.assertNotIn('your', room_args[0])   # bystander view, third person
            self.assertTrue(room_kwargs.get('exclude_self'))

    async def test_steals_item_when_no_silver(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import save_state, try_steal
            save_state({'room': 2, 'last_moved': datetime.datetime.utcnow().isoformat()})
            item = _FakeItem(50, 'a rusty key')
            player = _make_player(silver=0, items=[item])
            ctx = _make_ctx(room_no=2, player=player)
            with patch('random.randint', return_value=1):
                await try_steal(ctx)
            self.assertEqual(player.inventory.removed, [item])

    async def test_flavor_line_when_nothing_to_steal(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import save_state, try_steal
            save_state({'room': 2, 'last_moved': datetime.datetime.utcnow().isoformat()})
            player = _make_player(silver=0, items=[])
            ctx = _make_ctx(room_no=2, player=player)
            with patch('random.randint', return_value=1):
                await try_steal(ctx)
            ctx.send.assert_awaited_once_with(
                'A short bearded person eyes you, grumbles, and wanders off empty-handed.'
            )

    async def test_safe_in_water_room(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import save_state, try_steal
            save_state({'room': 5, 'last_moved': datetime.datetime.utcnow().isoformat()})
            player = _make_player(silver=500)
            ctx = _make_ctx(room_no=5, player=player)
            with patch('random.randint', return_value=1):
                await try_steal(ctx)
            self.assertEqual(player.get_silver('IN_HAND'), 500)

    async def test_immune_player_not_robbed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import save_state, try_steal
            save_state({'room': 2, 'last_moved': datetime.datetime.utcnow().isoformat()})
            player = _make_player(silver=500, dwarf_alive=False)
            ctx = _make_ctx(room_no=2, player=player)
            with patch('random.randint', return_value=1):
                await try_steal(ctx)
            self.assertEqual(player.get_silver('IN_HAND'), 500)

    async def test_mounted_evasion(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import save_state, try_steal
            save_state({'room': 2, 'last_moved': datetime.datetime.utcnow().isoformat()})
            player = _make_player(silver=500, mounted=True)
            ctx = _make_ctx(room_no=2, player=player)
            # First randint(1,100) call is the 1% theft roll, second is the
            # 50% evasion roll -- both need to succeed/fail as scripted.
            with patch('random.randint', side_effect=[1, 1]):
                await try_steal(ctx)
            self.assertEqual(player.get_silver('IN_HAND'), 500)
            ctx.send.assert_awaited_with('The DWARF struggles to reach up towards you!')

    async def test_pixie_evasion(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import save_state, try_steal
            save_state({'room': 2, 'last_moved': datetime.datetime.utcnow().isoformat()})
            player = _make_player(silver=500, race=PlayerRace.PIXIE)
            ctx = _make_ctx(room_no=2, player=player)
            with patch('random.randint', side_effect=[1, 1]):
                await try_steal(ctx)
            self.assertEqual(player.get_silver('IN_HAND'), 500)
            ctx.send.assert_awaited_with('The DWARF swats at you angrily as you fly by!')


class TestOnKilled(unittest.IsolatedAsyncioTestCase):
    async def test_awards_hoard_clears_flag_and_relocates(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_state(self, tmp)
            from encounters.dwarf import (MONSTER_NUMBER, current_room, on_killed,
                                           save_state)
            from config import config

            game_map = _make_map()
            game_map.get_room(1, 2).monster = MONSTER_NUMBER
            save_state({'room': 2, 'last_moved': datetime.datetime.utcnow().isoformat()})
            starting_hoard = config.dwarf_silver
            config.dwarf_silver = 750

            player = _make_player(silver=100)
            player.name = 'Killerella'
            ctx = _make_ctx(room_no=2, player=player, game_map=game_map)

            import net_common
            from pathlib import Path
            orig_dir = net_common.run_server_dir
            with tempfile.TemporaryDirectory() as log_tmp:
                net_common.run_server_dir = log_tmp
                try:
                    lines = await on_killed(ctx)
                    log_text = (Path(log_tmp) / 'battle.log').read_text()
                finally:
                    net_common.run_server_dir = orig_dir

            self.assertEqual(player.get_silver('IN_HAND'), 850)
            self.assertEqual(config.dwarf_silver, 0)
            player.clear_flag.assert_called_once_with(PlayerFlags.DWARF_ALIVE)
            self.assertEqual(game_map.get_room(1, 2).monster, 0)
            self.assertIn('750', lines[0])
            self.assertIn('Killerella slew the Dwarf and claimed 750 silver!', log_text)

            config.dwarf_silver = starting_hoard


class TestVisibility(unittest.TestCase):
    def test_visible_to_checks_dwarf_alive_flag(self):
        from encounters.dwarf import visible_to
        self.assertTrue(visible_to(_make_player(dwarf_alive=True)))
        self.assertFalse(visible_to(_make_player(dwarf_alive=False)))


if __name__ == '__main__':
    unittest.main()
