# test to ensure other players in a room are listed
import asyncio

from simple_server import Server
from commands.command_processor import create_command_processor
import net_common
from tada_utilities import list_players_in_room


def test_describe_room_shows_other_players():
    s = Server('127.0.0.1', 0)

    class DummyClient:
        pass

    # create two other clients and register them in client_manager
    c1 = DummyClient()
    c1.server = s
    c1.room = 1
    c1.username = 'Alice'

    c2 = DummyClient()
    c2.server = s
    c2.room = 1
    c2.username = 'Bob'

    # register in global client_manager
    net_common.client_manager.add_client(c1.username, c1)
    net_common.client_manager.add_client(c2.username, c2)

    # create the subject client (the one running look), put them in same room
    subj = DummyClient()
    subj.server = s
    subj.room = 1
    subj.username = 'Tester'

    # now describe the room for subj
    lines = s._describe_room(subj)

    # build expected players line (order may differ, so check substrings)
    expected_players_line = list_players_in_room([c1.username, c2.username])

    # Verify that one of the returned lines equals expected players line
    assert any(line.strip() == expected_players_line for line in lines), f"Players line not found. lines={lines}"


if __name__ == '__main__':
    try:
        test_describe_room_shows_other_players()
        print('PASS: test_describe_room_shows_other_players')
    except AssertionError:
        print('FAIL: test_describe_room_shows_other_players')
        raise
