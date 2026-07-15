#!/usr/bin/env python3
"""Tests login flow: guest login should place client in a room and send room description."""
import asyncio

from simple_server import Server
import net_common
from tests.movement.test_movement import FakeWriter
from commands.command_processor import create_command_processor


def test_guest_login_sets_room_and_sends_description():
    s = Server('127.0.0.1', 0)

    class DummyClient:
        pass

    # create fake client writer
    writer = FakeWriter()

    mover = DummyClient()
    mover.server = s
    mover.room = None
    mover.username = None
    mover.addr = ('127.0.0.1', 10011)
    mover.writer = writer

    # create a per-client processor similar to handshake
    mover.command_processor = create_command_processor(mover, context={'username': None, 'is_authenticated': False})

    # register client in server.clients so username uniqueness checks examine it (empty username fine)
    s.clients[mover.addr] = mover

    # simulate inline guest flow: create a minimal message with lines = ['guest']
    from net_common import Message, MessageType, Mode
    msg = Message(lines=['guest'], mode=Mode.login, type=MessageType.REGULAR)

    # call handle_login_mode directly (it's async)
    asyncio.run(s.handle_login_mode(mover, msg, writer))

    # after this, mover should have username and room set and writer should have buffer
    assert getattr(mover, 'username', None) is not None
    assert getattr(mover, 'room', None) is not None
    assert len(writer.buf) > 0


if __name__ == '__main__':
    test_guest_login_sets_room_and_sends_description()
    print('PASS: test_guest_login_sets_room_and_sends_description')
