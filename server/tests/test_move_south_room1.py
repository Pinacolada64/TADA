import asyncio
import json
import os
import time


def test_move_south_from_room1_goes_to_13_and_saves(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    from simple_server import Server
    from simple_client import perform_handshake, send_message, receive_message
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
        await perform_handshake(reader, writer)
        # request guest connection
        await send_message(writer, Message(lines=['guest'], mode=Mode.login))

        assigned_username = None
        start = time.time()
        while time.time() - start < 3:
            msg = await receive_message(reader)
            if not msg:
                break
            lines = msg.get('lines') if isinstance(msg, dict) else None
            if lines:
                for ln in lines:
                    if isinstance(ln, str) and ln.startswith('Connected as '):
                        assigned_username = ln.split()[2].strip('.').strip()
                        break
            if assigned_username:
                break
        assert assigned_username is not None

        # send 's' to move south
        await send_message(writer, Message(lines=['s'], mode=Mode.app))
        # give server a moment to process
        await asyncio.sleep(0.1)

        # inspect server client to confirm room change
        server_client = None
        for addr, c in server.clients.items():
            if getattr(c, 'username', None) == assigned_username:
                server_client = c
                break
        assert server_client is not None, 'server client not found'
        # both client.room and player.map_room should be 13 per level_1.json
        assert getattr(server_client, 'room', None) == 13
        assert getattr(getattr(server_client, 'player', None), 'map_room', None) == 13

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
        return assigned_username

    assigned = asyncio.run(run_scenario())

    # Check saved JSON
    p = Player(name='probe', id=assigned)
    path = p._json_path(assigned)
    assert os.path.exists(path)
    with open(path, 'r') as f:
        data = json.load(f)
    assert data.get('map_room') == 13

    try:
        os.remove(path)
    except Exception:
        pass

