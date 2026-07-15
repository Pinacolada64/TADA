"""tests/test_config_ports.py — separate ansi_port/petscii_port config
(Ryan: "add separate port config for ansi and petscii").

Replaces the previous single 'port' key, which was never actually wired
to simple_server.py's real listeners anyway (it defaulted to 5001, not
DEFAULT_PORT's real 34083) -- dead scaffolding, not a working setting.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from config import SETTINGS_METADATA, ServerConfig


class _IsolatedConfigTest(unittest.TestCase):
    def setUp(self):
        self._orig_file = ServerConfig._config_file
        self._orig_instance = ServerConfig._instance
        ServerConfig._config_file = Path('run') / 'server' / 'test_server_config_ports.json'
        ServerConfig._instance = None
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()

    def tearDown(self):
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()
        ServerConfig._config_file = self._orig_file
        ServerConfig._instance = self._orig_instance


class TestPortDefaults(_IsolatedConfigTest):
    def test_ansi_port_default_matches_simple_server(self):
        # simple_server.py's DEFAULT_PORT
        self.assertEqual(ServerConfig().ansi_port, 34083)

    def test_petscii_port_default_matches_simple_server(self):
        # simple_server.py's PETSCII_PORT
        self.assertEqual(ServerConfig().petscii_port, 34064)

    def test_no_generic_port_key_remains(self):
        self.assertNotIn('port', SETTINGS_METADATA)
        self.assertNotIn('port', ServerConfig._default_config)


class TestPortsSetIndependently(_IsolatedConfigTest):
    def test_set_and_get_round_trip(self):
        cfg = ServerConfig()
        cfg.ansi_port = 40001
        cfg.petscii_port = 40002
        self.assertEqual(cfg.ansi_port, 40001)
        self.assertEqual(cfg.petscii_port, 40002)

    def test_changing_one_does_not_affect_the_other(self):
        cfg = ServerConfig()
        cfg.ansi_port = 50000
        self.assertEqual(cfg.petscii_port, 34064)

    def test_persists_across_instances(self):
        cfg = ServerConfig()
        cfg.ansi_port = 40001
        cfg.petscii_port = 40002
        ServerConfig._instance = None
        reloaded = ServerConfig()
        self.assertEqual(reloaded.ansi_port, 40001)
        self.assertEqual(reloaded.petscii_port, 40002)


if __name__ == '__main__':
    unittest.main()
