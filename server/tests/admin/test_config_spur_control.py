"""tests/test_config_spur_control.py — SPUR.CONTROL.S-derived server
config: game name (config2), session time limit (time.set), and victory
conditions (object label). See config.py's ServerConfig for the full
citation/rationale on each.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from config import SETTINGS_METADATA, ServerConfig, resolve_key, setting_label


class TestSettingLabels(unittest.TestCase):
    """Human-readable display labels (Ryan: "instead of 'victory_item'
    display 'Victory Item'") -- SETTINGS_METADATA[key].label / the
    setting_label() fallback helper."""

    def test_every_metadata_entry_has_a_label(self):
        for key, info in SETTINGS_METADATA.items():
            self.assertTrue(info.label, f'{key} has no label')

    def test_specific_labels_match_the_requested_wording(self):
        self.assertEqual(SETTINGS_METADATA['victory_item_number'].label, 'Victory Item')
        self.assertEqual(SETTINGS_METADATA['game_name'].label, 'Game Name')
        self.assertEqual(SETTINGS_METADATA['ansi_port'].label, 'ANSI Port')
        self.assertEqual(SETTINGS_METADATA['petscii_port'].label, 'PETSCII Port')

    def test_setting_label_helper_matches_metadata(self):
        for key, info in SETTINGS_METADATA.items():
            self.assertEqual(setting_label(key), info.label)

    def test_setting_label_falls_back_for_unknown_key(self):
        self.assertEqual(setting_label('some_made_up_key'), 'Some Made Up Key')


class TestConfigFileIsAbsolute(unittest.TestCase):
    """Regression test: _config_file used to be a bare relative
    Path('server_config.json'), so it wrote wherever the *process's* cwd
    happened to be -- for setup/server_setup.py (runnable from server/,
    the repo root, or anywhere else) that meant a stray server_config.json
    could land outside server/ entirely. Found live via a test launched
    with cwd=repo root."""

    def test_default_config_file_is_absolute_and_in_server_dir(self):
        self.assertTrue(ServerConfig._config_file.is_absolute())
        self.assertEqual(ServerConfig._config_file.name, 'server_config.json')
        self.assertEqual(
            ServerConfig._config_file.parent,
            Path(__file__).resolve().parent.parent.parent,
        )


class TestResolveKey(unittest.TestCase):
    """Partial-name matching for CONFIG's <key> argument (Ryan: "please
    add partial key matching. that's a lot to type...")."""

    def test_exact_match(self):
        key, candidates = resolve_key('game_name')
        self.assertEqual(key, 'game_name')
        self.assertEqual(candidates, ['game_name'])

    def test_unique_prefix_expands(self):
        key, candidates = resolve_key('victory_t')
        self.assertEqual(key, 'victory_type')

    def test_unique_prefix_case_insensitive(self):
        key, candidates = resolve_key('VICTORY_T')
        self.assertEqual(key, 'victory_type')

    def test_ambiguous_prefix_lists_all_candidates(self):
        key, candidates = resolve_key('victory')
        self.assertIsNone(key)
        self.assertEqual(
            set(candidates),
            {'victory_type', 'victory_gold_amount', 'victory_item_number'},
        )

    def test_no_match_returns_empty_candidates(self):
        key, candidates = resolve_key('not_a_real_setting_prefix')
        self.assertIsNone(key)
        self.assertEqual(candidates, [])

    def test_every_metadata_key_resolves_to_itself(self):
        for k in SETTINGS_METADATA:
            key, _candidates = resolve_key(k)
            self.assertEqual(key, k)


class _IsolatedConfigTest(unittest.TestCase):
    def setUp(self):
        self._orig_file = ServerConfig._config_file
        self._orig_instance = ServerConfig._instance
        ServerConfig._config_file = Path('run') / 'server' / 'test_server_config_spur.json'
        ServerConfig._instance = None
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()

    def tearDown(self):
        if ServerConfig._config_file.exists():
            ServerConfig._config_file.unlink()
        ServerConfig._config_file = self._orig_file
        ServerConfig._instance = self._orig_instance


class TestGameName(_IsolatedConfigTest):
    def test_default(self):
        self.assertEqual(ServerConfig().game_name, 'The Land of Spur')

    def test_set_and_get_round_trips(self):
        cfg = ServerConfig()
        cfg.game_name = "Ryan's Dungeon"
        self.assertEqual(cfg.game_name, "Ryan's Dungeon")


class TestSessionTimeLimit(_IsolatedConfigTest):
    def test_default_is_unlimited(self):
        self.assertEqual(ServerConfig().session_time_limit_minutes, 0)

    def test_set_and_get_round_trips(self):
        cfg = ServerConfig()
        cfg.session_time_limit_minutes = 45
        self.assertEqual(cfg.session_time_limit_minutes, 45)

    def test_clamped_to_0_90(self):
        cfg = ServerConfig()
        cfg.session_time_limit_minutes = 500
        self.assertEqual(cfg.session_time_limit_minutes, 90)
        cfg.session_time_limit_minutes = -5
        self.assertEqual(cfg.session_time_limit_minutes, 0)


class TestVictoryCondition(_IsolatedConfigTest):
    def test_defaults(self):
        cfg = ServerConfig()
        self.assertEqual(cfg.victory_type, 'gold')
        self.assertEqual(cfg.victory_gold_amount, 5000)
        self.assertEqual(cfg.victory_item_number, 0)

    def test_victory_type_accepts_valid_values(self):
        cfg = ServerConfig()
        for value in ('gold', 'item', 'both'):
            cfg.victory_type = value
            self.assertEqual(cfg.victory_type, value)

    def test_victory_type_rejects_invalid_value(self):
        cfg = ServerConfig()
        with self.assertRaises(ValueError):
            cfg.victory_type = 'diamonds'

    def test_gold_amount_and_item_number_round_trip(self):
        cfg = ServerConfig()
        cfg.victory_gold_amount = 10000
        cfg.victory_item_number = 25  # oil painting, objects.json
        self.assertEqual(cfg.victory_gold_amount, 10000)
        self.assertEqual(cfg.victory_item_number, 25)

    def test_negative_amounts_clamp_to_zero(self):
        cfg = ServerConfig()
        cfg.victory_gold_amount = -100
        cfg.victory_item_number = -1
        self.assertEqual(cfg.victory_gold_amount, 0)
        self.assertEqual(cfg.victory_item_number, 0)

    def test_persists_across_instances(self):
        cfg = ServerConfig()
        cfg.victory_type = 'both'
        cfg.victory_gold_amount = 7500
        cfg.victory_item_number = 6  # large ruby
        ServerConfig._instance = None
        reloaded = ServerConfig()
        self.assertEqual(reloaded.victory_type, 'both')
        self.assertEqual(reloaded.victory_gold_amount, 7500)
        self.assertEqual(reloaded.victory_item_number, 6)


if __name__ == '__main__':
    unittest.main()
