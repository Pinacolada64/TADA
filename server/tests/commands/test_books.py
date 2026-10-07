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
from unittest.mock import MagicMock, patch

from books import PROSPECTING_ITEM_NUMBER, get_book_text, load_books


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
        """The actual server/books.json should load 24 entries -- one per
        book-type item in objects.json."""
        books = load_books('books.json')
        self.assertEqual(len(books), 24)
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


def _patched_config(**overrides):
    cfg = MagicMock()
    cfg.victory_type = overrides.get('victory_type', 'silver')
    cfg.victory_silver_amount = overrides.get('victory_silver_amount', 5000)
    cfg.victory_item_number = overrides.get('victory_item_number', 0)
    return cfg


class TestProspectingBookReflectsWinConfig(unittest.TestCase):
    """#61 "Prospecting..." is generated from config.py's victory_*
    settings rather than books.json's hardcoded SPUR default."""

    def _read(self, **overrides) -> str:
        ctx = MagicMock()
        ctx.server.books = {PROSPECTING_ITEM_NUMBER: ['stale SPUR text']}
        with patch('config.config', _patched_config(**overrides)):
            return ' '.join(get_book_text(ctx, PROSPECTING_ITEM_NUMBER))

    def test_silver_shows_configured_amount(self):
        text = self._read(victory_type='silver', victory_silver_amount=12345)
        self.assertIn('12,345 silver pieces', text)
        self.assertNotIn('gold', text.lower())
        self.assertNotIn('stale', text)

    def test_silver_ignores_item_number(self):
        text = self._read(victory_type='silver', victory_item_number=34)
        self.assertNotIn('Grail', text)

    def test_item_names_configured_item_without_silver(self):
        text = self._read(victory_type='item', victory_item_number=35)
        self.assertIn('the sand dollar', text)
        self.assertNotIn('silver', text)

    def test_item_keeps_existing_article(self):
        text = self._read(victory_type='item', victory_item_number=34)
        self.assertIn('the Holy Grail', text)
        self.assertNotIn('the the', text)

    def test_both_mentions_amount_and_item(self):
        text = self._read(victory_type='both', victory_silver_amount=750,
                          victory_item_number=35)
        self.assertIn('750 silver pieces', text)
        self.assertIn('the sand dollar', text)

    def test_both_with_no_item_set_is_silver_only(self):
        """victory.py skips the item gate when victory_item_number is 0."""
        text = self._read(victory_type='both', victory_item_number=0)
        self.assertIn('5,000 silver pieces', text)
        self.assertNotIn('in hand as well', text)

    def test_item_with_no_item_set_mentions_only_wraith_king(self):
        text = self._read(victory_type='item', victory_item_number=0)
        self.assertIn('King of the Wraiths', text)

    def test_works_even_if_books_json_failed_to_load(self):
        ctx = MagicMock()
        ctx.server = MagicMock(spec=[])
        with patch('config.config', _patched_config(victory_silver_amount=5000)):
            self.assertIn('5,000 silver', ' '.join(get_book_text(ctx, PROSPECTING_ITEM_NUMBER)))
