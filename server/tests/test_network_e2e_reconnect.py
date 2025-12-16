import asyncio
import json
import os
import time


def test_network_e2e_reconnect_restores_room(tmp_path):
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    from simple_server import Server
    from simple_client import perform_handshake, send_message, receive_message
    from net_common import Message, Mode
    from player import Player

    server = Server('127.0.0.1', 0)

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
        await perform_handshake(reader, writer)
        await send_message(writer, Message(lines=['guest'], mode=Mode.login))

        # capture assigned username
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
                        parts = ln.split()
                        if len(parts) >= 3:
                            assigned_username = parts[2].strip('.').strip()
                            break
            if assigned_username:
                break
        assert assigned_username is not None

        # Try to move using common directions. We'll try 'e' then 'n' then 's' until one reports movement.
        dest_room = None
        tried_dirs = ['e', 'n', 's', 'w', 'u', 'd']
        for d in tried_dirs:
            await send_message(writer, Message(lines=[d], mode=Mode.app))
            # wait for a response and inspect if room changed in returned description
            got = await receive_message(reader)
            if not got:
                continue
            # If server returned data with 'lines' containing 'You move' or similar, assume moved
            lines = got.get('lines') if isinstance(got, dict) else []
            joined = ' '.join([str(x) for x in (lines or [])])
            if 'moves' in joined or 'move' in joined or 'You move' in joined:
                # best-effort: read saved file later; for now assume move succeeded and break
                dest_room = 'moved'
                break
        # If movement didn't work, set player's map_room directly on server to a sentinel (avoid relying on map data)
        if dest_room is None:
            # find the client object on server and sync player's location via server helper
            for addr, client in list(server.clients.items()):
                if getattr(client, 'username', None) and client.username == assigned_username:
                    try:
                        # Use server API to keep client.room and player.map_room consistent
                        server._sync_player_location(client, 9999)
                        expected_room = 9999
                    except Exception:
                        # fallback if helper unavailable
                        try:
                            client.player.map_room = 9999
                            expected_room = 9999
                        except Exception:
                            expected_room = 1
                    break
        else:
            # we don't know the exact numeric room; read saved player file later and compare changed value
            expected_room = None

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

        return assigned_username, expected_room

    assigned_username, expected_room = asyncio.run(run_scenario())

    # confirm saved file exists
    p = Player(name='probe', id=assigned_username)
    path = p._json_path(assigned_username)
    assert os.path.exists(path), f'Player file {path} missing'
    with open(path, 'r') as f:
        data = json.load(f)

    # If we set expected_room explicitly, verify saved map_room matches it; otherwise expect map_room to be present
    if expected_room is not None:
        assert data.get('map_room') == expected_room
    else:
        assert 'map_room' in data

    # Now reconnect and login as same user and check server player object restores room
    # Start server again
    server2 = Server('127.0.0.1', 0)

    async def reconnect_scenario():
        server_task = asyncio.create_task(server2.start())
        for _ in range(200):
            if getattr(server2, 'server', None) is not None and server2.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server2.server.sockets[0].getsockname()[1]

        r2, w2 = await asyncio.open_connection('127.0.0.1', port)
        await perform_handshake(r2, w2)
        # attempt to login: connect <username>
        await send_message(w2, Message(lines=[f'connect {assigned_username}'], mode=Mode.login))

        # read responses until we see a welcome or room description
        got_room = None
        start = time.time()
        while time.time() - start < 3:
            msg = await receive_message(r2)
            if not msg:
                break
            lines = msg.get('lines') if isinstance(msg, dict) else None
            if lines:
                for ln in lines:
                    if isinstance(ln, str) and ln.startswith('Login successful'):
                        # After login the server sends room description; we'll try to parse numeric room if present in data file
                        pass
            # check server's internal client player if available
            for addr, client in list(server2.clients.items()):
                if getattr(client, 'username', None) == assigned_username:
                    pl = getattr(client, 'player', None)
                    if pl:
                        return getattr(pl, 'map_room', None)
        # shutdown
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        return None

    restored_room = asyncio.run(reconnect_scenario())

    # If we had an explicit expected_room, compare; otherwise compare saved file vs restored_room
    if expected_room is not None:
        assert restored_room == expected_room
    else:
        assert restored_room == data.get('map_room', restored_room)

    # cleanup
    try:
        os.remove(path)
    except Exception:
        pass

