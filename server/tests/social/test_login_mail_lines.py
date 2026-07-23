"""tests/social/test_login_mail_lines.py

Unit tests for commands/connect.py's _login_mail_lines() -- the
"you have N unread mail message(s)" notice shown at login, right after
news (see MECHANICS.md's "Mail / Paging" section).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mail as mail_store
from commands.connect import _login_mail_lines


class _FakePlayer:
    def __init__(self, name='bob'):
        self.name = name


class TestLoginMailLines(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(mail_store, 'MAIL_DIR', Path(self._tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_no_mail_returns_no_lines(self):
        self.assertEqual(_login_mail_lines(_FakePlayer()), [])

    def test_unread_mail_mentions_count(self):
        mail_store.add_message('bob', 'Alice', 'hi')
        mail_store.add_message('bob', 'Carol', 'hey')
        lines = _login_mail_lines(_FakePlayer())
        self.assertTrue(any('2 unread mail messages' in ln for ln in lines))

    def test_singular_for_one_message(self):
        mail_store.add_message('bob', 'Alice', 'hi')
        lines = _login_mail_lines(_FakePlayer())
        joined = ' '.join(lines)
        self.assertIn('1 unread mail message.', joined)
        self.assertNotIn('messages.', joined)

    def test_read_mail_does_not_count(self):
        mail_store.add_message('bob', 'Alice', 'hi')
        mail_store.mark_read('bob', 0)
        self.assertEqual(_login_mail_lines(_FakePlayer()), [])

    def test_does_not_mark_anything_read(self):
        mail_store.add_message('bob', 'Alice', 'hi')
        _login_mail_lines(_FakePlayer())
        self.assertFalse(mail_store.load_mailbox('bob')[0]['read'])


if __name__ == '__main__':
    unittest.main()
