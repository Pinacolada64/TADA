import asyncio
import json
import os

from conftest import perform_login, seed_test_account

_USERNAME = 'e2ereconnect'
_PASSWORD = 'e2epass'


def test_network_e2e_reconnect_restores_room(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')
    seed_test_account(_USERNAME, _PASSWORD, map_room=1)

    from simple_server import Server
    from simple_client import send_message
    from net_common import Message, Mode
    from player import Player

    server = Server('127.0.0.1', 0, 0)

    async def run_scenario():
        server_task = asyncio.create_task(server.start())
        # wait until server bound
        for _ in range(200):
            if getattr(server, 'server', None) is not None and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        else:
            server_task.cancel()
            raise RuntimeError('Server failed to bind')
        port = server.server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        logged_in = await perform_login(reader, writer, _USERNAME, _PASSWORD)
        assert logged_in

        # Move south from room 1 to room 13, per level_1.json's exits.
        await send_message(writer, Message(lines=['s'], mode=Mode.app))
        await asyncio.sleep(0.1)

        # send bye to save
        await send_message(writer, Message(lines=[], mode=Mode.bye))
        await asyncio.sleep(0.25)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

        # cancel server
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(asyncio.wait_for(run_scenario(), timeout=10))

    # confirm saved file exists and reflects the move
    p = Player(name='probe', id=_USERNAME)
    path = p._json_path(_USERNAME)
    assert os.path.exists(path), f'Player file {path} missing'
    with open(path, 'r') as f:
        data = json.load(f)
    assert data.get('map_room') == 13

    # Now reconnect and login as same user and check server player object restores room
    # Start server again
    server2 = Server('127.0.0.1', 0, 0)

    async def reconnect_scenario():
        server_task = asyncio.create_task(server2.start())
        for _ in range(200):
            if getattr(server2, 'server', None) is not None and server2.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server2.server.sockets[0].getsockname()[1]

        r2, w2 = await asyncio.open_connection('127.0.0.1', port)
        logged_in = await perform_login(r2, w2, _USERNAME, _PASSWORD)
        assert logged_in

        # check server's internal client player. The player lives at
        # client.ctx.player (never client.player -- that attribute is
        # never set anywhere in the codebase).
        restored_room = None
        for addr, client in list(server2.clients.items()):
            if getattr(client, 'username', None) == _USERNAME:
                pl = getattr(getattr(client, 'ctx', None), 'player', None)
                if pl:
                    restored_room = getattr(pl, 'map_room', None)
                break

        # Close our client connection before cancelling the server -- on
        # Python 3.12+, Server.wait_closed() (called by start()'s "async
        # with json_server, petscii_server:" teardown) also waits for
        # existing client connections to close, so leaving w2 open here
        # hangs the cancellation forever.
        try:
            w2.close()
            await w2.wait_closed()
        except Exception:
            pass

        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        return restored_room

    restored_room = asyncio.run(asyncio.wait_for(reconnect_scenario(), timeout=10))
    assert restored_room == 13

    # cleanup
    try:
        os.remove(path)
    except Exception:
        pass
