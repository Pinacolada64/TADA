"""tests/new-player/test_new_recruit_announcement.py

Unit tests for commands/new_player.py's _announce_new_recruit(), called
once a character finishes creation (SPUR-code/SPUR.NEW.S "new6"/"nw.plyr":
writes a "NEW RECRUIT" news item, seen once by every other player).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from base_classes import Guild, PlayerClass, PlayerRace
from commands.new_player import _announce_new_recruit


class _FakePlayer:
    def __init__(self, name='Rulan', char_race=None, char_class=None, guild=None):
        self.name = name
        self.char_race = char_race
        self.char_class = char_class
        self.guild = guild


class _FakeCtx:
    def __init__(self, player):
        self.player = player


class TestAnnounceNewRecruit(unittest.TestCase):

    def test_posts_a_once_news_item(self):
        player = _FakePlayer(char_race=PlayerRace.HUMAN, char_class=PlayerClass.FIGHTER,
                              guild=Guild.CIVILIAN)
        ctx = _FakeCtx(player)
        with patch('news.load_news', return_value=[]) as mock_load, \
             patch('news.next_id', return_value=1), \
             patch('news.save_news') as mock_save:
            _announce_new_recruit(ctx)

        mock_load.assert_called_once()
        mock_save.assert_called_once()
        (items,), _kwargs = mock_save.call_args
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['title'], 'New Recruit')
        self.assertEqual(item['lifetime'], 'once')
        self.assertEqual(item['seen_by'], [])
        self.assertIn('Rulan', item['body'][0])
        self.assertIn('Human', item['body'][0])
        self.assertIn('Fighter', item['body'][0])

    def test_civilian_guild_uses_a_or_an_phrasing(self):
        player = _FakePlayer(char_race=PlayerRace.OGRE, char_class=PlayerClass.KNIGHT,
                              guild=Guild.CIVILIAN)
        ctx = _FakeCtx(player)
        with patch('news.load_news', return_value=[]), \
             patch('news.next_id', return_value=1), \
             patch('news.save_news') as mock_save:
            _announce_new_recruit(ctx)

        body = mock_save.call_args[0][0][0]['body'][0]
        self.assertIn('as a Civilian', body)

    def test_real_guild_uses_the_phrasing(self):
        player = _FakePlayer(char_race=PlayerRace.ELF, char_class=PlayerClass.WIZARD,
                              guild=Guild.FIST)
        ctx = _FakeCtx(player)
        with patch('news.load_news', return_value=[]), \
             patch('news.next_id', return_value=1), \
             patch('news.save_news') as mock_save:
            _announce_new_recruit(ctx)

        body = mock_save.call_args[0][0][0]['body'][0]
        self.assertIn('the The Iron Fist', body)

    def test_failure_is_swallowed_not_raised(self):
        player = _FakePlayer(char_race=PlayerRace.HUMAN, char_class=PlayerClass.FIGHTER)
        ctx = _FakeCtx(player)
        with patch('news.load_news', side_effect=RuntimeError('boom')):
            _announce_new_recruit(ctx)  # must not raise


if __name__ == '__main__':
    unittest.main(verbosity=2)
