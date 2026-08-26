"""tests/social/test_board_migration.py

Unit tests for board/migration.py -- the one-time, explicitly-invoked
migration from the old single-board storage (board.json/
board_config.json) into the SIG/board-aware storage (board_sigs.json/
board_meta.json/board_threads.json).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from board.migration import migrate_if_needed


class BoardMigrationTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.legacy_board_path = tmp / 'board.json'
        self.legacy_config_path = tmp / 'board_config.json'
        self.sigs_path = tmp / 'board_sigs.json'
        self.meta_path = tmp / 'board_meta.json'
        self.threads_path = tmp / 'board_threads.json'

    def _migrate(self) -> bool:
        return migrate_if_needed(
            legacy_board_path=self.legacy_board_path,
            legacy_config_path=self.legacy_config_path,
            sigs_path=self.sigs_path,
            meta_path=self.meta_path,
            threads_path=self.threads_path,
        )


class TestFreshInstall(BoardMigrationTestCase):
    def test_no_legacy_files_is_a_no_op(self):
        self.assertFalse(self._migrate())
        self.assertFalse(self.sigs_path.exists())
        self.assertFalse(self.meta_path.exists())
        self.assertFalse(self.threads_path.exists())


class TestMigratesLegacyData(BoardMigrationTestCase):
    def setUp(self):
        super().setUp()
        self.legacy_threads = [
            {'id': 1, 'title': 'Hello', 'author': 'bob', 'anonymous': False,
             'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'root text'}],
             'replies': [{'author': 'carol', 'anonymous': True,
                          'posted_at': '2026-01-02T00:00:00',
                          'body': [{'text': 'reply text'}]}]},
            {'id': 5, 'title': 'Second Thread', 'author': 'dave', 'anonymous': True,
             'posted_at': '2026-02-01T00:00:00', 'body': [{'text': 'x'}], 'replies': []},
        ]
        self.legacy_board_path.write_text(json.dumps(self.legacy_threads))
        self.legacy_config_path.write_text(json.dumps({'anonymous_mode': 'yes'}))

    def test_returns_true_and_writes_all_three_new_files(self):
        self.assertTrue(self._migrate())
        self.assertTrue(self.sigs_path.exists())
        self.assertTrue(self.meta_path.exists())
        self.assertTrue(self.threads_path.exists())

    def test_thread_data_preserved_byte_identical_aside_from_board_id(self):
        self._migrate()
        migrated = json.loads(self.threads_path.read_text())
        self.assertEqual(len(migrated), 2)
        for original, new in zip(self.legacy_threads, migrated):
            expected = dict(original)
            expected['board_id'] = 1
            self.assertEqual(new, expected)

    def test_anonymous_mode_carried_over_onto_default_board(self):
        self._migrate()
        meta = json.loads(self.meta_path.read_text())
        self.assertEqual(meta['boards']['1']['anonymous_mode'], 'yes')

    def test_default_board_and_sig_created(self):
        self._migrate()
        meta = json.loads(self.meta_path.read_text())
        self.assertEqual(meta['boards']['1']['id'], 1)
        self.assertIn('name', meta['boards']['1'])
        self.assertEqual(meta['boards']['1']['access'], {'type': 'any'})
        self.assertEqual(meta['boards']['1']['admins'], [])

        sigs = json.loads(self.sigs_path.read_text())
        self.assertEqual(len(sigs['sigs']), 1)
        self.assertEqual(sigs['sigs'][0]['board_ids'], [1])

    def test_legacy_files_left_untouched(self):
        self._migrate()
        self.assertEqual(json.loads(self.legacy_board_path.read_text()), self.legacy_threads)
        self.assertEqual(json.loads(self.legacy_config_path.read_text()), {'anonymous_mode': 'yes'})

    def test_idempotent_second_call_is_a_no_op(self):
        self.assertTrue(self._migrate())
        # Mutate the migrated threads file, then run migration again --
        # it must not overwrite what's there now, since the new files
        # already exist.
        self.threads_path.write_text(json.dumps([{'id': 99, 'board_id': 1}]))
        self.assertFalse(self._migrate())
        self.assertEqual(json.loads(self.threads_path.read_text()), [{'id': 99, 'board_id': 1}])


class TestMigratesBoardJsonOnlyNoConfig(BoardMigrationTestCase):
    def test_missing_legacy_config_still_migrates_with_default_anonymous_mode(self):
        self.legacy_board_path.write_text(json.dumps([
            {'id': 1, 'title': 'X', 'author': 'a', 'anonymous': False,
             'posted_at': '2026-01-01T00:00:00', 'body': [], 'replies': []},
        ]))
        self.assertTrue(self._migrate())
        meta = json.loads(self.meta_path.read_text())
        self.assertEqual(meta['boards']['1']['anonymous_mode'], 'ask')


class TestMigratesConfigOnlyNoThreads(BoardMigrationTestCase):
    def test_missing_legacy_board_file_still_migrates_config(self):
        self.legacy_config_path.write_text(json.dumps({'anonymous_mode': 'no'}))
        self.assertTrue(self._migrate())
        self.assertEqual(json.loads(self.threads_path.read_text()), [])
        meta = json.loads(self.meta_path.read_text())
        self.assertEqual(meta['boards']['1']['anonymous_mode'], 'no')


if __name__ == '__main__':
    unittest.main()
