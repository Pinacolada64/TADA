"""tests/test_nightly_recruit_digest.py — nightly "combined new recruits"
news digest job (tools/nightly_recruit_digest.py). Mirrors
test_nightly_guild_maintenance.py's _TempDirs pattern.
"""
from __future__ import annotations

import datetime
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import news as news_store
import tools.nightly_recruit_digest as m


class _TempDirs(unittest.TestCase):
    def setUp(self):
        self._orig_server_dir = m._SERVER_DIR
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / 'run' / 'server').mkdir(parents=True, exist_ok=True)
        m._SERVER_DIR = self.tmp

        self._news_path = self.tmp / 'run' / 'server' / 'news.json'
        self._news_patcher = patch.object(news_store, 'NEWS_FILE', self._news_path)
        self._news_patcher.start()

    def tearDown(self):
        self._news_patcher.stop()
        m._SERVER_DIR = self._orig_server_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_battle_log(self, text: str) -> None:
        (self.tmp / 'run' / 'server' / 'battle.log').write_text(text)


class TestParseRecruitLines(unittest.TestCase):
    def test_extracts_only_matching_date_and_tag(self):
        log_text = (
            '[2026-08-19 20:06 UTC] NEW RECRUIT: Gadget, a Human Fighter, has joined the Mark of the Sword.\n'
            '[2026-08-19 21:10 UTC] Ardent defeated Belwin in a duel, IN the field\n'
            '[2026-08-20 08:00 UTC] NEW RECRUIT: Tealguy, a Pixie Assassin, has joined the Mark of the Claw.\n'
        )
        result = m.parse_recruit_lines(log_text, datetime.date(2026, 8, 19))
        self.assertEqual(result, ['Gadget, a Human Fighter, has joined the Mark of the Sword.'])

    def test_no_matches_returns_empty_list(self):
        result = m.parse_recruit_lines('', datetime.date(2026, 8, 19))
        self.assertEqual(result, [])

    def test_preserves_file_order_for_multiple_recruits_same_day(self):
        log_text = (
            '[2026-08-19 09:00 UTC] NEW RECRUIT: Alice, a Human Fighter, has joined as a Civilian.\n'
            '[2026-08-19 15:00 UTC] NEW RECRUIT: Bob, an Elf Wizard, has joined as a Civilian.\n'
        )
        result = m.parse_recruit_lines(log_text, datetime.date(2026, 8, 19))
        self.assertEqual(result, [
            'Alice, a Human Fighter, has joined as a Civilian.',
            'Bob, an Elf Wizard, has joined as a Civilian.',
        ])


class TestBuildDigestItem(unittest.TestCase):
    def test_singular_title_for_one_recruit(self):
        item = m.build_digest_item(['Gadget, a Human Fighter, joined.'], [],
                                    datetime.datetime(2026, 8, 20, 0, 5))
        self.assertEqual(item['title'], 'New Recruit')
        self.assertEqual(item['lifetime'], 'once')
        self.assertEqual(item['seen_by'], [])
        self.assertIn('Gadget, a Human Fighter, joined.', item['body'])

    def test_plural_title_and_all_lines_included(self):
        lines = ['Alice joined.', 'Bob joined.', 'Cara joined.']
        item = m.build_digest_item(lines, [], datetime.datetime(2026, 8, 20, 0, 5))
        self.assertEqual(item['title'], '3 New Recruits')
        for line in lines:
            self.assertIn(line, item['body'])

    def test_id_derived_from_existing_items(self):
        existing = [{'id': 5}, {'id': 9}]
        item = m.build_digest_item(['X joined.'], existing, datetime.datetime(2026, 8, 20))
        self.assertEqual(item['id'], 10)


