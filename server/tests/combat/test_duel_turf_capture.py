"""tests/combat/test_duel_turf_capture.py — combat/duel.py's
DuelSession._try_capture_turf(): Ryan's own extension (not a SPUR
mechanic) where winning a decisive SPORT DUEL flips the room's
RoomAlignment to the winner's guild, except HQ/FREE_FIRE rooms, which
stay immutable, and Civilian/Outlaw winners, who have no guild to
plant a flag for.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from base_classes import Guild, Map, PlayerClass, PlayerRace, Room, RoomAlignment
from combat.duel import DuelSession
from items import Weapon
from player import Player


class _TempStateDir(unittest.TestCase):
    def setUp(self):
        import room_alignment
        self._orig_dir = room_alignment._STATE_DIR
        room_alignment._STATE_DIR = Path('run') / 'server' / 'test_duel_turf_capture'
        if room_alignment._STATE_DIR.exists():
            for f in room_alignment._STATE_DIR.glob('*.json'):
                f.unlink()
            room_alignment._STATE_DIR.rmdir()

    def tearDown(self):
        import room_alignment
        if room_alignment._STATE_DIR.exists():
            for f in room_alignment._STATE_DIR.glob('*.json'):
                f.unlink()
            room_alignment._STATE_DIR.rmdir()
        room_alignment._STATE_DIR = self._orig_dir


class _FakeServer:
    def __init__(self, game_map):
        self.game_map = game_map
        self.clients: dict = {}


class _FakeCtx:
    def __init__(self, player, server=None):
        self.player = player
        self.server = server
        self.client = None
        self.sent: list = []

    async def send(self, *args):
        self.sent.extend(args)


def _make_duelist(name, *, guild=Guild.CIVILIAN, level=1, room_number=9):
    p = Player(name=name, id=name.lower())
    p.char_class = PlayerClass.FIGHTER
    p.char_race = PlayerRace.HUMAN
    p.guild = guild
    p.map_level = level
    p.map_room = room_number
    p.readied_weapon = Weapon(
        id_number=1, name='LONG SWORD', stability=50,
        to_hit=60, weapon_class='bash/slash',
    )
    return p


def _make_map(level: int, room_number: int, alignment=RoomAlignment.NEUTRAL) -> Map:
    game_map = Map()
    room = Room(number=room_number, name='Contested Square', desc='A room.', alignment=alignment)
    game_map.levels[level] = {room_number: room}
    return game_map


def _make_session(winner_guild, room_alignment_=RoomAlignment.NEUTRAL, level=1, room_number=9):
    game_map = _make_map(level, room_number, alignment=room_alignment_)
    server = _FakeServer(game_map)
    winner = _make_duelist('Ardent', guild=winner_guild, level=level, room_number=room_number)
    loser = _make_duelist('Belwin', guild=Guild.CIVILIAN)
    winner_ctx, loser_ctx = _FakeCtx(winner, server), _FakeCtx(loser, server)
    session = DuelSession(winner, winner_ctx, loser, loser_ctx)
    session.end_lines = {}   # normally set by _end() before it calls _try_capture_turf
    return session, game_map


class TestGuildGate(_TempStateDir):
    def test_civilian_winner_cannot_capture(self):
        session, game_map = _make_session(Guild.CIVILIAN)
        session._try_capture_turf(session.a, Guild.CIVILIAN)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.NEUTRAL)

    def test_outlaw_winner_cannot_capture(self):
        session, game_map = _make_session(Guild.OUTLAW)
        session._try_capture_turf(session.a, Guild.OUTLAW)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.NEUTRAL)

    def test_guild_winner_captures_neutral_room(self):
        session, game_map = _make_session(Guild.CLAW)
        session._try_capture_turf(session.a, Guild.CLAW)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.CLAW)


class TestImmutableRooms(_TempStateDir):
    def test_hq_room_cannot_be_captured(self):
        session, game_map = _make_session(Guild.FIST, room_alignment_=RoomAlignment.HQ)
        session._try_capture_turf(session.a, Guild.FIST)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.HQ)

    def test_free_fire_room_cannot_be_captured(self):
        session, game_map = _make_session(Guild.FIST, room_alignment_=RoomAlignment.FREE_FIRE)
        session._try_capture_turf(session.a, Guild.FIST)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.FREE_FIRE)


class TestNoOpAndFlavor(_TempStateDir):
    def test_already_aligned_to_winner_guild_is_a_no_op(self):
        session, game_map = _make_session(Guild.SWORD, room_alignment_=RoomAlignment.SWORD)
        session._try_capture_turf(session.a, Guild.SWORD)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.SWORD)
        self.assertEqual(session.end_lines, {})

    def test_capturing_enemy_turf_flips_it_and_adds_flavor(self):
        session, game_map = _make_session(Guild.SWORD, room_alignment_=RoomAlignment.FIST)
        session.end_lines = {id(session.a): 'existing win line'}
        session._try_capture_turf(session.a, Guild.SWORD)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.SWORD)
        self.assertIn('existing win line', session.end_lines[id(session.a)])
        self.assertIn('claim this room', session.end_lines[id(session.a)])
        self.assertTrue(any('claims' in n for n in session._terse_notes))


class TestPersistence(_TempStateDir):
    def test_capture_is_persisted_to_the_level_sidecar_file(self):
        from room_alignment import load_overrides
        session, game_map = _make_session(Guild.CLAW, level=3, room_number=17)
        session._try_capture_turf(session.a, Guild.CLAW)
        self.assertEqual(load_overrides(3), {'17': 'claw'})


if __name__ == '__main__':
    unittest.main()
