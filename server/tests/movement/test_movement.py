import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from simple_server import Server
from commands.movement import MoveCommand


def test_move_broadcasts_and_changes_room():
    """Moving through a real exit updates the client's room and shows it.

    Rewritten against the current architecture (same generation of stale
    test as tests/e2e/test_login_flow.py -- see that file's docstring).
    The previous version drove commands.command_processor.process_input()
    with a bare dict context (no ctx= kwarg), which command_processor.py
    only accepts as a *fallback* -- MoveCommand.execute() needs a real
    ctx with .send()/.server/.client/.player, which a dict doesn't have.
    It also asserted on a room-broadcast-to-other-clients-in-the-room
    behavior that doesn't exist anywhere in the current movement code
    (no send_room() call in commands/movement.py or Server._move()) --
    dropped rather than reintroduced speculatively.

    Room exit lookup goes through Room.get_exit() (see
    tests/movement/test_multilevel_room_lookup.py's regression coverage)
    since room data is keyed by full words (north/south/...), not the
    single letters MoveCommand's aliases accept.
    """
    s = Server('127.0.0.1', 0)

    room = s.game_map.rooms[1]
    direction = None
    for d in ['n', 's', 'e', 'w', 'u', 'd']:
        if room.get_exit(d):
            direction = d
            break
    if direction is None:
        raise RuntimeError('No exits available in test room; cannot test movement')
    dest = room.get_exit(direction)

    ctx = MagicMock()
    ctx.server           = s
    ctx.client.room       = 1
    ctx.player.map_level  = 1
    ctx.player.map_room   = 1
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()

    with patch('ally_events.try_ally_find_gold', new=AsyncMock()):
        res = asyncio.run(MoveCommand().execute(ctx, direction))

    assert res.success is True
    assert ctx.client.room == dest
    ctx.send.assert_called()   # room description sent to the mover


def test_moving_north_from_room_49_on_level_1_enters_bar():
    """SPUR.MAIN.S: "if cl=1 then if cr=49 then if di=1 link dy$" -- the
    Wall Bar & Grill's real trigger, level 1 room 49 moving north.
    Confirmed against the actual loaded map data (level 1 room 49's own
    north exit really is room 37, "WALL BAR & GRILL")."""
    s = Server('127.0.0.1', 0)

    ctx = MagicMock()
    ctx.server            = s
    ctx.client.room       = 49
    ctx.player.map_level  = 1
    ctx.player.map_room   = 49
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()

    with patch('bar.main.enter_bar', new=AsyncMock()) as enter_bar, \
         patch.object(s, '_show_room', new=AsyncMock()):
        res = asyncio.run(MoveCommand().execute(ctx, 'n'))

    assert res.success is True
    enter_bar.assert_awaited_once()


def test_moving_to_room_37_on_a_different_level_does_not_enter_bar():
    """Regression: the bar's room-number check (_BAR_ROOM = 37, this
    port's own exit-destination number, not SPUR's source room number)
    used to fire on *any* level whose map happened to route an exit to
    room 37, since only the destination room number was checked, never
    the player's level -- confirmed live, moving to room 49 on a
    different level dropped the player straight into the bar. The real
    trigger is level-gated in the original source (see the test above),
    same as its Allys Guild/Jake's Stable siblings.
    """
    s = Server('127.0.0.1', 0)

    fake_room = MagicMock()
    fake_room.get_exit.return_value = 37
    fake_room.exits = {}
    fake_room.flags = []   # explicit -- an auto-mocked attribute here would
                            # make _room_has_flag()'s `in` check ambiguous
    fake_game_map = MagicMock()
    fake_game_map.get_room.return_value = fake_room

    ctx = MagicMock()
    ctx.server            = s
    ctx.client.room       = 49
    ctx.player.map_level  = 2   # not level 1 -- the bar's real level
    ctx.player.map_room   = 49
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()

    with patch.object(s, 'game_map', fake_game_map), \
         patch.object(s, '_move', new=AsyncMock()) as move, \
         patch.object(s, '_show_room', new=AsyncMock()), \
         patch('bar.main.enter_bar', new=AsyncMock()) as enter_bar:
        res = asyncio.run(MoveCommand().execute(ctx, 'n'))

    assert res.success is True
    enter_bar.assert_not_awaited()
    move.assert_awaited_once()   # fell through to normal movement instead


if __name__ == '__main__':
    test_move_broadcasts_and_changes_room()
    print('PASS: test_move_broadcasts_and_changes_room')
    test_moving_north_from_room_49_on_level_1_enters_bar()
    print('PASS: test_moving_north_from_room_49_on_level_1_enters_bar')
    test_moving_to_room_37_on_a_different_level_does_not_enter_bar()
    print('PASS: test_moving_to_room_37_on_a_different_level_does_not_enter_bar')
