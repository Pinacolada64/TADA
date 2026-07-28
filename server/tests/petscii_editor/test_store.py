"""tests/petscii_editor/test_store.py

Covers petscii_editor/store.py: on-disk [tokenized]/[raw_petscii]
header-tag disambiguation (Ryan's call -- a loader shouldn't have to
infer format from a filename/extension convention), and load()'s
backward compatibility with legacy banner files that have no tag at all.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from petscii_editor import store
from petscii_editor.canvas import Canvas


class TestLoadSave(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self._tmpdir.name) / 'test.canvas'

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_file_returns_empty_list(self):
        self.assertEqual(store.load(self.path), [])

    def test_raw_petscii_round_trip(self):
        cv = Canvas()
        cv.chars[42] = 0x99
        cv.colors[42] = 3
        store.save(self.path, cv)

        loaded = store.load(self.path)
        self.assertIsInstance(loaded, Canvas)
        self.assertEqual(loaded.chars, cv.chars)
        self.assertEqual(loaded.colors, cv.colors)

    def test_file_starts_with_raw_petscii_tag(self):
        store.save(self.path, Canvas())
        with open(self.path, 'rb') as f:
            first_line = f.readline().rstrip(b'\r\n')
        self.assertEqual(first_line, store.TAG_RAW.encode('ascii'))

    def test_tokenized_round_trip(self):
        lines = ['|red|Hello|reset|', 'World']
        store.save_tokenized(self.path, lines)
        loaded = store.load(self.path)
        self.assertEqual(loaded, lines)

    def test_legacy_untagged_file_treated_as_tokenized(self):
        self.path.write_text('|red|Hello|reset|\nWorld', encoding='utf-8')
        loaded = store.load(self.path)
        self.assertEqual(loaded, ['|red|Hello|reset|', 'World'])


class TestPathFor(unittest.TestCase):
    def test_sanitizes_name(self):
        p = store.path_for('../../etc/passwd')
        self.assertEqual(p.parent, store.CANVASES_DIR)
        self.assertNotIn('..', p.name)

    def test_same_name_same_path(self):
        self.assertEqual(store.path_for('sword-banner'), store.path_for('sword-banner'))


if __name__ == '__main__':
    unittest.main()
