# test to ensure other players in a room are listed
from simple_server import Server
from tada_utilities import list_players_in_room


def _make_server():
    return Server('127.0.0.1', 0)


class DummyClient:
    ctx = None
    virtual_location = None


def test_describe_room_shows_other_players():
    s = Server('127.0.0.1', 0)

    c1 = DummyClient()
    c1.room     = 1
    c1.username = 'Alice'

    c2 = DummyClient()
    c2.room     = 1
    c2.username = 'Bob'

    s.clients['addr1'] = c1
    s.clients['addr2'] = c2

    subj = DummyClient()
    subj.room = 1

    lines = s._describe_room(subj)
    full  = '\n'.join(lines)

    assert 'Alice' in full, f'Alice not found in room description: {lines}'
    assert 'Bob'   in full, f'Bob not found in room description: {lines}'


def test_describe_room_hides_players_in_virtual_location():
    """Players inside a virtual area (shoppe, elevator) must not appear in room listings."""
    s = Server('127.0.0.1', 0)

    # Railbender is in room 1 but currently inside the shoppe
    rb = DummyClient()
    rb.room             = 1
    rb.username         = 'Railbender'
    rb.virtual_location = 'shoppe'

    # Alice is in room 1 and not in any virtual area
    alice = DummyClient()
    alice.room     = 1
    alice.username = 'Alice'

    s.clients['rb']    = rb
    s.clients['alice'] = alice

    subj = DummyClient()
    subj.room = 1

    lines = s._describe_room(subj)
    full  = '\n'.join(lines)

    assert 'Alice'       in full, 'Alice should be visible in the room'
    assert 'Railbender' not in full, 'Railbender is in shoppe — should not appear in room'


def test_describe_room_excludes_self():
    s = Server('127.0.0.1', 0)

    subj = DummyClient()
    subj.room     = 1
    subj.username = 'Tester'

    s.clients['subj'] = subj

    lines = s._describe_room(subj)
    full  = '\n'.join(lines)

    assert 'Tester' not in full, 'Player should not see themselves in room listing'


def test_describe_room_excludes_different_room():
    s = Server('127.0.0.1', 0)

    other = DummyClient()
    other.room     = 99
    other.username = 'FarAway'

    s.clients['other'] = other

    subj = DummyClient()
    subj.room = 1

    lines = s._describe_room(subj)
    full  = '\n'.join(lines)

    assert 'FarAway' not in full, 'Player in different room should not appear'


if __name__ == '__main__':
    test_describe_room_shows_other_players()
    test_describe_room_hides_players_in_virtual_location()
    test_describe_room_excludes_self()
    test_describe_room_excludes_different_room()
    print('All tests passed.')
