"""tests/test_config_command.py — CONFIG command: admin-only view/edit of
server_config.json (config.py's ServerConfig).
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from commands.config import ConfigCommand
from flags import PlayerFlags


def make_ctx(*, is_admin=True, is_dm=False, prompt_responses=None):
    player = MagicMock()
    player.name = 'Admin'
    player.query_flag = MagicMock(side_effect=lambda f: (
        (f == PlayerFlags.ADMIN and is_admin)
        or (f == PlayerFlags.DUNGEON_MASTER and is_dm)
    ))
    player.client_settings = MagicMock(screen_columns=80, border_style='single', return_key='Enter')

    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    # menu_system.run_menu() prompts for a choice each time the menu is
    # (re)displayed -- a queued response list lets tests drive it through
    # a menu item and back out; default (None) exits the menu immediately.
    responses = list(prompt_responses) if prompt_responses else [None]
    async def _prompt(*args, **kwargs):
        return responses.pop(0) if responses else None
    ctx.prompt = AsyncMock(side_effect=_prompt)
    return ctx


def _sent_text(ctx) -> str:
    out = []
    for call in ctx.send.call_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                out.extend(str(x) for x in arg)
            else:
                out.append(str(arg))
    return '\n'.join(out)


class TestConfigCommandPermissions(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_non_dm_is_rejected(self):
        ctx = make_ctx(is_admin=False, is_dm=False)
        result = await ConfigCommand().execute(ctx)
        self.assertFalse(result.success)
        self.assertIn('authority', _sent_text(ctx))

    async def test_admin_can_list(self):
        ctx = make_ctx(is_admin=True)
        result = await ConfigCommand().execute(ctx)
        self.assertTrue(result.success)

    async def test_dungeon_master_can_list(self):
        """Ryan: "when running config from within the game, it says I
        don't have permission, even though I set administrator/dungeon
        master flags" -- CONFIG used to check PlayerFlags.ADMIN only
        (matching ban.py/reload.py/teleport.py), not Dungeon Master too
        (matching commands/whereat.py's broader _is_privileged())."""
        ctx = make_ctx(is_admin=False, is_dm=True)
        result = await ConfigCommand().execute(ctx)
        self.assertTrue(result.success)

    async def test_bare_config_opens_menu_showing_settings(self):
        """No arguments -> the live menu (menu_system.py), not the old
        flat-text listing. Blank prompt response exits immediately."""
        ctx = make_ctx(is_admin=True)
        await ConfigCommand().execute(ctx)
        text = _sent_text(ctx)
        self.assertIn('Server Configuration', text)
        # Human-readable labels (config.SETTINGS_METADATA[key].label), not
        # raw snake_case keys -- Ryan: "instead of 'victory_item' display
        # 'Victory Item'".
        self.assertIn('Game Name', text)

    async def test_menu_item_edits_a_setting(self):
        # See TestConfigCommandIO's docstring: must isolate the actual
        # pre-bound `config` singleton object in place, not just reset
        # ServerConfig._instance/_config_file (which doesn't affect an
        # already-imported reference to the old instance).
        from config import config as server_config
        orig_config_file = server_config._config_file
        orig_config_data = dict(server_config._config)
        server_config._config_file = Path('run') / 'server' / 'test_server_config_menu.json'
        if server_config._config_file.exists():
            server_config._config_file.unlink()
        server_config._load_config()
        try:
            # SETTINGS_METADATA's first entry is 'game_name' -> menu choice "1".
            ctx = make_ctx(is_admin=True, prompt_responses=['1', "Ryan's Dungeon", None])
            await ConfigCommand().execute(ctx)
            self.assertEqual(server_config.game_name, "Ryan's Dungeon")
        finally:
            if server_config._config_file.exists():
                server_config._config_file.unlink()
            server_config._config_file = orig_config_file
            server_config._config = orig_config_data


class TestConfigCommandIO(unittest.IsolatedAsyncioTestCase):
    """commands/config.py imports the process-wide `config` singleton by
    reference (`from config import config as server_config`), not a fresh
    ServerConfig() per call -- resetting ServerConfig._instance/
    _config_file (as other config test files do) only affects *future*
    ServerConfig() constructor calls, not that already-bound object, so it
    silently doesn't isolate anything here. Found live: a stray
    'item'/'both' leaked from an unrelated test into this file's runs.
    Isolating the actual shared singleton instance in place instead.
    """
    def setUp(self):
        from config import config as server_config
        self._server_config = server_config
        self._orig_config_file = server_config._config_file
        self._orig_config_data = dict(server_config._config)
        server_config._config_file = Path('run') / 'server' / 'test_server_config_cmd.json'
        if server_config._config_file.exists():
            server_config._config_file.unlink()
        server_config._load_config()

    def tearDown(self):
        if self._server_config._config_file.exists():
            self._server_config._config_file.unlink()
        self._server_config._config_file = self._orig_config_file
        self._server_config._config = self._orig_config_data

    async def test_list_shows_known_settings(self):
        from config import SETTINGS_METADATA
        ctx = make_ctx()
        await ConfigCommand().execute(ctx)
        text = _sent_text(ctx)
        for key in ('game_name', 'session_time_limit_minutes', 'victory_type', 'dwarf_silver'):
            self.assertIn(SETTINGS_METADATA[key].label, text)

    async def test_show_one_includes_description(self):
        ctx = make_ctx()
        await ConfigCommand().execute(ctx, 'victory_type')
        text = _sent_text(ctx)
        self.assertIn('victory_type', text)
        self.assertIn('ladder up', text)

    async def test_unknown_key_rejected(self):
        ctx = make_ctx()
        result = await ConfigCommand().execute(ctx, 'not_a_real_setting')
        self.assertFalse(result.success)
        self.assertIn('Unknown setting', _sent_text(ctx))

    async def test_unique_abbreviation_shows_the_setting(self):
        ctx = make_ctx()
        result = await ConfigCommand().execute(ctx, 'victory_t')
        self.assertTrue(result.success)
        self.assertIn('victory_type', _sent_text(ctx))

    async def test_unique_abbreviation_sets_the_setting(self):
        from config import config as server_config
        ctx = make_ctx()
        result = await ConfigCommand().execute(ctx, 'session', '45')
        self.assertTrue(result.success)
        self.assertEqual(server_config.session_time_limit_minutes, 45)

    async def test_ambiguous_abbreviation_lists_candidates_not_a_guess(self):
        ctx = make_ctx()
        result = await ConfigCommand().execute(ctx, 'victory')
        self.assertFalse(result.success)
        text = _sent_text(ctx)
        self.assertIn('victory_type', text)
        self.assertIn('victory_gold_amount', text)
        self.assertIn('victory_item_number', text)

    async def test_set_string_value(self):
        from config import config as server_config
        ctx = make_ctx()
        result = await ConfigCommand().execute(ctx, 'game_name', "Ryan's", 'Dungeon')
        self.assertTrue(result.success)
        self.assertEqual(server_config.game_name, "Ryan's Dungeon")

    async def test_set_int_value(self):
        from config import config as server_config
        ctx = make_ctx()
        await ConfigCommand().execute(ctx, 'session_time_limit_minutes', '45')
        self.assertEqual(server_config.session_time_limit_minutes, 45)

    async def test_set_bool_value(self):
        from config import config as server_config
        ctx = make_ctx()
        await ConfigCommand().execute(ctx, 'require_invites', 'off')
        self.assertEqual(server_config.require_invites, False)
        await ConfigCommand().execute(ctx, 'require_invites', 'on')
        self.assertEqual(server_config.require_invites, True)

    async def test_set_invalid_int_rejected(self):
        ctx = make_ctx()
        result = await ConfigCommand().execute(ctx, 'max_players', 'not-a-number')
        self.assertFalse(result.success)
        self.assertIn('whole number', _sent_text(ctx))

    async def test_set_key_without_dedicated_property_actually_persists(self):
        """Regression test: host/max_players/invite_expiry_days have no
        @property on ServerConfig -- a naive setattr(server_config, key,
        value) would silently create a stray instance attribute instead
        of updating self._config, so the change would appear to succeed
        but never actually take. Found live via 'config port 9999'
        reporting the change while CONFIG (no args) kept showing the old
        value (before ansi_port/petscii_port had their own properties)."""
        from config import config as server_config
        ctx = make_ctx()
        await ConfigCommand().execute(ctx, 'max_players', '250')
        self.assertEqual(server_config.get('max_players'), 250)
        await ConfigCommand().execute(ctx, 'host', '0.0.0.0')
        self.assertEqual(server_config.get('host'), '0.0.0.0')
        await ConfigCommand().execute(ctx, 'invite_expiry_days', '14')
        self.assertEqual(server_config.get('invite_expiry_days'), 14)

    async def test_set_ansi_and_petscii_ports_separately(self):
        from config import config as server_config
        ctx = make_ctx()
        await ConfigCommand().execute(ctx, 'ansi_port', '40001')
        await ConfigCommand().execute(ctx, 'petscii_port', '40002')
        self.assertEqual(server_config.ansi_port, 40001)
        self.assertEqual(server_config.petscii_port, 40002)

    async def test_set_invalid_victory_type_rejected(self):
        ctx = make_ctx()
        result = await ConfigCommand().execute(ctx, 'victory_type', 'diamonds')
        self.assertFalse(result.success)


if __name__ == '__main__':
    unittest.main()
