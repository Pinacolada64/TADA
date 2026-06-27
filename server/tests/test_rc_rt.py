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

def test_exits_up_to_room_and_direction_label():
    room = Room(number=1, name="Test", desc="", exits={'n': 2, 'rc': 1, 'rt': 5})
    txt = room.exits_txt(debug=True)
    assert 'North' in txt
    assert 'Up to #5' in txt


def test_exits_up_to_shoppe():
    room = Room(number=2, name="ShopTest", desc="", exits={'rc': 1, 'rt': 0})
    txt = room.exits_txt(debug=True)
    assert 'Up to Shoppe' in txt


def test_exits_string_values_coerced():
    # rc and rt provided as strings (as might come from JSON)
    room = Room(number=3, name="StringTest", desc="", exits={'e': 4, 'rc': '2', 'rt': '23'})
    txt = room.exits_txt(debug=True)
    assert 'East' in txt
    assert 'Down to #23' in txt

def test_exits_missing_rc_rt():
    room = Room(number=4, name="NoRCTest", desc="", exits={'s': 5})
    txt = room.exits_txt(debug=True)
    assert 'South' in txt
    assert 'Up' not in txt
    assert 'Down' not in txt
    assert 'Shoppe' not in txt
    assert '#' not in txt

def test_exits_invalid_rc_rt():
    room = Room(number=5, name="InvalidRCTest", desc="", exits={'w': 6, 'rc': 'invalid', 'rt': 'also_invalid'})
    txt = room.exits_txt(debug=True)
    assert 'West' in txt
    assert 'Up' not in txt
    assert 'Down' not in txt
    assert 'Shoppe' not in txt
    assert '#' not in txt
