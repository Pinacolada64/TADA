"""tests/combat/test_stats_ring.py — commands/stats.py's "Ring worn." line:
requires BOTH the RING_WORN flag AND an actual Ring in the player's
inventory (via Player.has_item()) before it's shown. Ryan's request,
following up on the has_item() rework.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from base_classes import Guild, PlayerStat
from commands.stats import _build_stats_lines
from flags import PlayerFlags
from party import Party


def _make_player(*, ring_worn: bool, has_ring: bool):
    player = MagicMock()
    player.name = 'Rulan'
    player.stats = {s: 10 for s in PlayerStat}
    player.shield = 0
    player.armor = 0
    player.get_silver = lambda k: 100
    player.experience = 0
    player.dead_monsters = []
    player.honor = 1000
    player.xp_level = 1
    player.hit_points = 20
    player.guild = Guild.CIVILIAN
    player.char_class = None
    player.char_race = None
    player.active_shield_id = None
    player.shield_proficiency = {}
    player.query_flag = lambda f: f == PlayerFlags.RING_WORN and ring_worn
    player.has_item = MagicMock(return_value=has_ring)
    player.wizard_glow = None
    player.tuts_treasure = None
    player.time_remaining_minutes = None
    player.party = Party()
    return player


class TestRingWornLine(unittest.TestCase):
    def test_flag_and_item_both_present_shows_line(self):
        player = _make_player(ring_worn=True, has_ring=True)
        lines = _build_stats_lines(player)
        self.assertTrue(any('Ring worn' in l for l in lines))

    def test_flag_set_without_item_hides_line(self):
        """RING_WORN alone isn't enough -- the Ring must actually be in
        the player's inventory (has_item() checks both)."""
        player = _make_player(ring_worn=True, has_ring=False)
        lines = _build_stats_lines(player)
        self.assertFalse(any('Ring worn' in l for l in lines))

    def test_item_present_without_flag_hides_line(self):
        player = _make_player(ring_worn=False, has_ring=True)
        lines = _build_stats_lines(player)
        self.assertFalse(any('Ring worn' in l for l in lines))

    def test_neither_flag_nor_item_hides_line(self):
        player = _make_player(ring_worn=False, has_ring=False)
        lines = _build_stats_lines(player)
        self.assertFalse(any('Ring worn' in l for l in lines))

    def test_has_item_called_with_ring_category_and_name(self):
        from items import ItemCategory
        player = _make_player(ring_worn=True, has_ring=True)
        _build_stats_lines(player)
        player.has_item.assert_any_call(category=ItemCategory.ITEM, name="RING")


if __name__ == '__main__':
    unittest.main()
