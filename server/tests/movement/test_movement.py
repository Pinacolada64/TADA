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


if __name__ == '__main__':
    test_move_broadcasts_and_changes_room()
    print('PASS: test_move_broadcasts_and_changes_room')
