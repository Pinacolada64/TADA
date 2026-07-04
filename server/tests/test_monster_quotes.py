"""tests/test_monster_quotes.py

Unit tests for monster combat taunts/greetings, ported from SPUR.MISC4.S's
mon.ret/perm.qt (skip branch) using the real captured quote data in
monster_quotes.json (originally SPUR-data/MONSTER.QUOTE.TXT).

Coverage:
  - monsters.load_quotes() loads {number: text} from monster_quotes.json
  - combat.engine._pick_monster_quote():
      - fixed monster['quote_number'] always wins, regardless of race/flags
      - Ogre/Half-Elf player + evil monster -> friendly pool (61-71)
      - Pixie/Elf player + good monster -> friendly pool (61-71)
      - no race/alignment match -> taunt pool (1-52)
      - '$' placeholder substituted with the player's name
      - no quotes loaded on the server -> returns None (no crash)

Run with:
    python -m pytest tests/test_monster_quotes.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from combat.engine import _pick_monster_quote, _TAUNT_RANGE, _FRIENDLY_RANGE
from monsters import load_quotes


def make_ctx(*, race='Human', quotes=None):
    ctx = MagicMock()
    ctx.player.name = 'Rulan'
    ctx.player.char_race = race
    ctx.server.monster_quotes = quotes if quotes is not None else {
        1: '$, your butt is mine!',
        52: 'YOU CAN NOT HAVE PRECIOUSsssssss!!!',
        61: 'Welcome to OZ!!',
        71: "What do you call 500 lawyers in cement boots, $? A good start! Harr Harr.",
    }
    return ctx


class TestLoadQuotes(unittest.TestCase):
    def test_loads_real_data_file(self):
        quotes = load_quotes('monster_quotes.json')
        self.assertGreaterEqual(len(quotes), 52)
        self.assertIn(1, quotes)
        self.assertIn('$', quotes[1])

    def test_missing_file_returns_empty_dict(self):
        quotes = load_quotes('does-not-exist.json')
        self.assertEqual(quotes, {})


class TestPickMonsterQuote(unittest.TestCase):
    def test_fixed_quote_number_wins_regardless_of_flags(self):
        ctx = make_ctx(race='Human')
        monster = {'name': 'BOSS', 'flags': {'evil': True}, 'quote_number': 61}
        self.assertEqual(_pick_monster_quote(ctx, monster), 'Welcome to OZ!!')

    def test_player_name_substituted_for_dollar_sign(self):
        ctx = make_ctx(race='Human')
        monster = {'name': 'BOSS', 'flags': {}, 'quote_number': 1}
        self.assertEqual(_pick_monster_quote(ctx, monster), 'Rulan, your butt is mine!')

    def test_ogre_vs_evil_monster_uses_friendly_pool(self):
        ctx = make_ctx(race='Ogre')
        monster = {'name': 'GOBLIN', 'flags': {'evil': True}}
        for _ in range(20):
            result = _pick_monster_quote(ctx, monster)
            self.assertIn(result, ('Welcome to OZ!!',
                                   'What do you call 500 lawyers in cement boots, Rulan? A good start! Harr Harr.'))

    def test_pixie_vs_good_monster_uses_friendly_pool(self):
        ctx = make_ctx(race='Pixie')
        monster = {'name': 'ANGEL', 'flags': {'good': True}}
        for _ in range(20):
            result = _pick_monster_quote(ctx, monster)
            self.assertIn(result, ('Welcome to OZ!!',
                                   'What do you call 500 lawyers in cement boots, Rulan? A good start! Harr Harr.'))

    def test_human_vs_evil_monster_uses_taunt_pool(self):
        ctx = make_ctx(race='Human')
        monster = {'name': 'GOBLIN', 'flags': {'evil': True}}
        for _ in range(20):
            result = _pick_monster_quote(ctx, monster)
            self.assertIn(result, ('Rulan, your butt is mine!',
                                   'YOU CAN NOT HAVE PRECIOUSsssssss!!!'))

    def test_ogre_vs_good_monster_uses_taunt_pool(self):
        # Race/alignment must match -- Ogre only gets the friendly pool vs evil monsters.
        ctx = make_ctx(race='Ogre')
        monster = {'name': 'ANGEL', 'flags': {'good': True}}
        for _ in range(20):
            result = _pick_monster_quote(ctx, monster)
            self.assertIn(result, ('Rulan, your butt is mine!',
                                   'YOU CAN NOT HAVE PRECIOUSsssssss!!!'))

    def test_no_quotes_loaded_returns_none(self):
        ctx = make_ctx(quotes={})
        monster = {'name': 'GOBLIN', 'flags': {}}
        self.assertIsNone(_pick_monster_quote(ctx, monster))

    def test_ranges_are_disjoint(self):
        self.assertLess(_TAUNT_RANGE[1], _FRIENDLY_RANGE[0])


if __name__ == '__main__':
    unittest.main()
