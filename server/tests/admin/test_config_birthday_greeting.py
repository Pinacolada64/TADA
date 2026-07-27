"""tests/admin/test_config_birthday_greeting.py — the sysop-facing toggle
for logon_events/birthday.py (TODO.md's "Modular logon event" idea,
first concrete module).
"""
from __future__ import annotations

import unittest
from pathlib import Path

import config as config_module
from config import ServerConfig, SETTINGS_METADATA


class TestBirthdayGreetingConfig(unittest.TestCase):
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

    def test_defaults_to_enabled(self):
        cfg = ServerConfig()
        self.assertTrue(cfg.birthday_greeting_enabled)

    def test_set_and_get_round_trips(self):
        cfg = ServerConfig()
        cfg.birthday_greeting_enabled = False
        self.assertFalse(cfg.birthday_greeting_enabled)

    def test_persists_to_disk_across_instances(self):
        cfg = ServerConfig()
        cfg.birthday_greeting_enabled = False
        ServerConfig._instance = None
        reloaded = ServerConfig()
        self.assertFalse(reloaded.birthday_greeting_enabled)

    def test_registered_in_settings_metadata(self):
        self.assertIn('birthday_greeting_enabled', SETTINGS_METADATA)
        self.assertIs(SETTINGS_METADATA['birthday_greeting_enabled'].type, bool)

    def test_module_level_config_instance_exposes_same_property(self):
        self.assertTrue(hasattr(config_module.config, 'birthday_greeting_enabled'))


if __name__ == '__main__':
    unittest.main()
