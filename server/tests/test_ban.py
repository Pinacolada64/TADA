"""tests/test_ban.py — Unit tests for ban/unban command and is_banned()."""
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from commands.ban import (
    BanCommand,
    is_banned,
    load_bans,
    save_bans,
    _parse_ban_args,
)
from flags import PlayerFlags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ctx(*, is_admin=True):
    player = MagicMock()
    player.name = 'Admin'
    player.query_flag = MagicMock(
        side_effect=lambda f: f == PlayerFlags.ADMIN and is_admin
    )
    ctx = MagicMock()
    ctx.player    = player
    ctx.send      = AsyncMock()
    ctx._invoked_as = 'ban'
    return ctx


def _today():
    return date.today()

def _days(n):
    return (_today() + timedelta(days=n)).isoformat()


# ---------------------------------------------------------------------------
# is_banned() — pure logic, no I/O (bans dict injected via patch)
# ---------------------------------------------------------------------------

class TestIsBanned(unittest.TestCase):

    def _check(self, entry, *, want_banned, fragment=None):
        bans = {'alice': entry}
        with patch('commands.ban.load_bans', return_value=bans):
            banned, msg = is_banned('alice')
        self.assertEqual(banned, want_banned, msg)
        if fragment:
            self.assertIn(fragment, msg)
        return msg

    def test_permanent_ban(self):
        self._check({'reason': 'griefing', 'banned_by': 'Admin', 'banned_at': '2026-01-01'},
                    want_banned=True, fragment='permanently')

    def test_permanent_ban_reason_in_message(self):
        msg = self._check({'reason': 'griefing', 'banned_by': 'Admin', 'banned_at': '2026-01-01'},
                          want_banned=True)
        self.assertIn('griefing', msg)

    def test_not_in_list(self):
        with patch('commands.ban.load_bans', return_value={}):
            banned, msg = is_banned('alice')
        self.assertFalse(banned)
        self.assertEqual(msg, '')

    def test_case_insensitive_lookup(self):
        bans = {'alice': {'reason': 'test', 'banned_by': 'Admin', 'banned_at': '2026-01-01'}}
        with patch('commands.ban.load_bans', return_value=bans):
            banned, _ = is_banned('ALICE')
        self.assertTrue(banned)

    # Dated bans — active window
    def test_dated_ban_active(self):
        entry = {'reason': 'spam', 'banned_by': 'Admin', 'banned_at': '2026-01-01',
                 'ban_end': _days(5)}
        self._check(entry, want_banned=True, fragment='suspended until')

    def test_dated_ban_until_message_contains_date(self):
        end = _days(5)
        entry = {'reason': 'spam', 'banned_by': 'Admin', 'banned_at': '2026-01-01',
                 'ban_end': end}
        msg = self._check(entry, want_banned=True)
        parsed_end = date.fromisoformat(end)
        self.assertIn(str(parsed_end.year), msg)

    # Dated bans — expired
    def test_dated_ban_expired(self):
        entry = {'reason': 'spam', 'banned_by': 'Admin', 'banned_at': '2026-01-01',
                 'ban_end': _days(-1)}
        self._check(entry, want_banned=False)

    def test_dated_ban_expires_today_is_still_active(self):
        entry = {'reason': 'spam', 'banned_by': 'Admin', 'banned_at': '2026-01-01',
                 'ban_end': _today().isoformat()}
        self._check(entry, want_banned=True)

    # Dated bans — not yet started
    def test_dated_ban_not_yet_started(self):
        entry = {'reason': 'spam', 'banned_by': 'Admin', 'banned_at': '2026-01-01',
                 'ban_start': _days(5)}
        self._check(entry, want_banned=False)

    # Window ban (start + end)
    def test_window_ban_inside(self):
        entry = {'reason': 'test', 'banned_by': 'Admin', 'banned_at': '2026-01-01',
                 'ban_start': _days(-2), 'ban_end': _days(2)}
        self._check(entry, want_banned=True)

    def test_window_ban_before_window(self):
        entry = {'reason': 'test', 'banned_by': 'Admin', 'banned_at': '2026-01-01',
                 'ban_start': _days(1), 'ban_end': _days(5)}
        self._check(entry, want_banned=False)

    def test_window_ban_after_window(self):
        entry = {'reason': 'test', 'banned_by': 'Admin', 'banned_at': '2026-01-01',
                 'ban_start': _days(-5), 'ban_end': _days(-1)}
        self._check(entry, want_banned=False)


# ---------------------------------------------------------------------------
# _parse_ban_args() — argument parsing
# ---------------------------------------------------------------------------

class TestParseBanArgs(unittest.TestCase):

    def test_no_args_gives_permanent(self):
        start, end, reason = _parse_ban_args([])
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertEqual(reason, '(no reason given)')

    def test_plain_reason_is_permanent(self):
        start, end, reason = _parse_ban_args(['being', 'rude'])
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertEqual(reason, 'being rude')

    def test_until_sets_end_date(self):
        _, end, _ = _parse_ban_args(['until', '2026-12-31'])
        self.assertIsNotNone(end)
        self.assertEqual(end, date(2026, 12, 31))

    def test_until_no_start_date(self):
        start, _, _ = _parse_ban_args(['until', '2026-12-31'])
        self.assertIsNone(start)

    def test_until_bad_date_falls_back_to_permanent(self):
        start, end, reason = _parse_ban_args(['until', 'notadate'])
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertIn('until', reason)

    def test_from_to_sets_both_dates(self):
        start, end, _ = _parse_ban_args(['from', 'Jul', '1', 'to', 'Jul', '31', '2026'])
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertLessEqual(start, end)

    def test_no_reason_gives_default(self):
        _, end, reason = _parse_ban_args(['until', '2026-12-31'])
        self.assertEqual(reason, '(no reason given)')


