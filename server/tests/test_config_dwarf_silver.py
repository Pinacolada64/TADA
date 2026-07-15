"""tests/test_config_dwarf_silver.py — The Dwarf's stolen silver, stored
server-wide in config.py's ServerConfig (server_config.json), not on any
one player's wallet (the previous PlayerMoneyTypes.DWARF approach was
already flagged FIXME as wrong for a single server-wide NPC).
"""
from __future__ import annotations

import unittest
from pathlib import Path

import config as config_module
from config import ServerConfig


class TestDwarfSilverConfig(unittest.TestCase):
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

    def test_defaults_to_zero(self):
        cfg = ServerConfig()
        self.assertEqual(cfg.dwarf_silver, 0)

    def test_set_and_get_round_trips(self):
        cfg = ServerConfig()
        cfg.dwarf_silver = 250
        self.assertEqual(cfg.dwarf_silver, 250)

    def test_persists_to_disk_across_instances(self):
        cfg = ServerConfig()
        cfg.dwarf_silver = 500
        # Force a fresh singleton to reload from disk, like a server restart.
        ServerConfig._instance = None
        reloaded = ServerConfig()
        self.assertEqual(reloaded.dwarf_silver, 500)

    def test_module_level_config_instance_exposes_same_property(self):
        # config.config is the shared instance other modules import.
        self.assertTrue(hasattr(config_module.config, 'dwarf_silver'))


if __name__ == '__main__':
    unittest.main()
