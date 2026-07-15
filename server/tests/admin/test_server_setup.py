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

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from config import SETTINGS_METADATA

# "Back to main menu" is always one past the last setting -- computed, not
# hardcoded, so this file doesn't silently break every time a setting is
# added or removed (already bit once: adding petscii_port shifted it).
_BACK = str(len(SETTINGS_METADATA) + 1)

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent


class TestServerSetupImports(unittest.TestCase):
    def test_module_imports_without_error(self):
        import setup.server_setup  # noqa: F401 -- the test IS the import succeeding

    def test_headline_is_a_plain_banner(self):
        import setup.server_setup as s
        self.assertIn('Hello', s.headline('Hello'))

    def test_runs_as_a_plain_script_from_server_dir(self):
        """Regression test: found live (hardcopy.9) -- `python3 setup/
        server_setup.py` run directly (not `python3 -m setup.
        server_setup`) only puts setup/ on sys.path, not server/ where
        config.py/item_system.py live, so every import in this module
        raised ModuleNotFoundError: No module named 'config'. A subprocess
        is the only way to catch this: pytest's own process already has
        server/ on sys.path for unrelated reasons, so importing the
        module in-process wouldn't have reproduced the bug."""
        result = subprocess.run(
            [sys.executable, 'setup/server_setup.py'],
            cwd=_SERVER_DIR, input='q\n', capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn('ModuleNotFoundError', result.stderr)
        self.assertIn('Server Setup', result.stdout)

    def test_runs_as_a_plain_script_from_repo_root(self):
        """Same as above, but launched from a directory that isn't
        server/ at all -- confirms the sys.path fix uses an absolute path
        anchored to the script's own location, not the caller's cwd."""
        result = subprocess.run(
            [sys.executable, 'server/setup/server_setup.py'],
            cwd=_SERVER_DIR.parent, input='q\n', capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn('ModuleNotFoundError', result.stderr)


class TestEditServerConfig(unittest.TestCase):
    """setup/server_setup.py imports the process-wide `config` singleton
    by reference (`from config import config`), not a fresh ServerConfig()
    per call -- resetting ServerConfig._instance/_config_file (as other
    config test files do) only affects *future* ServerConfig() constructor
    calls, not that already-bound object, so it silently doesn't isolate
    anything here. Found live: a stray 'item'/'both' leaked between runs.
    Isolating the actual shared singleton instance in place instead.
    """
    def setUp(self):
        from config import config as server_config
        self._server_config = server_config
        self._orig_config_file = server_config._config_file
        self._orig_config_data = dict(server_config._config)
        server_config._config_file = Path('run') / 'server' / 'test_server_config_setup.json'
        if server_config._config_file.exists():
            server_config._config_file.unlink()
        server_config._load_config()

    def tearDown(self):
        if self._server_config._config_file.exists():
            self._server_config._config_file.unlink()
        self._server_config._config_file = self._orig_config_file
        self._server_config._config = self._orig_config_data

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
