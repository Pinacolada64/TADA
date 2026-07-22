"""tests/test_wild_horse_placement.py

Unit tests for Server._place_wild_horse() (simple_server.py) -- randomizing
which level-1 "Edge of Forest" room holds the wild horse (monsters.json #136,
a TADA extension with no canonical SPUR placement) each time the server
starts. Mutates the live Map/Room object only; never written back to
level_1.json, so the location resets on restart.

Coverage:
  - placed room's monster field is set to the wild horse monster number
  - only one of the three candidate rooms is chosen (not all three)
  - the other two candidate rooms are left untouched
  - repeated calls can land on different rooms (randomization actually varies)
  - a missing game_map doesn't raise

Run with:
    python -m pytest tests/test_wild_horse_placement.py -v
"""
from unittest.mock import patch

import pytest

from simple_server import Server, _WILD_HORSE_ROOMS, _WILD_HORSE_MONSTER_NUMBER


@pytest.fixture
def server():
    return Server('127.0.0.1', 0)


def test_chosen_room_gets_wild_horse(server):
    horse_rooms = [n for n in _WILD_HORSE_ROOMS
                   if server.game_map.rooms[n].monster == _WILD_HORSE_MONSTER_NUMBER]
    assert len(horse_rooms) == 1


def test_other_candidate_rooms_untouched(server):
    horse_rooms = {n for n in _WILD_HORSE_ROOMS
                   if server.game_map.rooms[n].monster == _WILD_HORSE_MONSTER_NUMBER}
    chosen = next(iter(horse_rooms))
    for n in _WILD_HORSE_ROOMS:
        if n != chosen:
            assert server.game_map.rooms[n].monster != _WILD_HORSE_MONSTER_NUMBER


def test_placement_respects_random_choice():
    with patch('simple_server.random.choice', return_value=_WILD_HORSE_ROOMS[1]):
        s = Server('127.0.0.1', 0)
    assert s.game_map.rooms[_WILD_HORSE_ROOMS[1]].monster == _WILD_HORSE_MONSTER_NUMBER
    for n in _WILD_HORSE_ROOMS:
        if n != _WILD_HORSE_ROOMS[1]:
            assert s.game_map.rooms[n].monster != _WILD_HORSE_MONSTER_NUMBER


def test_randomization_varies_across_instances():
    seen = set()
    for _ in range(30):
        s = Server('127.0.0.1', 0)
        seen.update(n for n in _WILD_HORSE_ROOMS
                    if s.game_map.rooms[n].monster == _WILD_HORSE_MONSTER_NUMBER)
        if len(seen) > 1:
            break
    assert len(seen) > 1, 'expected randomization to pick more than one room across 30 tries'


def test_missing_game_map_does_not_raise(server):
    server.game_map = None
    server._place_wild_horse()   # should return quietly, not raise
