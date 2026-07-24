"""tests/test_survival.py — survival.py's survival_tick() honoring
config.survival_tick_interval instead of a hardcoded constant.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from config import ServerConfig
from survival import survival_tick


class _FakePlayer:
    def __init__(self, food=20, drink=20, admin=False, dm=False):
        self.food = food
        self.drink = drink
        self.hit_points = 20
        self.poisoned = False
        self.diseased = False
        self.unsaved_changes = False
        self._admin = admin
        self._dm = dm
        self._flags: set = set()

    def query_flag(self, flag):
        from flags import PlayerFlags
        if flag == PlayerFlags.ADMIN:
            return self._admin
        if flag == PlayerFlags.DUNGEON_MASTER:
            return self._dm
        return flag in self._flags

    def set_flag(self, flag):
        self._flags.add(flag)

    def clear_flag(self, flag):
        self._flags.discard(flag)


class TestSurvivalTickInterval(unittest.TestCase):
    def setUp(self):
        self._orig_file = ServerConfig._config_file
        self._orig_instance = ServerConfig._instance
        ServerConfig._config_file = Path('run') / 'server' / 'test_server_config.json'
        ServerConfig._instance = None
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()

    def tearDown(self):
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()
        ServerConfig._config_file = self._orig_file
        ServerConfig._instance = self._orig_instance

    def test_no_depletion_before_interval_reached(self):
        from config import config
        config.survival_tick_interval = 5

        player = _FakePlayer()
        for _ in range(4):
            survival_tick(player)
        self.assertEqual(player.food, 20)
        self.assertEqual(player.drink, 20)

    def test_depletes_exactly_on_interval(self):
        from config import config
        config.survival_tick_interval = 5

        player = _FakePlayer()
        for _ in range(5):
            survival_tick(player)
        self.assertEqual(player.food, 19)
        self.assertEqual(player.drink, 19)

    def test_larger_interval_delays_depletion_further(self):
        from config import config
        config.survival_tick_interval = 30

        player = _FakePlayer()
        for _ in range(20):
            survival_tick(player)
        self.assertEqual(player.food, 20)
        self.assertEqual(player.drink, 20)

    def test_counter_is_persisted_on_the_player(self):
        """Regression: Ryan pointed out the counter used to be session-only
        (reset to 0 on every login), so a player could dodge hunger/thirst
        entirely by just logging out and back in. It's a plain attribute
        on Player now (see player.py's __init__/simple_keys), so a fresh
        object seeded with a prior count picks up where it left off."""
        from config import config
        config.survival_tick_interval = 5

        player = _FakePlayer()
        player._survival_counter = 4   # as if restored from a save file
        survival_tick(player)
        self.assertEqual(player.food, 19)
        self.assertEqual(player.drink, 19)

    def test_interval_of_minus_one_disables_depletion(self):
        """Ryan's ask: a sysop who doesn't want this feature at all can
        set survival_tick_interval to -1 to turn off depletion entirely."""
        from config import config
        config.survival_tick_interval = -1

        player = _FakePlayer()
        for _ in range(200):
            survival_tick(player)
        self.assertEqual(player.food, 20)
        self.assertEqual(player.drink, 20)


class TestSurvivalTickHungerThirstFlags(unittest.TestCase):
    def setUp(self):
        self._orig_file = ServerConfig._config_file
        self._orig_instance = ServerConfig._instance
        ServerConfig._config_file = Path('run') / 'server' / 'test_server_config.json'
        ServerConfig._instance = None
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()

    def tearDown(self):
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()
        ServerConfig._config_file = self._orig_file
        ServerConfig._instance = self._orig_instance

    def test_hunger_flag_set_when_food_low(self):
        from flags import PlayerFlags
        player = _FakePlayer(food=6, drink=20)
        survival_tick(player)
        self.assertTrue(player.query_flag(PlayerFlags.HUNGER))

    def test_hunger_flag_clear_when_food_not_low(self):
        from flags import PlayerFlags
        player = _FakePlayer(food=7, drink=20)
        player.set_flag(PlayerFlags.HUNGER)   # simulate a stale flag from earlier
        survival_tick(player)
        self.assertFalse(player.query_flag(PlayerFlags.HUNGER))

    def test_thirst_flag_set_when_drink_low(self):
        from flags import PlayerFlags
        player = _FakePlayer(food=20, drink=2)
        survival_tick(player)
        self.assertTrue(player.query_flag(PlayerFlags.THIRST))

    def test_thirst_flag_clear_when_drink_not_low(self):
        from flags import PlayerFlags
        player = _FakePlayer(food=20, drink=10)
        player.set_flag(PlayerFlags.THIRST)
        survival_tick(player)
        self.assertFalse(player.query_flag(PlayerFlags.THIRST))

    def test_flags_reflect_state_even_when_depletion_disabled(self):
        """Flag syncing isn't gated on the tick actually firing -- it
        should reflect whatever food/drink currently are (e.g. set by
        editplayer) regardless of survival_tick_interval."""
        from config import config
        from flags import PlayerFlags
        config.survival_tick_interval = -1

        player = _FakePlayer(food=2, drink=20)
        survival_tick(player)
        self.assertTrue(player.query_flag(PlayerFlags.HUNGER))


class TestSurvivalTickAdminImmunity(unittest.TestCase):
    def setUp(self):
        self._orig_file = ServerConfig._config_file
        self._orig_instance = ServerConfig._instance
        ServerConfig._config_file = Path('run') / 'server' / 'test_server_config.json'
        ServerConfig._instance = None
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()

    def tearDown(self):
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()
        ServerConfig._config_file = self._orig_file
        ServerConfig._instance = self._orig_instance

    def test_admin_is_immune(self):
        player = _FakePlayer(admin=True)
        for _ in range(50):
            msgs = survival_tick(player)
        self.assertEqual(msgs, [])
        self.assertEqual(player.food, 20)
        self.assertEqual(player.drink, 20)
        self.assertEqual(getattr(player, '_survival_counter', 0), 0)

    def test_dungeon_master_is_immune(self):
        player = _FakePlayer(dm=True)
        for _ in range(50):
            msgs = survival_tick(player)
        self.assertEqual(msgs, [])
        self.assertEqual(player.food, 20)
        self.assertEqual(player.drink, 20)

    def test_admin_immune_even_when_already_poisoned(self):
        player = _FakePlayer(admin=True)
        player.poisoned = True
        for _ in range(20):
            survival_tick(player)
        self.assertEqual(player.hit_points, 20)

    def test_ordinary_player_is_not_immune(self):
        from config import config
        config.survival_tick_interval = 5
        player = _FakePlayer()
        for _ in range(5):
            survival_tick(player)
        self.assertEqual(player.food, 19)


if __name__ == '__main__':
    unittest.main()
