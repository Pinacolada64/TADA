"""tests/test_books.py

Unit tests for books.py -- server/books.json loading and lookup.

books.json recovers SPUR's book flavor text (SPUR-data/SPUR.BOOKS.TXT, a
GBBS Pro message base, via tools/gbbsmsgtool.py) keyed by objects.json
item number, same shape/pattern as server/messages.json + messages.py.

Run with:
    python -m pytest tests/test_books.py -v
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from books import get_book_text, load_books


class TestLoadBooks(unittest.TestCase):

    def test_loads_and_converts_keys_to_int(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'books.json'
            path.write_text(json.dumps({'30': ['line one'], '31': ['line two']}))
            books = load_books(str(path))
        self.assertEqual(books, {30: ['line one'], 31: ['line two']})

    def test_missing_file_returns_empty_dict(self):
        self.assertEqual(load_books('/nonexistent/path/books.json'), {})

    def test_real_books_json_loads_and_has_expected_count(self):
        """The actual server/books.json should load 23 entries -- one per
        book-type item in objects.json."""
        books = load_books('books.json')
        self.assertEqual(len(books), 23)
        self.assertIn(30, books)   # The Howling
        self.assertIn(89, books)  # Scroll of Endurance
        self.assertIn(92, books)  # the "other" Scroll of Endurance

    def test_every_book_type_item_in_objects_json_has_an_entry(self):
        objects = json.loads(Path('objects.json').read_text())
        book_numbers = {it['number'] for it in objects['items'] if it.get('type') == 'book'}
        books = load_books('books.json')
        self.assertEqual(set(books.keys()), book_numbers)


class TestGetBookText(unittest.TestCase):

    def _ctx(self, books: dict):
        ctx = MagicMock()
        ctx.server.books = books
        return ctx

    def test_returns_paragraphs_for_known_number(self):
        ctx = self._ctx({30: ['some text']})
        self.assertEqual(get_book_text(ctx, 30), ['some text'])

    def test_returns_none_for_unknown_number(self):
        ctx = self._ctx({30: ['some text']})
        self.assertIsNone(get_book_text(ctx, 999))

    def test_returns_none_when_server_has_no_books_attribute(self):
        ctx = MagicMock()
        ctx.server = MagicMock(spec=[])  # no .books at all
        self.assertIsNone(get_book_text(ctx, 30))


if __name__ == '__main__':
    unittest.main(verbosity=2)
