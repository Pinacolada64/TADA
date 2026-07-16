"""tests/client/test_prefs_timezone_date_format.py

Covers commands/prefs.py's 'Z' (Timezone) and 'D' (Date Format) rows,
formatting.format_player_datetime(), and the client_settings save/load
round trip that had to be fixed alongside them -- Player._load() never
restored client_settings at all before this (every PREFS choice reset
to default on reconnect); see terminal.py's ClientSettings.to_dict()/
from_dict() and player.py's save()/_load().
"""
from __future__ import annotations

import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from player import Player
from commands.prefs import _pick_timezone, _pick_date_format
from formatting import format_player_datetime
from terminal import ClientSettings, ColorName


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestPickTimezone(unittest.IsolatedAsyncioTestCase):
    async def test_numbered_preset(self):
        ctx = _FakeCtx(['3'], Player())  # US Eastern
        await _pick_timezone(ctx)
        self.assertEqual(ctx.player.client_settings.timezone, 'America/New_York')
        self.assertIn('US Eastern', ctx._flat())

    async def test_server_local_preset_stores_empty_string(self):
        p = Player()
        p.client_settings.timezone = 'UTC'
        ctx = _FakeCtx(['1'], p)  # Server Local
        await _pick_timezone(ctx)
        self.assertEqual(ctx.player.client_settings.timezone, '')

    async def test_typed_valid_iana_zone(self):
        ctx = _FakeCtx(['Asia/Kolkata'], Player())
        await _pick_timezone(ctx)
        self.assertEqual(ctx.player.client_settings.timezone, 'Asia/Kolkata')

    async def test_typed_invalid_zone_rejected(self):
        p = Player()
        p.client_settings.timezone = 'UTC'
        ctx = _FakeCtx(['Not/AZone'], p)
        await _pick_timezone(ctx)
        self.assertEqual(ctx.player.client_settings.timezone, 'UTC')  # unchanged
        self.assertIn("isn't a recognized zone", ctx._flat())

    async def test_blank_leaves_unchanged(self):
        p = Player()
        p.client_settings.timezone = 'UTC'
        ctx = _FakeCtx([''], p)
        await _pick_timezone(ctx)
        self.assertEqual(ctx.player.client_settings.timezone, 'UTC')

    async def test_name_match_case_insensitive(self):
        ctx = _FakeCtx(['us pacific'], Player())
        await _pick_timezone(ctx)
        self.assertEqual(ctx.player.client_settings.timezone, 'America/Los_Angeles')


class TestPickDateFormat(unittest.IsolatedAsyncioTestCase):
    async def test_numbered_preset(self):
        ctx = _FakeCtx(['4'], Player())  # YYYY-MM-DD
        await _pick_date_format(ctx)
        self.assertEqual(ctx.player.client_settings.date_format, '%Y-%m-%d')
        self.assertIn('YYYY-MM-DD', ctx._flat())

    async def test_name_match(self):
        ctx = _FakeCtx(['MM/DD/YYYY'], Player())
        await _pick_date_format(ctx)
        self.assertEqual(ctx.player.client_settings.date_format, '%m/%d/%Y')

    async def test_invalid_choice_unchanged(self):
        p = Player()
        p.client_settings.date_format = '%Y-%m-%d'
        ctx = _FakeCtx(['99'], p)
        await _pick_date_format(ctx)
        self.assertEqual(ctx.player.client_settings.date_format, '%Y-%m-%d')
        self.assertIn('unchanged', ctx._flat())

    async def test_blank_leaves_unchanged(self):
        p = Player()
        p.client_settings.date_format = '%Y-%m-%d'
        ctx = _FakeCtx([''], p)
        await _pick_date_format(ctx)
        self.assertEqual(ctx.player.client_settings.date_format, '%Y-%m-%d')

    async def test_preview_shown_for_each_preset(self):
        ctx = _FakeCtx([''], Player())
        await _pick_date_format(ctx)
        text = ctx._flat()
        self.assertIn('Month Day, Year', text)
        self.assertIn('MM/DD/YYYY', text)
        self.assertIn('DD/MM/YYYY', text)
        self.assertIn('YYYY-MM-DD', text)
        self.assertIn('Day Month Year', text)


