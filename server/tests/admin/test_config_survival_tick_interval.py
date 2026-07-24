"""tests/admin/test_config_survival_tick_interval.py — Sysop-tunable
commands-between-hunger/thirst-depletion setting (survival.py's
survival_tick()). Ryan felt the shipped default (10) was too aggressive;
rather than pick a new hardcoded value, it's now a CONFIG setting.

Also covers survival_max -- the maximum/starting value for the food/
drink counters themselves (survival.py's old hardcoded _MAX=20),
likewise sysop-tunable, and the same value commands/editplayer.py's
Food/Drink editors clamp to.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import config as config_module
from config import SETTINGS_METADATA, ServerConfig


class TestSurvivalTickIntervalConfig(unittest.TestCase):
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

    def test_defaults_to_ten(self):
        cfg = ServerConfig()
        self.assertEqual(cfg.survival_tick_interval, 10)

    def test_set_and_get_round_trips(self):
        cfg = ServerConfig()
        cfg.survival_tick_interval = 25
        self.assertEqual(cfg.survival_tick_interval, 25)

    def test_clamped_to_a_minimum_of_one(self):
        cfg = ServerConfig()
        cfg.survival_tick_interval = 0
        self.assertEqual(cfg.survival_tick_interval, 1)
        cfg.survival_tick_interval = -5
        self.assertEqual(cfg.survival_tick_interval, 1)

    def test_minus_one_is_preserved_as_the_disable_sentinel(self):
        cfg = ServerConfig()
        cfg.survival_tick_interval = -1
        self.assertEqual(cfg.survival_tick_interval, -1)

    def test_persists_to_disk_across_instances(self):
        cfg = ServerConfig()
        cfg.survival_tick_interval = 30
        ServerConfig._instance = None
        reloaded = ServerConfig()
        self.assertEqual(reloaded.survival_tick_interval, 30)

    def test_listed_in_settings_metadata(self):
        self.assertIn('survival_tick_interval', SETTINGS_METADATA)
        self.assertEqual(SETTINGS_METADATA['survival_tick_interval'].type, int)

    def test_module_level_config_instance_exposes_same_property(self):
        self.assertTrue(hasattr(config_module.config, 'survival_tick_interval'))


class TestSurvivalMaxConfig(unittest.TestCase):
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

    def test_defaults_to_twenty(self):
        cfg = ServerConfig()
        self.assertEqual(cfg.survival_max, 20)

    def test_set_and_get_round_trips(self):
        cfg = ServerConfig()
        cfg.survival_max = 40
        self.assertEqual(cfg.survival_max, 40)

    def test_clamped_to_a_minimum_of_one(self):
        cfg = ServerConfig()
        cfg.survival_max = 0
        self.assertEqual(cfg.survival_max, 1)
        cfg.survival_max = -5
        self.assertEqual(cfg.survival_max, 1)

    def test_persists_to_disk_across_instances(self):
        cfg = ServerConfig()
        cfg.survival_max = 50
        ServerConfig._instance = None
        reloaded = ServerConfig()
        self.assertEqual(reloaded.survival_max, 50)

    def test_listed_in_settings_metadata(self):
        self.assertIn('survival_max', SETTINGS_METADATA)
        self.assertEqual(SETTINGS_METADATA['survival_max'].type, int)

    def test_module_level_config_instance_exposes_same_property(self):
        self.assertTrue(hasattr(config_module.config, 'survival_max'))


if __name__ == '__main__':
    unittest.main()
