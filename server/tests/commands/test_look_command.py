import asyncio
from unittest.mock import AsyncMock, MagicMock

from simple_server import Server
from commands.command_processor import create_command_processor


def test_look_uses_server_description():
    """Verify the 'look' command sends the same lines as Server._describe_room(client).

    This test constructs a Server, a mock client/ctx pair attached to that
    server, runs the per-client command processor to execute the 'look'
    command and compares what was sent to ctx.send() against the
    server-side room description helper.

    LookCommand's no-target branch renders the room via
    `ctx.server._show_room(ctx)`, which sends the description straight to
    ctx.send() -- it doesn't put the text into CommandResult.message, so
    this test has to inspect the ctx.send() call rather than the result.
    """
    # Create server (loads map data)
    s = Server('127.0.0.1', 0)

    # LookCommand and Server._show_room/_describe_room need a real-ish
    # ctx/client pair (ctx.server, ctx.client, ctx.send, ctx.send_room,
    # and client.ctx.player for the room lookup) -- see
    # tests/movement/test_multilevel_room_lookup.py for the same pattern.
    ctx = MagicMock()
    ctx.server = s
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.player.name = 'unittest'
    ctx.player.map_level = 1
    ctx.client.room = 1
    ctx.client.ctx = ctx

    proc = create_command_processor(
        ctx.client,
        context={'client': ctx.client, 'username': 'unittest', 'is_authenticated': True},
    )

    # Run the processor synchronously using asyncio.run
    result = asyncio.run(proc.process_input('look', ctx=ctx))

    expected_lines = s._describe_room(ctx.client)

    assert result.success
    ctx.send.assert_awaited_once_with(expected_lines)


if __name__ == '__main__':
    # Run the test directly so CI isn't required. Will raise AssertionError on failure.
    try:
        test_look_uses_server_description()
        print('PASS: test_look_uses_server_description')
    except AssertionError as e:
        print('FAIL: test_look_uses_server_description')
        raise
