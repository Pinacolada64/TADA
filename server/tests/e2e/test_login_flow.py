"""Tests login flow: guest login should place client in a room and send room description.

Rewritten against the current architecture (see tests/e2e/test_integration_quit.py's
docstring for the same kind of rewrite applied to QuitCommand). The previous
version of this test called a `Server.handle_login_mode(mover, msg, writer)`
method that no longer exists -- login/room-entry is handled by
Server._game_loop() (simple_server.py), which sets ctx.client.room from
ctx.player.map_room and then sends the room description via _show_room().
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from network_context import GuestPlayer
from simple_server import Server


def test_guest_login_sets_room_and_sends_description():
    server = Server('127.0.0.1', 0)

    ctx        = MagicMock()
    ctx.player = GuestPlayer()
    ctx.client.room = None
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()
    # Disconnect immediately after the room is shown, so _game_loop() exits
    # after exactly one _show_room() call instead of looping forever.
    ctx.prompt = AsyncMock(return_value=None)

    asyncio.run(server._game_loop(ctx))

    assert ctx.client.room is not None
    ctx.send.assert_called()


if __name__ == '__main__':
    test_guest_login_sets_room_and_sends_description()
    print('PASS: test_guest_login_sets_room_and_sends_description')
