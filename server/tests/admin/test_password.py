"""tests/test_password.py

Unit tests for:
  - net_common.hash_password()/verify_password() -- bcrypt hashing plus
    backward-compatible legacy-plaintext verification with an upgrade hash.
  - commands/password.py's PasswordCommand -- change your login password.

Run with:
    python -m pytest tests/test_password.py -v
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from net_common import hash_password, verify_password
from commands.password import PasswordCommand


class TestHashPassword(unittest.TestCase):

    def test_hash_is_not_plaintext(self):
        self.assertNotEqual(hash_password('fescue'), 'fescue')

    def test_hash_has_bcrypt_prefix(self):
        self.assertTrue(hash_password('fescue').startswith('$2b$'))

    def test_same_password_hashes_differently_each_time(self):
        # bcrypt salts randomly -- two hashes of the same password must differ.
        self.assertNotEqual(hash_password('fescue'), hash_password('fescue'))


class TestVerifyPassword(unittest.TestCase):

    def test_correct_password_against_hash_matches(self):
        stored = hash_password('fescue')
        matched, rehashed = verify_password('fescue', stored)
        self.assertTrue(matched)
        self.assertIsNone(rehashed)

    def test_wrong_password_against_hash_fails(self):
        stored = hash_password('fescue')
        matched, rehashed = verify_password('wrong', stored)
        self.assertFalse(matched)
        self.assertIsNone(rehashed)

    def test_case_insensitive_against_hash(self):
        # C64 keyboards send uppercase by default.
        stored = hash_password('fescue')
        matched, _ = verify_password('FESCUE', stored)
        self.assertTrue(matched)

    def test_legacy_plaintext_match_returns_upgrade_hash(self):
        matched, rehashed = verify_password('fescue', 'fescue')
        self.assertTrue(matched)
        self.assertIsNotNone(rehashed)
        self.assertTrue(rehashed.startswith('$2b$'))
        # The upgrade hash must itself verify against the same password.
        matched2, rehashed2 = verify_password('fescue', rehashed)
        self.assertTrue(matched2)
        self.assertIsNone(rehashed2)

    def test_legacy_plaintext_case_insensitive(self):
        matched, rehashed = verify_password('FESCUE', 'fescue')
        self.assertTrue(matched)
        self.assertIsNotNone(rehashed)

    def test_legacy_plaintext_mismatch_no_upgrade(self):
        matched, rehashed = verify_password('wrong', 'fescue')
        self.assertFalse(matched)
        self.assertIsNone(rehashed)


class _FakePlayer:
    def __init__(self, player_id):
        self.id = player_id


class _FakeCtx:
    def __init__(self, responses, player_id='rulan'):
        self._q = list(responses)
        self.sent: list = []
        self.player = _FakePlayer(player_id)

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestPasswordCommand(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._udir = Path(self._tmpdir.name) / 'net'
        self._udir.mkdir(parents=True, exist_ok=True)
        self._patcher = patch('commands.password.user_dir', return_value=self._udir)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmpdir.cleanup()

    def _write_creds(self, username, password_field):
        (self._udir / f'login-{username}.json').write_text(
            json.dumps({'password': password_field})
        )

    def _read_creds(self, username):
        return json.loads((self._udir / f'login-{username}.json').read_text())

    async def test_no_account_fails(self):
        ctx = _FakeCtx([], player_id=None)
        result = await PasswordCommand().execute(ctx)
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'no_account')

    async def test_wrong_current_password_fails(self):
        self._write_creds('rulan', hash_password('oldpw'))
        ctx = _FakeCtx(['nope'])
        result = await PasswordCommand().execute(ctx)
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'wrong_password')

    async def test_change_password_succeeds_and_persists_hash(self):
        self._write_creds('rulan', hash_password('oldpw'))
        ctx = _FakeCtx(['oldpw', 'newpw123', 'newpw123'])
        result = await PasswordCommand().execute(ctx)
        self.assertTrue(result.success)

        creds = self._read_creds('rulan')
        self.assertTrue(creds['password'].startswith('$2b$'))
        matched, _ = verify_password('newpw123', creds['password'])
        self.assertTrue(matched)
        # old password no longer works
        matched_old, _ = verify_password('oldpw', creds['password'])
        self.assertFalse(matched_old)

    async def test_mismatched_confirmation_reprompts(self):
        self._write_creds('rulan', hash_password('oldpw'))
        ctx = _FakeCtx(['oldpw', 'newpw123', 'typo', 'newpw123', 'newpw123'])
        result = await PasswordCommand().execute(ctx)
        self.assertTrue(result.success)
        creds = self._read_creds('rulan')
        matched, _ = verify_password('newpw123', creds['password'])
        self.assertTrue(matched)

    async def test_too_short_new_password_reprompts(self):
        self._write_creds('rulan', hash_password('oldpw'))
        ctx = _FakeCtx(['oldpw', 'ab', 'longenough', 'longenough'])
        result = await PasswordCommand().execute(ctx)
        self.assertTrue(result.success)
        creds = self._read_creds('rulan')
        matched, _ = verify_password('longenough', creds['password'])
        self.assertTrue(matched)

    async def test_works_against_legacy_plaintext_current_password(self):
        # Account never logged in yet since the bcrypt migration -- current
        # password is still stored as plaintext.
        self._write_creds('rulan', 'oldpw')
        ctx = _FakeCtx(['oldpw', 'newpw123', 'newpw123'])
        result = await PasswordCommand().execute(ctx)
        self.assertTrue(result.success)
        creds = self._read_creds('rulan')
        self.assertTrue(creds['password'].startswith('$2b$'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
