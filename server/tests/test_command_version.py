"""tests/test_command_version.py

Unit tests for command_version.py -- resolves a command's own source
file's last-committed date (or file mtime fallback), used by the
universal '#version'/'#ver' switch (see
commands/command_processor.py's process_command()).

Run with:
    python -m pytest tests/test_command_version.py -v
"""
from __future__ import annotations

import subprocess
import unittest
from unittest.mock import MagicMock, patch

import command_version
from command_version import get_command_version


class _DummyCommand:
    """Stands in for a real Command instance/class -- get_command_version()
    only needs inspect.getfile() to resolve on it."""


class TestGetCommandVersion(unittest.TestCase):

    def setUp(self):
        command_version._cache.clear()

    def test_returns_git_log_date_when_available(self):
        fake_result = MagicMock(returncode=0, stdout='2026-07-09\n')
        with patch('command_version.subprocess.run', return_value=fake_result):
            result = get_command_version(_DummyCommand)
        self.assertEqual(result, '2026-07-09')

    def test_falls_back_to_mtime_when_git_unavailable(self):
        fake_result = MagicMock(returncode=1, stdout='')
        with patch('command_version.subprocess.run', return_value=fake_result), \
             patch('command_version._mtime_date', return_value='2026-01-01'):
            result = get_command_version(_DummyCommand)
        self.assertIn('2026-01-01', result)
        self.assertIn('mtime', result.lower())

    def test_falls_back_to_mtime_when_git_raises(self):
        with patch('command_version.subprocess.run', side_effect=OSError('no git')), \
             patch('command_version._mtime_date', return_value='2026-01-01'):
            result = get_command_version(_DummyCommand)
        self.assertIn('2026-01-01', result)

    def test_result_is_cached(self):
        fake_result = MagicMock(returncode=0, stdout='2026-07-09\n')
        with patch('command_version.subprocess.run', return_value=fake_result) as mock_run:
            get_command_version(_DummyCommand)
            get_command_version(_DummyCommand)
        mock_run.assert_called_once()

    def test_accepts_instance_not_just_class(self):
        fake_result = MagicMock(returncode=0, stdout='2026-07-09\n')
        with patch('command_version.subprocess.run', return_value=fake_result):
            result = get_command_version(_DummyCommand())
        self.assertEqual(result, '2026-07-09')

    def test_unresolvable_file_returns_unknown(self):
        class NotARealClassWithNoFile:
            pass
        # A plain built-in type has no source file inspect.getfile() can find.
        result = get_command_version(int)
        self.assertEqual(result, 'unknown')


if __name__ == '__main__':
    unittest.main()
