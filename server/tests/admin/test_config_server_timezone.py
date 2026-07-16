"""tests/admin/test_config_server_timezone.py

Covers config.py's server_timezone setting -- lets a sysop declare what
IANA zone this codebase's naive datetime.now() timestamps (player.
last_connection, etc.) actually represent, so PREFS 'Z' Timezone's
'Server Local' option means something concrete instead of whatever the
OS happens to be set to. Editable via the in-game CONFIG command and
setup/server_setup.py's edit_server_config() -- both just iterate
SETTINGS_METADATA, so no separate wiring needed for either.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from config import SETTINGS_METADATA, ServerConfig, parse_value


class _IsolatedConfigTest(unittest.TestCase):
    def setUp(self):
        self._orig_file = ServerConfig._config_file
        self._orig_instance = ServerConfig._instance
        ServerConfig._config_file = Path('run') / 'server' / 'test_server_config_tz.json'
        ServerConfig._instance = None
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()

    def tearDown(self):
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()
        ServerConfig._config_file = self._orig_file
        ServerConfig._instance = self._orig_instance


class TestServerTimezoneMetadata(_IsolatedConfigTest):
    def test_registered_in_settings_metadata(self):
        self.assertIn('server_timezone', SETTINGS_METADATA)

    def test_default_is_blank(self):
        self.assertEqual(ServerConfig().server_timezone, '')

    def test_parse_value_is_a_plain_string(self):
        self.assertEqual(parse_value('server_timezone', 'America/New_York'), 'America/New_York')


class TestServerTimezoneValidation(_IsolatedConfigTest):
    def test_valid_iana_zone_accepted(self):
        cfg = ServerConfig()
        cfg.server_timezone = 'America/New_York'
        self.assertEqual(cfg.server_timezone, 'America/New_York')

    def test_invalid_zone_rejected(self):
        cfg = ServerConfig()
        with self.assertRaises(ValueError):
            cfg.server_timezone = 'Not/AZone'

    def test_invalid_zone_does_not_change_stored_value(self):
        cfg = ServerConfig()
        cfg.server_timezone = 'Europe/London'
        with self.assertRaises(ValueError):
            cfg.server_timezone = 'Nowhere/Real'
        self.assertEqual(cfg.server_timezone, 'Europe/London')

    def test_blank_clears_it(self):
        cfg = ServerConfig()
        cfg.server_timezone = 'Europe/London'
        cfg.server_timezone = ''
        self.assertEqual(cfg.server_timezone, '')

    def test_set_validated_routes_through_property(self):
        cfg = ServerConfig()
        cfg.set_validated('server_timezone', 'Asia/Tokyo')
        self.assertEqual(cfg.server_timezone, 'Asia/Tokyo')
        with self.assertRaises(ValueError):
            cfg.set_validated('server_timezone', 'Bogus/Zone')


class TestServerTimezonePersistence(_IsolatedConfigTest):
    def test_persists_across_instances(self):
        cfg = ServerConfig()
        cfg.server_timezone = 'Australia/Sydney'
        ServerConfig._instance = None
        reloaded = ServerConfig()
        self.assertEqual(reloaded.server_timezone, 'Australia/Sydney')


if __name__ == '__main__':
    unittest.main()
