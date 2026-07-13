#!/usr/bin/env python3
"""Tests for rc/rt exit handling in base_classes.Room.exits_txt

Verifies that:
- 'rc' is treated as the connection flag (1=Up, 2=Down)
- 'rt' is treated as the transport/target (0=Shoppe, >0 room number)
- string values from JSON are handled (defensive int coercion)
"""
import os
import sys
import pytest
from base_classes import Room


# add project root to path (mirrors other tests)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class _Player:
    def __init__(self, is_debug: bool):
        self.is_debug = is_debug


class _Ctx:
    """Minimal ctx stand-in: exits_txt() only ever reads ctx.player.is_debug."""
    def __init__(self, is_debug: bool = False):
        self.player = _Player(is_debug)


def test_exits_up_to_room_and_direction_label():
    room = Room(number=1, name="Test", desc="", exits={'n': 2, 'rc': 1, 'rt': 5})
    txt = room.exits_txt(_Ctx(is_debug=True))
    assert 'North' in txt
    assert 'Up [to #5]' in txt


def test_exits_up_to_shoppe():
    room = Room(number=2, name="ShopTest", desc="", exits={'rc': 1, 'rt': 0})
    txt = room.exits_txt(_Ctx(is_debug=True))
    assert 'Up to Shoppe' in txt


def test_exits_string_values_coerced():
    # rc and rt provided as strings (as might come from JSON)
    room = Room(number=3, name="StringTest", desc="", exits={'e': 4, 'rc': '2', 'rt': '23'})
    txt = room.exits_txt(_Ctx(is_debug=True))
    assert 'East' in txt
    assert 'Down [to #23]' in txt

def test_exits_missing_rc_rt():
    room = Room(number=4, name="NoRCTest", desc="", exits={'s': 5})
    txt = room.exits_txt(_Ctx(is_debug=True))
    assert 'South' in txt
    assert 'Up' not in txt
    assert 'Down' not in txt
    assert 'Shoppe' not in txt

def test_exits_invalid_rc_rt():
    room = Room(number=5, name="InvalidRCTest", desc="", exits={'w': 6, 'rc': 'invalid', 'rt': 'also_invalid'})
    txt = room.exits_txt(_Ctx(is_debug=True))
    assert 'West' in txt
    assert 'Up' not in txt
    assert 'Down' not in txt
    assert 'Shoppe' not in txt


def test_exits_full_word_keys():
    # convert_from_gbbs_tool.py's EXIT_KEYS format (levels 2-7, and level_1.json
    # since its reconciliation onto the modern schema) -- full words, not the
    # short forms compass_txts is keyed by. Regression test: before the fix,
    # this silently produced an empty string, so "Ye may travel:" never
    # printed anything for any room using this key format.
    room = Room(number=157, name="The Ocean", desc="",
                exits={'north': 1, 'south': 1, 'west': 1})
    txt = room.exits_txt(_Ctx())
    assert 'North' in txt
    assert 'South' in txt
    assert 'West' in txt


def test_exits_full_word_keys_with_rc_rt():
    room = Room(number=6, name="MixedKeys", desc="",
                exits={'east': 7, 'rc': 1, 'rt': 0})
    txt = room.exits_txt(_Ctx(is_debug=True))
    assert 'East' in txt
    assert 'Up to Shoppe' in txt


def test_exits_not_debug_omits_room_numbers():
    room = Room(number=7, name="PlainTest", desc="", exits={'n': 2, 'rc': 1, 'rt': 5})
    txt = room.exits_txt(_Ctx(is_debug=False))
    assert 'North' in txt
    assert '#' not in txt


def test_exits_use_or_not_and():
    room = Room(number=8, name="ThreeWay", desc="", exits={'n': 2, 's': 3, 'e': 4})
    txt = room.exits_txt(_Ctx())
    assert txt == 'North, South, or East'


class TestGetExit:
    """Room.get_exit(): the actual movement lookup, not just the display text.

    Regression coverage for a real bug: commands/movement.py always resolves
    typed directions to short forms (n/s/e/w/u/d -- see _DIR_ALIASES) before
    calling Server._move(), but every level's exits dict is keyed by full
    words (convert_from_gbbs_tool.py's EXIT_KEYS). exits.get(direction) with
    a short-form direction against a full-word-keyed dict always returned
    None, so every real exit silently behaved like a dead end -- masked in
    prior tests only because the hidden-exit +/-1 fallback formula happened
    to produce the same destination room number in those specific fixtures.
    """

    def test_short_direction_resolves_full_word_key(self):
        room = Room(number=1, name="Test", desc="", exits={'east': 2})
        assert room.get_exit('e') == 2

    def test_full_word_direction_still_works(self):
        room = Room(number=1, name="Test", desc="", exits={'east': 2})
        assert room.get_exit('east') == 2

    def test_short_key_data_still_works(self):
        room = Room(number=1, name="Test", desc="", exits={'e': 2})
        assert room.get_exit('e') == 2

    def test_no_exit_that_direction_returns_none(self):
        room = Room(number=1, name="Test", desc="", exits={'east': 2})
        assert room.get_exit('w') is None

    def test_zero_destination_treated_as_no_exit(self):
        room = Room(number=1, name="Test", desc="", exits={'east': 0})
        assert room.get_exit('e') is None


class TestHiddenExit:
    """Room.hidden_exit(): confirmed hidden-exit destinations.

    Data-driven replacement for guessing target rooms via +/-1 adjacency --
    see MECHANICS.md's Hidden exits entries. A bare int means same-level;
    a {"room": n, "level": n} dict means a cross-level destination like
    level 1 room 89's hardcoded teleport.
    """

    def test_same_level_bare_int(self):
        room = Room(number=140, name="Village", desc="", hidden_exit_east=141)
        target = room.hidden_exit('e', current_level=5)
        assert (target.level, target.room, target.message_number) == (5, 141, None)

    def test_full_word_direction(self):
        room = Room(number=140, name="Village", desc="", hidden_exit_east=141)
        target = room.hidden_exit('east', current_level=5)
        assert (target.level, target.room) == (5, 141)

    def test_cross_level_dict(self):
        room = Room(number=89, name="Teleport Room", desc="",
                    hidden_exit_east={'room': 41, 'level': 5})
        target = room.hidden_exit('e', current_level=1)
        assert (target.level, target.room) == (5, 41)

    def test_cross_level_dict_with_message_number(self):
        room = Room(number=89, name="Teleport Room", desc="",
                    hidden_exit_east={'room': 41, 'level': 5, 'message_number': 18})
        target = room.hidden_exit('e', current_level=1)
        assert target.message_number == 18

    def test_unconfirmed_direction_returns_none(self):
        room = Room(number=140, name="Village", desc="", hidden_exit_east=141)
        assert room.hidden_exit('w', current_level=5) is None

    def test_no_hidden_exits_at_all(self):
        room = Room(number=1, name="Plain Room", desc="")
        assert room.hidden_exit('e', current_level=1) is None
