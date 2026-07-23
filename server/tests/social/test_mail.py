"""tests/social/test_mail.py

Unit tests for mail.py -- private mailbox storage/schema shared by
commands/page.py's offline fallback and commands/mail.py's MAIL command.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mail


class _TempMailDir(unittest.TestCase):
    """Patches mail.MAIL_DIR to a fresh temp directory for each test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patcher = patch('mail.MAIL_DIR', Path(self._tmp.name))
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()


class TestLoadSave(_TempMailDir):

    def test_missing_mailbox_returns_empty_list(self):
        self.assertEqual(mail.load_mailbox('nobody'), [])

    def test_round_trip(self):
        inbox = [{'from': 'Alice', 'timestamp': 't', 'body': 'hi', 'read': False}]
        mail.save_mailbox('Bob', inbox)
        self.assertEqual(mail.load_mailbox('bob'), inbox)  # lowercased on disk

    def test_case_insensitive_filename(self):
        mail.save_mailbox('Bob', [{'from': 'Alice', 'timestamp': 't', 'body': 'hi', 'read': False}])
        self.assertEqual(len(mail.load_mailbox('BOB')), 1)


class TestAddMessage(_TempMailDir):

    def test_appends_a_well_formed_record(self):
        mail.add_message('Bob', 'Alice', 'hello there')
        inbox = mail.load_mailbox('Bob')
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]['from'], 'Alice')
        self.assertEqual(inbox[0]['body'], 'hello there')
        self.assertFalse(inbox[0]['read'])
        self.assertIn('timestamp', inbox[0])

    def test_appends_to_existing_mailbox(self):
        mail.add_message('Bob', 'Alice', 'first')
        mail.add_message('Bob', 'Carol', 'second')
        inbox = mail.load_mailbox('Bob')
        self.assertEqual([m['body'] for m in inbox], ['first', 'second'])


class TestUnreadCount(_TempMailDir):

    def test_zero_for_empty_mailbox(self):
        self.assertEqual(mail.unread_count('nobody'), 0)

    def test_counts_only_unread(self):
        mail.add_message('Bob', 'Alice', 'one')
        mail.add_message('Bob', 'Alice', 'two')
        mail.mark_read('Bob', 0)
        self.assertEqual(mail.unread_count('Bob'), 1)


class TestMarkRead(_TempMailDir):

    def test_marks_and_returns_the_message(self):
        mail.add_message('Bob', 'Alice', 'hi')
        msg = mail.mark_read('Bob', 0)
        self.assertTrue(msg['read'])
        self.assertTrue(mail.load_mailbox('Bob')[0]['read'])

    def test_out_of_range_returns_none(self):
        self.assertIsNone(mail.mark_read('Bob', 5))


class TestDeleteMessage(_TempMailDir):

    def test_deletes_and_returns_true(self):
        mail.add_message('Bob', 'Alice', 'one')
        mail.add_message('Bob', 'Alice', 'two')
        self.assertTrue(mail.delete_message('Bob', 0))
        inbox = mail.load_mailbox('Bob')
        self.assertEqual(len(inbox), 1)
        self.assertEqual(inbox[0]['body'], 'two')

    def test_out_of_range_returns_false(self):
        self.assertFalse(mail.delete_message('Bob', 0))


class TestMarkArchived(_TempMailDir):

    def test_marks_and_returns_the_message(self):
        mail.add_message('Bob', 'Alice', 'hi')
        msg = mail.mark_archived('Bob', 0)
        self.assertTrue(msg['archived'])
        self.assertTrue(mail.load_mailbox('Bob')[0]['archived'])

    def test_out_of_range_returns_none(self):
        self.assertIsNone(mail.mark_archived('Bob', 5))

    def test_archived_excluded_from_unread_count(self):
        mail.add_message('Bob', 'Alice', 'one')
        mail.add_message('Bob', 'Alice', 'two')
        mail.mark_archived('Bob', 0)
        self.assertEqual(mail.unread_count('Bob'), 1)


if __name__ == '__main__':
    unittest.main()
