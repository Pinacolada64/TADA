#!/usr/bin/env python3
"""Tests for rc/rt exit handling in old_server.Room.exitsTxt

Verifies that:
- 'rc' is treated as the connection flag (1=Up, 2=Down)
- 'rt' is treated as the transport/target (0=Shoppe, >0 room number)
- string values from JSON are handled (defensive int coercion)
"""
import os
import sys
import pytest

# add project root to path (mirrors other tests)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import old_server


def test_exits_up_to_room_and_direction_label():
    room = old_server.Room(number=1, name="Test", desc="", exits={'n': 2, 'rc': 1, 'rt': 5})
    txt = room.exitsTxt(debug=True)
    assert 'North' in txt
    assert 'Up to #5' in txt


def test_exits_up_to_shoppe():
    room = old_server.Room(number=2, name="ShopTest", desc="", exits={'rc': 1, 'rt': 0})
    txt = room.exitsTxt(debug=True)
    # (1,0) maps to 'Up to Shoppe' via extra_txts
    assert 'Up to Shoppe' in txt


def test_exits_string_values_coerced():
    # rc and rt provided as strings (as might come from JSON)
    room = old_server.Room(number=3, name="StringTest", desc="", exits={'e': 4, 'rc': '2', 'rt': '23'})
    txt = room.exitsTxt(debug=True)
    assert 'East' in txt
    assert 'Down to #23' in txt

