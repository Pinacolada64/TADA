import asyncio
import json
import os
import time

from pprint import pprint


def test_network_e2e_real_login_and_save(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    from simple_server import Server
    from simple_client import perform_handshake, send_message, receive_message
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

        # connect as a client and run handshake
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        # perform handshake (this will send client init and consume server init)
        banner = await perform_handshake(reader, writer)
        # after handshake we should get a login banner; now request guest connection
        await send_message(writer, Message(lines=['guest'], mode=Mode.login))

        # collect messages until we see 'Connected as' or timeout
        assigned_username = None
        start = time.time()
        while time.time() - start < 3:
            msg = await receive_message(reader)
            if not msg:
                break
            # msg is a dict representing Message; look at its 'lines'
            lines = msg.get('lines') if isinstance(msg, dict) else None
            if lines:
                for ln in lines:
                    if isinstance(ln, str) and ln.startswith('Connected as '):
                        # format: "Connected as Guest1."
                        parts = ln.split()
                        if len(parts) >= 3:
                            assigned_username = parts[2].strip('.').strip()
                            break
            if assigned_username:
                break
        assert assigned_username is not None, 'Did not receive Connected as message'

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

        return assigned_username

    assigned_username = asyncio.run(run_scenario())

    # check for saved player file
    from player import Player
    temp_player = Player(name='probe', id=assigned_username)
    path = temp_player._json_path(assigned_username)
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

