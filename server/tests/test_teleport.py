import asyncio
from commands.command_processor import create_command_processor
from flags import PlayerFlags


class DummyPlayer:
    def __init__(self, is_admin: bool = False):
        self._is_admin = is_admin
        self.map_room = 1

    def query_flag(self, flag):
        # Return True only for PlayerFlags.ADMIN when _is_admin is True
        try:
            return flag == PlayerFlags.ADMIN and self._is_admin
        except Exception:
            return False


class DummyServer:
    def __init__(self):
        class GameMap:
            def __init__(self):
                self.rooms = {37: object(), 1: object()}

        self.game_map = GameMap()

    def _describe_room(self, client):
        # Return a simple description that includes the room number
        return [f"ROOM {getattr(client, 'room', None)} description"]


class DummyClient:
    def __init__(self, player: DummyPlayer, server: DummyServer):
        self.player = player
        self.server = server
        # keep a client.room in sync with player.map_room initially
        self.room = getattr(player, 'map_room', 1)


def run_proc(client, input_text: str):
    proc = create_command_processor(client)
    return asyncio.run(proc.process_input(input_text))


def test_teleport_admin_allows():
    player = DummyPlayer(is_admin=True)
    server = DummyServer()
    client = DummyClient(player, server)

    res = run_proc(client, '#37')
    assert res.success is True
    assert res.data.get('room') == 37
    # message should include the description returned by DummyServer
    assert any('ROOM 37' in line for line in (res.message if isinstance(res.message, list) else [str(res.message)]))


def test_teleport_non_admin_denied():
    player = DummyPlayer(is_admin=False)
    server = DummyServer()
    client = DummyClient(player, server)

    res = run_proc(client, '#37')
    assert res.success is False
    assert res.error == 'permission_denied'


def test_teleport_with_space_variant():
    player = DummyPlayer(is_admin=True)
    server = DummyServer()
    client = DummyClient(player, server)

    # space-separated token should also work: '# 37'
    res = run_proc(client, '# 37')
    assert res.success is True
    assert res.data.get('room') == 37
    assert any('ROOM 37' in line for line in (res.message if isinstance(res.message, list) else [str(res.message)]))