class TestRun(_TempDirs):
    def test_posts_combined_digest_for_target_date(self):
        self._write_battle_log(
            '[2026-08-19 09:00 UTC] NEW RECRUIT: Alice, a Human Fighter, has joined as a Civilian.\n'
            '[2026-08-19 15:00 UTC] NEW RECRUIT: Bob, an Elf Wizard, has joined as a Civilian.\n'
            '[2026-08-20 08:00 UTC] NEW RECRUIT: TooLate, a Gnome Thief, has joined as a Civilian.\n'
        )
        result = m.run(datetime.date(2026, 8, 19))
        self.assertTrue(result['posted'])

        items = news_store.load_news()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], '2 New Recruits')
        self.assertIn('Alice, a Human Fighter, has joined as a Civilian.', items[0]['body'])
        self.assertIn('Bob, an Elf Wizard, has joined as a Civilian.', items[0]['body'])
        self.assertNotIn('TooLate, a Gnome Thief, has joined as a Civilian.', items[0]['body'])

    def test_no_recruits_posts_nothing_but_records_date(self):
        self._write_battle_log('[2026-08-19 09:00 UTC] Ardent defeated Belwin in a duel\n')
        result = m.run(datetime.date(2026, 8, 19))
        self.assertFalse(result['posted'])
        self.assertEqual(news_store.load_news(), [])
        self.assertTrue(m._state_path().exists())

    def test_missing_battle_log_treated_as_empty(self):
        result = m.run(datetime.date(2026, 8, 19))
        self.assertFalse(result['posted'])
        self.assertEqual(news_store.load_news(), [])

    def test_rerunning_same_date_is_a_noop_without_force(self):
        self._write_battle_log(
            '[2026-08-19 09:00 UTC] NEW RECRUIT: Alice, a Human Fighter, has joined as a Civilian.\n'
        )
        first = m.run(datetime.date(2026, 8, 19))
        self.assertTrue(first['posted'])

        second = m.run(datetime.date(2026, 8, 19))
        self.assertFalse(second['posted'])
        self.assertTrue(second['skipped_already_done'])
        self.assertEqual(len(news_store.load_news()), 1)  # still just the one digest

    def test_force_reposts_even_if_already_done(self):
        self._write_battle_log(
            '[2026-08-19 09:00 UTC] NEW RECRUIT: Alice, a Human Fighter, has joined as a Civilian.\n'
        )
        m.run(datetime.date(2026, 8, 19))
        second = m.run(datetime.date(2026, 8, 19), force=True)
        self.assertTrue(second['posted'])
        self.assertEqual(len(news_store.load_news()), 2)

    def test_dry_run_does_not_write_news_or_state(self):
        self._write_battle_log(
            '[2026-08-19 09:00 UTC] NEW RECRUIT: Alice, a Human Fighter, has joined as a Civilian.\n'
        )
        result = m.run(datetime.date(2026, 8, 19), dry_run=True)
        self.assertFalse(result['posted'])
        self.assertEqual(result['recruit_lines'], ['Alice, a Human Fighter, has joined as a Civilian.'])
        self.assertEqual(news_store.load_news(), [])
        self.assertFalse(m._state_path().exists())

    def test_skips_when_disabled_via_config(self):
        # run() reads the real, already-imported config.config singleton,
        # so toggle its in-memory dict directly rather than going through
        # the @property setter -- that setter calls ServerConfig.set(),
        # which persists to the real server_config.json on disk.
        from config import config as server_config
        self._write_battle_log(
            '[2026-08-19 09:00 UTC] NEW RECRUIT: Alice, a Human Fighter, has joined as a Civilian.\n'
        )
        orig = server_config._config.get('nightly_recruit_digest_enabled', True)
        server_config._config['nightly_recruit_digest_enabled'] = False
        try:
            result = m.run(datetime.date(2026, 8, 19))
        finally:
            server_config._config['nightly_recruit_digest_enabled'] = orig

        self.assertFalse(result['posted'])
        self.assertTrue(result['skipped_disabled'])
        self.assertEqual(news_store.load_news(), [])
        self.assertFalse(m._state_path().exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
