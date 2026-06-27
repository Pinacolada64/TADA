import asyncio
import json
import os
import time


def test_abrupt_disconnect_saves_player(tmp_path):
    """Start server, connect as guest, then close socket without sending 'bye'. Verify player JSON saved."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')

    from simple_server import Server
    from simple_client import perform_handshake, send_message, receive_message
    from net_common import Message, Mode
    from player import Player

    server = Server('127.0.0.1', 0)

    async def run_scenario():
        server_task = asyncio.create_task(server.start())
        # wait for server socket
        for _ in range(200):
            if getattr(server, 'server', None) and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server.server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        await perform_handshake(reader, writer)
        # request guest connection
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
                        assigned_username = ln.split()[2].strip('.').strip()
                        break
            if assigned_username:
                break
        assert assigned_username is not None

        # Optionally perform an action so player state may change; we'll just close abruptly now
        # Abruptly close the transport to simulate network failure
        try:
            transport = writer.transport
            transport.abort()
        except Exception:
            # fallback: close without sending bye
            try:
                writer.close()
            except Exception:
                pass

        # Give server a moment to detect closure and handle quit
        await asyncio.sleep(0.25)

        # cancel server
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

        return assigned_username

    assigned = asyncio.run(run_scenario())

    p = Player(name='probe', id=assigned)
    path = p._json_path(assigned)

    # wait up to 2s for file to appear
    deadline = time.time() + 2
    while time.time() < deadline and not os.path.exists(path):
        time.sleep(0.05)

    assert os.path.exists(path), f'Player file {path} not found after abrupt disconnect'

    with open(path, 'r') as f:
        data = json.load(f)

    # basic sanity: id/name present
    assert data.get('id') == assigned or data.get('name') == assigned

    # cleanup
    try:
        os.remove(path)
    except Exception:
        pass

