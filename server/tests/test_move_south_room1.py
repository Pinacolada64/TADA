import asyncio
import json
import os

from conftest import perform_login, seed_test_account

_USERNAME = 'e2emover'
_PASSWORD = 'e2epass'


def test_move_south_from_room1_goes_to_13_and_saves(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')
    seed_test_account(_USERNAME, _PASSWORD, map_room=1)

    from simple_server import Server
    from simple_client import send_message
    from net_common import Message, Mode
    from player import Player

    server = Server('127.0.0.1', 0)

    async def run_scenario():
        server_task = asyncio.create_task(server.start())
        for _ in range(200):
            if getattr(server, 'server', None) and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server.server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        logged_in = await perform_login(reader, writer, _USERNAME, _PASSWORD)
        assert logged_in

        # send 's' to move south
        await send_message(writer, Message(lines=['s'], mode=Mode.app))
        # give server a moment to process
        await asyncio.sleep(0.1)

        # inspect server client to confirm room change. The player lives at
        # client.ctx.player (never client.player -- that attribute is never
        # set anywhere in the codebase).
        server_client = None
        for addr, c in server.clients.items():
            if getattr(c, 'username', None) == _USERNAME:
                server_client = c
                break
        assert server_client is not None, 'server client not found'
        # both client.room and player.map_room should be 13 per level_1.json
        assert getattr(server_client, 'room', None) == 13
        assert getattr(getattr(server_client, 'ctx', None).player, 'map_room', None) == 13

        # send bye to save and close
        await send_message(writer, Message(lines=[], mode=Mode.bye))
        await asyncio.sleep(0.2)
        try:
            writer.close(); await writer.wait_closed()
        except Exception:
            pass
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(asyncio.wait_for(run_scenario(), timeout=10))

    # Check saved JSON
    p = Player(name='probe', id=_USERNAME)
    path = p._json_path(_USERNAME)
    assert os.path.exists(path)
    with open(path, 'r') as f:
        data = json.load(f)
    assert data.get('map_room') == 13

    try:
        os.remove(path)
    except Exception:
        pass
