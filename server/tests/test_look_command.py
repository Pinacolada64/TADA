import asyncio

from simple_server import Server
from commands.command_processor import create_command_processor


def test_look_uses_server_description():
    """Verify the 'look' command returns the same lines as Server._describe_room(client).

    This test constructs a Server, a dummy client attached to that server,
    runs the per-client command processor to execute the 'look' command and
    compares the CommandResult to the server-side room description helper.
    """
    # Create server (loads map data)
    s = Server('127.0.0.1', 0)

    class DummyClient:
        pass

    client = DummyClient()
    client.server = s
    client.room = 1
    client.username = 'unittest'

    proc = create_command_processor(client, context={'client': client, 'username': client.username, 'is_authenticated': True})

    # Run the processor synchronously using asyncio.run
    result = asyncio.run(proc.process_input('look'))

    expected_lines = s._describe_room(client)

    # The processor/command may populate either message (as a list) or lines; accept both
    if isinstance(result.message, list):
        assert result.message == expected_lines
    elif getattr(result, 'lines', None):
        assert result.lines == expected_lines
    else:
        # Fallback: compare the stringified message to the joined expected lines
        assert [str(result.message)] == expected_lines


if __name__ == '__main__':
    # Run the test directly so CI isn't required. Will raise AssertionError on failure.
    try:
        test_look_uses_server_description()
        print('PASS: test_look_uses_server_description')
    except AssertionError as e:
        print('FAIL: test_look_uses_server_description')
        raise
