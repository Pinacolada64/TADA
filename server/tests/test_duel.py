"""tests/test_duel.py — rough-draft SPORT DUEL resolution tests.

Covers combat/duel.py's resolve_sport_duel() (pure, no ctx/I/O) and
guild_standings.py's tally persistence. DuelCommand's (combat/duel.py)
challenge/accept UX is exercised indirectly via _offense_rating and
outcome shape here; full command-level bot testing is done live (see
session notes), not duplicated as unit tests for this rough draft.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from base_classes import PlayerClass, PlayerRace
from combat.duel import _offense_rating, resolve_sport_duel
from items import Weapon
from player import Player


def _make_duelist(name, *, char_class=PlayerClass.FIGHTER, char_race=PlayerRace.HUMAN,
                   hit_points=30, weapon_number=1):
    p = Player(name=name, id=name.lower())
    p.char_class = char_class
    p.char_race = char_race
    p.hit_points = hit_points
    p.shield = 0
    p.armor = 0
    p.readied_weapon = Weapon(
        id_number=weapon_number, name='LONG SWORD', stability=50,
        to_hit=60, weapon_class='bash/slash',
    )
    return p


class TestOffenseRating(unittest.TestCase):
    def test_no_weapon_still_returns_a_rating(self):
        p = _make_duelist('Rulan')
        self.assertGreaterEqual(_offense_rating(p, None), 3)

    def test_rating_is_clamped_3_to_9(self):
        p = _make_duelist('Rulan')
        weapon = p.readied_weapon
        rating = _offense_rating(p, weapon)
        self.assertGreaterEqual(rating, 3)
        self.assertLessEqual(rating, 9)


class TestResolveSportDuel(unittest.TestCase):
    def test_someone_wins_or_it_is_a_draw(self):
        a = _make_duelist('Attacker')
        b = _make_duelist('Defender')
        outcome = resolve_sport_duel(a, b)
        if outcome.fled:
            self.assertEqual(outcome.winner_name, '')
        else:
            self.assertIn(outcome.winner_name, (a.name, b.name))
            self.assertIn(outcome.loser_name, (a.name, b.name))
            self.assertNotEqual(outcome.winner_name, outcome.loser_name)

    def test_loser_left_at_min_hp_not_dead(self):
        # Heavily stack the deck so Attacker reliably wins quickly.
        a = _make_duelist('Attacker', hit_points=100)
        b = _make_duelist('Defender', hit_points=5)
        outcome = resolve_sport_duel(a, b)
        self.assertFalse(outcome.fled)
        loser = a if outcome.loser_name == a.name else b
        self.assertEqual(loser.hit_points, 15)

    def test_winner_hit_points_never_forced_negative_by_loss_floor(self):
        a = _make_duelist('Attacker', hit_points=100)
        b = _make_duelist('Defender', hit_points=5)
        resolve_sport_duel(a, b)
        # Only the loser gets the hp=15 floor; the winner's hp is whatever
        # combat left it at (not artificially bumped).
        self.assertGreater(a.hit_points, 0)

    def test_rounds_recorded_for_both_sides(self):
        a = _make_duelist('Attacker')
        b = _make_duelist('Defender')
        outcome = resolve_sport_duel(a, b)
        self.assertGreater(len(outcome.rounds), 0)
        names = {r.attacker_name for r in outcome.rounds}
        self.assertTrue(names.issubset({a.name, b.name}))


class TestGuildStandings(unittest.TestCase):
    def setUp(self):
        import guild_standings
        self._orig_file = guild_standings._STANDINGS_FILE
        guild_standings._STANDINGS_FILE = Path('run') / 'server' / 'test_guild_standings.json'
        if guild_standings._STANDINGS_FILE.exists():
            guild_standings._STANDINGS_FILE.unlink()

    def tearDown(self):
        import guild_standings
        if guild_standings._STANDINGS_FILE.exists():
            guild_standings._STANDINGS_FILE.unlink()
        guild_standings._STANDINGS_FILE = self._orig_file

    def test_record_duel_result_increments_both_sides(self):
        from guild_standings import load_standings, record_duel_result
        record_duel_result('Mark of the Claw', 'Iron Fist')
        standings = load_standings()
        self.assertEqual(standings['Mark of the Claw']['wins'], 1)
        self.assertEqual(standings['Iron Fist']['losses'], 1)

    def test_repeated_results_accumulate(self):
        from guild_standings import load_standings, record_duel_result
        record_duel_result('Mark of the Claw', 'Iron Fist')
        record_duel_result('Mark of the Claw', 'Iron Fist')
        standings = load_standings()
        self.assertEqual(standings['Mark of the Claw']['wins'], 2)
        self.assertEqual(standings['Iron Fist']['losses'], 2)


if __name__ == '__main__':
    unittest.main()
