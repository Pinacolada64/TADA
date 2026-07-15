"""tests/test_hidden_exit_data.py

Regression coverage for the confirmed hidden_exit_east/west data baked into
level_1.json, level_2.json, level_5.json, and level_6.json -- guards against
a future data edit silently breaking one of these traced destinations.

All 12 currently-known hidden-exit rooms are confirmed (see MECHANICS.md's
Hidden exits entries): one hardcoded cross-level teleport (level 1 room 89),
and 11 same-level cr +/-1 rooms derived from SPUR.MAIN.S:169-171's row
arithmetic using each level's real row width (from D.LEVEL{n}.TXT headers:
level 2 ri=15, level 5 ri=20, level 6 ri=30), each corroborated by the
guarded room -> connector/reward room pairing in the actual room data.

Run with:
    python -m pytest tests/test_hidden_exit_data.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

from base_classes import Map

_LEVEL_DIR = Path(__file__).parent.parent.parent


@pytest.fixture(scope='module')
def game_map() -> Map:
    m = Map()
    for lvl in (1, 2, 5, 6):
        m.read_map(str(_LEVEL_DIR / f'level_{lvl}.json'), level=lvl)
    return m


# (level, room, direction, expected_target_level, expected_target_room)
_CONFIRMED = [
    (1, 89,  'e', 5, 41),   # Teleport Room -> Land of the Wraiths (cross-level)
    (2, 155, 'e', 2, 156),  # Burial Chamber -> Narrow Tunnel
    (2, 157, 'e', 2, 158),  # Mummy's Tomb -> Secret Chamber
    (2, 157, 'w', 2, 156),  # Mummy's Tomb -> Narrow Tunnel
    (5, 85,  'e', 5, 86),   # Cold Cave -> Inner Cave
    (5, 140, 'e', 5, 141),  # Village -> The Chief's Treasure Room
    (6, 45,  'e', 6, 46),   # Engineering -> Access Tunnel
    (6, 49,  'w', 6, 48),   # Engineering -> Equipment Locker
    (6, 79,  'e', 6, 80),   # Access Tunnel -> Vent Duct
    (6, 99,  'e', 6, 100),  # Main Reactor -> Storage Closet
    (6, 109, 'w', 6, 108),  # Main Reactor -> Security Bunker
    (6, 115, 'e', 6, 116),  # Witches Coven -> Witches House
    (6, 186, 'e', 6, 187),  # A Strange Room -> Garden Of Eden
]


@pytest.mark.parametrize('level,room_no,direction,exp_level,exp_room', _CONFIRMED)
def test_confirmed_hidden_exit(game_map, level, room_no, direction, exp_level, exp_room):
    room = game_map.get_room(level, room_no)
    assert room is not None, f'room {room_no} missing from level {level}'
    target = room.hidden_exit(direction, level)
    assert target is not None, f'room {room_no} has no confirmed {direction} hidden exit'
    assert (target.level, target.room) == (exp_level, exp_room)
    # The destination itself must actually exist in the loaded map data.
    assert game_map.get_room(target.level, target.room) is not None


def test_no_leftover_legacy_flag_strings(game_map):
    """Confirmed rooms should have dropped the old hidden_exit_east/west flag
    string now that the real field carries the same information -- avoids
    two sources of truth that could drift apart."""
    seen = set()
    for level, room_no, _direction, _el, _er in _CONFIRMED:
        if (level, room_no) in seen:
            continue
        seen.add((level, room_no))
        room = game_map.get_room(level, room_no)
        flags = getattr(room, 'flags', None) or []
        assert 'hidden_exit_east' not in flags
        assert 'hidden_exit_west' not in flags
