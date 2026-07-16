import json
import os
import time
import asyncio

import pytest

from conftest import perform_login, seed_test_account

# Starts a real Server + real sockets -- slow, excluded from local
# default runs (pyproject.toml addopts -m "not e2e"); CI overrides with
# -m "" so both ci.yml's full suite and e2e-tests.yml's dedicated run
# still cover it.
pytestmark = pytest.mark.e2e

_USERNAME = 'e2eabrupt'
_PASSWORD = 'e2epass'


def test_abrupt_disconnect_saves_player(tmp_path):
    """Start server, log in, then close socket without sending 'bye'. Verify player JSON saved."""
    import net_common
    net_common.run_server_dir = str(tmp_path / 'run' / 'server')
    seed_test_account(_USERNAME, _PASSWORD)

    from simple_server import Server
    from player import Player

    server = Server('127.0.0.1', 0, 0)

    async def run_scenario():
        server_task = asyncio.create_task(server.start())
        # wait for server socket
        for _ in range(200):
            if getattr(server, 'server', None) and server.server.sockets:
                break
            await asyncio.sleep(0.01)
        port = server.server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        logged_in = await perform_login(reader, writer, _USERNAME, _PASSWORD)
        assert logged_in

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

    asyncio.run(asyncio.wait_for(run_scenario(), timeout=10))

    p = Player(name='probe', id=_USERNAME)
    path = p._json_path(_USERNAME)

    # wait up to 2s for file to appear
    deadline = time.time() + 2
    while time.time() < deadline and not os.path.exists(path):
        time.sleep(0.05)

    assert os.path.exists(path), f'Player file {path} not found after abrupt disconnect'

    with open(path, 'r') as f:
        data = json.load(f)

    # basic sanity: id/name present
    assert data.get('id') == _USERNAME or data.get('name') == _USERNAME

    # cleanup
    try:
        os.remove(path)
    except Exception:
        pass
