import asyncio
import json
import os

from pprint import pprint

from conftest import perform_login, seed_test_account

_USERNAME = 'e2erealogin'
_PASSWORD = 'e2epass'


def test_network_e2e_real_login_and_save(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')
    seed_test_account(_USERNAME, _PASSWORD)

    from simple_server import Server
    from simple_client import send_message
    from net_common import Message, Mode

    server = Server('127.0.0.1', 0)

    async def run_scenario():
        # start server in background
        server_task = asyncio.create_task(server.start())
        # wait until server has a bound socket
        for _ in range(200):
            if getattr(server, 'server', None) is not None and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        else:
            server_task.cancel()
            raise RuntimeError('Server failed to bind')

        port = server.server.sockets[0].getsockname()[1]

        # connect as a client, handshake, and log in with real credentials
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        logged_in = await perform_login(reader, writer, _USERNAME, _PASSWORD)
        assert logged_in, 'Did not receive login confirmation'

        # send a bye message to trigger player quit/save
        await send_message(writer, Message(lines=[], mode=Mode.bye))
        # wait a short while for server to process quit/save
        await asyncio.sleep(0.25)

        # close client
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

        # shut down server task
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    asyncio.run(asyncio.wait_for(run_scenario(), timeout=10))

    # check for saved player file
    from player import Player
    temp_player = Player(name='probe', id=_USERNAME)
    path = temp_player._json_path(_USERNAME)
    assert os.path.exists(path), f'Player file {path} not found'

    with open(path, 'r') as f:
        data = json.load(f)
    pprint(data)
    # flags must be minimal mapping name-> {name,status}
    assert 'flags' in data and isinstance(data['flags'], dict)
    for v in data['flags'].values():
        assert set(v.keys()) <= {'name', 'status'}
        assert isinstance(v['status'], bool)

    # cleanup
    try:
        os.remove(path)
    except Exception:
        pass