class TestFormatPlayerDatetime(unittest.TestCase):
    def _player(self, timezone='', date_format=''):
        p = Player()
        if timezone:
            p.client_settings.timezone = timezone
        if date_format:
            p.client_settings.date_format = date_format
        return p

    def test_default_format_and_no_timezone_conversion(self):
        dt = datetime.datetime(2026, 7, 16, 14, 30)
        result = format_player_datetime(dt, self._player())
        self.assertEqual(result, 'July 16, 2026')

    def test_custom_date_format(self):
        dt = datetime.datetime(2026, 7, 16, 14, 30)
        player = self._player(date_format='%Y-%m-%d')
        self.assertEqual(format_player_datetime(dt, player), '2026-07-16')

    def test_timezone_conversion_changes_the_date(self):
        # 2026-07-16 23:30 local -> next day in a zone ~10h ahead.
        dt = datetime.datetime(2026, 7, 16, 23, 30)
        player = self._player(timezone='Pacific/Auckland', date_format='%Y-%m-%d %H:%M')
        result = format_player_datetime(dt, player)
        self.assertNotEqual(result, '2026-07-16 23:30')

    def test_invalid_timezone_falls_back_to_server_local(self):
        dt = datetime.datetime(2026, 7, 16, 14, 30)
        player = self._player(timezone='Not/AZone', date_format='%Y-%m-%d')
        self.assertEqual(format_player_datetime(dt, player), '2026-07-16')

    def test_invalid_date_format_falls_back_to_default(self):
        dt = datetime.datetime(2026, 7, 16, 14, 30)
        player = self._player(date_format='%Q')  # not a real strftime directive combo
        result = format_player_datetime(dt, player)
        self.assertIsInstance(result, str)  # must not raise


class TestClientSettingsPersistence(unittest.TestCase):
    """Regression: Player._load() never restored client_settings at all --
    every PREFS choice (border style, colors, tab settings, line ending,
    and now timezone/date format) silently reset on reconnect."""

    def test_to_dict_from_dict_round_trip(self):
        cs = ClientSettings()
        cs.border_style = 'double'
        cs.timezone = 'America/New_York'
        cs.date_format = '%Y-%m-%d'
        cs.colors.text_color = ColorName.CYAN
        cs.tab_settings.has_tab_key = False
        cs.tab_settings.tab_width = 4

        restored = ClientSettings.from_dict(cs.to_dict())
        self.assertEqual(restored.border_style, 'double')
        self.assertEqual(restored.timezone, 'America/New_York')
        self.assertEqual(restored.date_format, '%Y-%m-%d')
        self.assertEqual(restored.colors.text_color, ColorName.CYAN)
        self.assertFalse(restored.tab_settings.has_tab_key)
        self.assertEqual(restored.tab_settings.tab_width, 4)

    def test_player_save_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('player.Player._json_path',
                       staticmethod(lambda uid: str(Path(tmp) / f'player-{uid}.json'))):
                p = Player(name='Rulan', id='rulan')
                p.client_settings.timezone = 'Europe/London'
                p.client_settings.date_format = '%d %B %Y'
                p.client_settings.border_style = 'double'
                p.unsaved_changes = True
                self.assertTrue(p.save(force=True))

                reloaded = Player(name='Rulan', id='rulan')
                self.assertEqual(reloaded.client_settings.timezone, 'Europe/London')
                self.assertEqual(reloaded.client_settings.date_format, '%d %B %Y')
                self.assertEqual(reloaded.client_settings.border_style, 'double')

    def test_unknown_translation_name_falls_back_gracefully(self):
        restored = ClientSettings.from_dict({'translation': 'NOT_A_REAL_ONE'})
        self.assertIsInstance(restored, ClientSettings)  # must not raise

    def test_missing_client_settings_key_does_not_break_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('player.Player._json_path',
                       staticmethod(lambda uid: str(Path(tmp) / f'player-{uid}.json'))):
                p = Player(name='Rulan', id='rulan')
                p.unsaved_changes = True
                self.assertTrue(p.save(force=True))

                # Simulate an old save file predating client_settings persistence.
                import json
                path = Path(tmp) / 'player-rulan.json'
                data = json.loads(path.read_text())
                del data['client_settings']
                path.write_text(json.dumps(data))

                reloaded = Player(name='Rulan', id='rulan')
                self.assertIsInstance(reloaded.client_settings, ClientSettings)


if __name__ == '__main__':
    unittest.main(verbosity=2)