# ---------------------------------------------------------------------------
# BanCommand — permission gate
# ---------------------------------------------------------------------------

class TestBanPermission(unittest.IsolatedAsyncioTestCase):

    async def test_non_admin_denied(self):
        cmd = BanCommand()
        ctx = make_ctx(is_admin=False)
        with patch('commands.ban.load_bans', return_value={}), \
             patch('commands.ban.save_bans'):
            res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'permission_denied')

    async def test_non_admin_no_save(self):
        cmd = BanCommand()
        ctx = make_ctx(is_admin=False)
        with patch('commands.ban.save_bans') as mock_save:
            await cmd.execute(ctx, 'alice')
        mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# BanCommand — ban action
# ---------------------------------------------------------------------------

class TestBanAction(unittest.IsolatedAsyncioTestCase):

    async def _ban(self, *args, bans=None):
        cmd = BanCommand()
        ctx = make_ctx()
        stored = {}
        with patch('commands.ban.load_bans', return_value=bans or {}), \
             patch('commands.ban.save_bans', side_effect=lambda b: stored.update(b)):
            res = await cmd.execute(ctx, *args)
        return res, stored, ctx

    async def test_ban_creates_entry(self):
        _, stored, _ = await self._ban('alice')
        self.assertIn('alice', stored)

    async def test_ban_stores_reason(self):
        _, stored, _ = await self._ban('alice', 'being', 'rude')
        self.assertEqual(stored['alice']['reason'], 'being rude')

    async def test_ban_records_admin_name(self):
        _, stored, _ = await self._ban('alice')
        self.assertEqual(stored['alice']['banned_by'], 'Admin')

    async def test_ban_permanent_no_dates(self):
        _, stored, _ = await self._ban('alice')
        self.assertNotIn('ban_end', stored['alice'])
        self.assertNotIn('ban_start', stored['alice'])

    async def test_ban_until_stores_end(self):
        _, stored, _ = await self._ban('alice', 'until', '2026-12-31')
        self.assertIn('ban_end', stored['alice'])
        self.assertEqual(stored['alice']['ban_end'], '2026-12-31')

    async def test_ban_no_args_fails(self):
        res, _, _ = await self._ban()
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'missing_args')

    async def test_ban_confirms_to_admin(self):
        _, _, ctx = await self._ban('alice', 'griefing')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('alice', sent.lower())

    async def test_ban_view_returns_ok(self):
        cmd = BanCommand()
        ctx = make_ctx()
        ctx._invoked_as = 'ban'
        with patch('commands.ban.load_bans', return_value={}):
            res = await cmd.execute(ctx, '#view')
        self.assertTrue(res.success)

    async def test_ban_view_empty_list(self):
        cmd = BanCommand()
        ctx = make_ctx()
        with patch('commands.ban.load_bans', return_value={}):
            await cmd.execute(ctx, '#view')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('No players', sent)

    async def test_ban_view_shows_username(self):
        bans = {'alice': {'reason': 'test', 'banned_by': 'Admin',
                          'banned_at': '2026-01-01T00:00:00+00:00'}}
        cmd = BanCommand()
        ctx = make_ctx()
        with patch('commands.ban.load_bans', return_value=bans):
            await cmd.execute(ctx, '#view')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('alice', sent)


# ---------------------------------------------------------------------------
# BanCommand — unban action
# ---------------------------------------------------------------------------

class TestUnbanAction(unittest.IsolatedAsyncioTestCase):

    async def _unban(self, *args, bans=None):
        cmd = BanCommand()
        ctx = make_ctx()
        ctx._invoked_as = 'unban'
        stored = dict(bans or {})
        with patch('commands.ban.load_bans', return_value=dict(stored)), \
             patch('commands.ban.save_bans', side_effect=lambda b: stored.clear() or stored.update(b)):
            res = await cmd.execute(ctx, *args)
        return res, stored, ctx

    async def test_unban_removes_entry(self):
        bans = {'alice': {'reason': 'test', 'banned_by': 'Admin', 'banned_at': '2026-01-01'}}
        _, stored, _ = await self._unban('alice', bans=bans)
        self.assertNotIn('alice', stored)

    async def test_unban_missing_user_ok(self):
        res, _, ctx = await self._unban('alice')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('not banned', sent)

    async def test_unban_no_args_fails(self):
        res, _, _ = await self._unban()
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'missing_args')

    async def test_unban_confirms_to_admin(self):
        bans = {'alice': {'reason': 'test', 'banned_by': 'Admin', 'banned_at': '2026-01-01'}}
        _, _, ctx = await self._unban('alice', bans=bans)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('alice', sent)

    async def test_unban_does_not_affect_others(self):
        bans = {
            'alice': {'reason': 'test', 'banned_by': 'Admin', 'banned_at': '2026-01-01'},
            'bob':   {'reason': 'test', 'banned_by': 'Admin', 'banned_at': '2026-01-01'},
        }
        _, stored, _ = await self._unban('alice', bans=bans)
        self.assertIn('bob', stored)


if __name__ == '__main__':
    unittest.main()
