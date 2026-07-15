"""tests/test_server_setup.py — setup/server_setup.py's config editor.

Regression coverage for a real bug: this script used to import
old_server.menu_system / old_server.commands.help / old_server.setup,
none of which exist anywhere in this checkout (no old_server package at
all) -- the whole module raised ModuleNotFoundError on import, making the
entire offline setup tool unusable. Fixed to use config.py's ServerConfig
directly, sharing SETTINGS_METADATA/resolve_key with the live in-game
CONFIG command (commands/config.py) so both list/validate the same
settings.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from config import SETTINGS_METADATA, ServerConfig

# "Back to main menu" is always one past the last setting -- computed, not
# hardcoded, so this file doesn't silently break every time a setting is
# added or removed (already bit once: adding petscii_port shifted it).
_BACK = str(len(SETTINGS_METADATA) + 1)


class TestServerSetupImports(unittest.TestCase):
    def test_module_imports_without_error(self):
        import setup.server_setup  # noqa: F401 -- the test IS the import succeeding

    def test_headline_is_a_plain_banner(self):
        import setup.server_setup as s
        self.assertIn('Hello', s.headline('Hello'))


class TestEditServerConfig(unittest.TestCase):
    def setUp(self):
        self._orig_file = ServerConfig._config_file
        self._orig_instance = ServerConfig._instance
        ServerConfig._config_file = Path('run') / 'server' / 'test_server_config_setup.json'
        ServerConfig._instance = None
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()

    def tearDown(self):
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()
        ServerConfig._config_file = self._orig_file
        ServerConfig._instance = self._orig_instance

    def test_edit_by_number(self):
        import setup.server_setup as s
        from config import config as server_config
        with patch('builtins.input', side_effect=['1', "Ryan's Dungeon", _BACK]):
            s.edit_server_config()
        self.assertEqual(server_config.game_name, "Ryan's Dungeon")

    def test_edit_by_unique_abbreviation(self):
        import setup.server_setup as s
        from config import config as server_config
        with patch('builtins.input', side_effect=['victory_t', 'both', _BACK]):
            s.edit_server_config()
        self.assertEqual(server_config.victory_type, 'both')

    def test_ambiguous_abbreviation_does_not_crash_or_guess(self):
        import setup.server_setup as s
        from config import config as server_config
        with patch('builtins.input', side_effect=['victory', _BACK]):
            s.edit_server_config()
        # Untouched -- ambiguous input must not silently pick one.
        self.assertEqual(server_config.victory_type, 'gold')

    def test_edit_game_config_and_edit_game_goal_route_to_same_editor(self):
        import setup.server_setup as s
        from config import config as server_config
        with patch('builtins.input', side_effect=['session', '30', _BACK]):
            s.edit_game_config()
        self.assertEqual(server_config.session_time_limit_minutes, 30)
        with patch('builtins.input', side_effect=['victory_g', '9000', _BACK]):
            s.edit_game_goal()
        self.assertEqual(server_config.victory_gold_amount, 9000)


if __name__ == '__main__':
    unittest.main()
