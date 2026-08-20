"""tests/admin/test_config_nightly_cron_toggles.py — sysop-facing on/off
toggles for tools/nightly_recruit_digest.py and
tools/nightly_guild_maintenance.py (CONFIG command). Mirrors
test_config_birthday_greeting.py's pattern.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import config as config_module
from config import ServerConfig, SETTINGS_METADATA

_KEYS = ('nightly_recruit_digest_enabled', 'nightly_guild_maintenance_enabled')


class TestNightlyCronToggles(unittest.TestCase):
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

    def test_both_default_to_enabled(self):
        cfg = ServerConfig()
        self.assertTrue(cfg.nightly_recruit_digest_enabled)
        self.assertTrue(cfg.nightly_guild_maintenance_enabled)

    def test_set_and_get_round_trip_independently(self):
        cfg = ServerConfig()
        cfg.nightly_recruit_digest_enabled = False
        self.assertFalse(cfg.nightly_recruit_digest_enabled)
        self.assertTrue(cfg.nightly_guild_maintenance_enabled)  # unaffected

    def test_persists_to_disk_across_instances(self):
        cfg = ServerConfig()
        cfg.nightly_recruit_digest_enabled = False
        cfg.nightly_guild_maintenance_enabled = False
        ServerConfig._instance = None
        reloaded = ServerConfig()
        self.assertFalse(reloaded.nightly_recruit_digest_enabled)
        self.assertFalse(reloaded.nightly_guild_maintenance_enabled)

    def test_registered_in_settings_metadata(self):
        for key in _KEYS:
            self.assertIn(key, SETTINGS_METADATA)
            self.assertIs(SETTINGS_METADATA[key].type, bool)

    def test_module_level_config_instance_exposes_same_properties(self):
        for key in _KEYS:
            self.assertTrue(hasattr(config_module.config, key))


if __name__ == '__main__':
    unittest.main()
