"""tests/social/test_tips.py — tip-of-the-day (tips.py, commands/tips.py,
command_settings.TipsSettings).
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from command_settings import CommandSettings, TipsSettings
from tips import load_tips, next_tip


class _FakePlayer:
    def __init__(self, tip_number=0, enabled=True):
        self.command_settings = CommandSettings(tips=TipsSettings(enabled=enabled, tip_number=tip_number))
        self.unsaved_changes = False
        self.client_settings = MagicMock()


class TestLoadTips(unittest.TestCase):
    def test_missing_file_returns_empty_list(self):
        self.assertEqual(load_tips(Path('/nonexistent/tips.json')), [])

    def test_real_file_loads_nonempty(self):
        tips = load_tips()
        self.assertGreater(len(tips), 0)
        self.assertTrue(all(isinstance(t, str) for t in tips))


class TestNextTip(unittest.TestCase):
    def _tips_path(self, tmp, tips):
        import json
        path = Path(tmp) / 'tips.json'
        path.write_text(json.dumps(tips))
        return path

    def test_no_tips_returns_none(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tips_path(tmp, [])
            from unittest.mock import patch
            with patch('tips.TIPS_FILE', path):
                player = _FakePlayer()
                self.assertIsNone(next_tip(player))

    def test_advances_from_zero_to_one(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tips_path(tmp, ['first', 'second', 'third'])
            with patch('tips.TIPS_FILE', path):
                player = _FakePlayer(tip_number=0)
                tip = next_tip(player)
                self.assertEqual(tip, 'first')
                self.assertEqual(player.command_settings.tips.tip_number, 1)
                self.assertTrue(player.unsaved_changes)

    def test_advances_sequentially(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tips_path(tmp, ['first', 'second', 'third'])
            with patch('tips.TIPS_FILE', path):
                player = _FakePlayer(tip_number=1)
                self.assertEqual(next_tip(player), 'second')
                self.assertEqual(player.command_settings.tips.tip_number, 2)

    def test_wraps_back_to_first_after_last(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            path = self._tips_path(tmp, ['first', 'second', 'third'])
            with patch('tips.TIPS_FILE', path):
                player = _FakePlayer(tip_number=3)
                self.assertEqual(next_tip(player), 'first')
                self.assertEqual(player.command_settings.tips.tip_number, 1)


class TestCommandSettingsTipsRoundTrip(unittest.TestCase):
    def test_default_has_tips_enabled(self):
        cs = CommandSettings()
        self.assertTrue(cs.tips.enabled)
        self.assertEqual(cs.tips.tip_number, 0)

    def test_to_dict_nests_tips(self):
        cs = CommandSettings(tips=TipsSettings(enabled=False, tip_number=5))
        d = cs.to_dict()
        self.assertEqual(d['tips'], {'enabled': False, 'tip_number': 5})

    def test_from_dict_reconstructs_tips_settings_instance(self):
        d = {'tips': {'enabled': False, 'tip_number': 7}}
        cs = CommandSettings.from_dict(d)
        self.assertIsInstance(cs.tips, TipsSettings)
        self.assertFalse(cs.tips.enabled)
        self.assertEqual(cs.tips.tip_number, 7)

    def test_from_dict_without_tips_key_uses_default(self):
        cs = CommandSettings.from_dict({})
        self.assertIsInstance(cs.tips, TipsSettings)
        self.assertTrue(cs.tips.enabled)
        self.assertEqual(cs.tips.tip_number, 0)


class TestTipsCommand(unittest.IsolatedAsyncioTestCase):
    def _ctx(self, tip_number=0, enabled=True):
        ctx = MagicMock()
        ctx.player = _FakePlayer(tip_number=tip_number, enabled=enabled)
        ctx.send = AsyncMock()
        return ctx

    async def test_bare_shows_next_tip_and_advances(self):
        from commands.tips import TipsCommand
        ctx = self._ctx(tip_number=0)
        result = await TipsCommand().execute(ctx)
        self.assertTrue(result.success)
        ctx.send.assert_awaited()
        self.assertEqual(ctx.player.command_settings.tips.tip_number, 1)

    async def test_hash_off_disables_and_does_not_advance(self):
        from commands.tips import TipsCommand
        ctx = self._ctx(tip_number=2)
        result = await TipsCommand().execute(ctx, '#off')
        self.assertTrue(result.success)
        self.assertFalse(ctx.player.command_settings.tips.enabled)
        self.assertEqual(ctx.player.command_settings.tips.tip_number, 2)

    async def test_hash_on_enables(self):
        from commands.tips import TipsCommand
        ctx = self._ctx(enabled=False)
        result = await TipsCommand().execute(ctx, '#on')
        self.assertTrue(result.success)
        self.assertTrue(ctx.player.command_settings.tips.enabled)


class TestLoginTipLines(unittest.TestCase):
    def _ctx(self, **kwargs):
        ctx = MagicMock()
        ctx.player = _FakePlayer(**kwargs)
        return ctx

    def test_disabled_returns_no_lines(self):
        from commands.connect import _login_tip_lines
        ctx = self._ctx(enabled=False)
        self.assertEqual(_login_tip_lines(ctx), [])

    def test_enabled_returns_lines_and_advances(self):
        from commands.connect import _login_tip_lines
        ctx = self._ctx(enabled=True, tip_number=0)
        lines = _login_tip_lines(ctx)
        self.assertTrue(lines)
        self.assertEqual(ctx.player.command_settings.tips.tip_number, 1)
        self.assertTrue(any('Tip #1' in l for l in lines))


if __name__ == '__main__':
    unittest.main()
