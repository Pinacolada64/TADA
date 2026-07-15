import asyncio
import json
import socket
import sys
import types
from pathlib import Path
import tempfile

# Prepare a temporary run dir and provide a minimal net_common + simple_client stub
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# This file has no test_* functions -- it's a standalone debug harness meant
# to be run directly (`python tests/test_e2e_network_quit.py`), not through
# pytest. But its filename matches pytest's test_*.py collection pattern, so
# pytest still imports it during collection. The stub setup below used to
# run at module level, which meant merely importing this file permanently
# overwrote sys.modules['net_common']/['simple_client'] with stubs lacking
# real functionality (e.g. net_common.user_dir()) for every other test in
# the same pytest session. Guarded behind a function now, only called from
# run_e2e_test()/__main__, so importing this module for collection is a no-op.

def _install_stubs():
    """Minimal net_common/simple_client stubs so Player._json_path finds our
    temp directory at runtime without pulling in the real modules."""
    net_common = types.ModuleType('net_common')
    net_common.run_server_dir = None  # will set later in test
    sys.modules['net_common'] = net_common

    simple_client = types.ModuleType('simple_client')
    async def send_message(writer, obj):
        return None
    simple_client.send_message = send_message
    sys.modules['simple_client'] = simple_client
    return net_common


async def server_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    # Very small server handler to emulate required server behavior for E2E test
    from player import Player
    addr = writer.get_extra_info('peername')
    try:
        # 1) Read initial handshake (a JSON line)
        data = await reader.readline()
        if not data:
            writer.close()
            await writer.wait_closed()
            return
        try:
            init = json.loads(data.decode('utf-8').strip())
        except Exception:
            init = None

        # Create a real Player tied to this connection
        p = Player(name='E2EPlayer')
        p.id = 'net-e2e-1'
        p.unsaved_changes = True

        # Wait for a command message from client
        data = await reader.readline()
        if data:
            try:
                msg = json.loads(data.decode('utf-8').strip())
            except Exception:
                msg = None

            # If client requested quit or sent mode 'bye', persist player and respond
            if msg and ((msg.get('type') == 'command' and msg.get('text') == 'quit') or msg.get('mode') == 'bye' or msg.get('text') == 'bye'):
                # Use player's quit() to force save
                try:
                    p.quit()
                except Exception:
                    p.save(force=True)
                # respond with goodbye
                resp = {'lines': ['Goodbye.'], 'mode': 'bye'}
                writer.write((json.dumps(resp) + '\n').encode('utf-8'))
                await writer.drain()
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


def run_e2e_test():
    net_common = _install_stubs()
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td) / 'run' / 'server'
        run_dir.mkdir(parents=True)
        # Point stub net_common to this run dir so Player._json_path writes here
        net_common.run_server_dir = run_dir

        # Start asyncio server
        async def run_server_and_client():
            server = await asyncio.start_server(server_handler, '127.0.0.1', 0)
            addr = server.sockets[0].getsockname()
            host, port = addr[0], addr[1]

            # Run client: connect, send handshake, send quit command
            reader, writer = await asyncio.open_connection(host, port)
            # send handshake
            handshake = {'mode': 'init', 'server_id': 'test', 'server_key': 'test', 'protocol_version': 1}
            writer.write((json.dumps(handshake) + '\n').encode('utf-8'))
            await writer.drain()

            # send quit command
            cmd = {'mode': 'app', 'type': 'command', 'text': 'quit'}
            writer.write((json.dumps(cmd) + '\n').encode('utf-8'))
            await writer.drain()

            # read response
            resp_line = await reader.readline()
            # close client socket
            writer.close()
            await writer.wait_closed()

            # allow server to handle closure briefly
            await asyncio.sleep(0.05)
            server.close()
            await server.wait_closed()

        asyncio.run(run_server_and_client())

        # Check that Player saved file exists
        expected = run_dir / 'player-net-e2e-1.json'
        print('Expected file:', expected)
        assert expected.exists(), f"Player file not created: {expected}"
        # Basic sanity of JSON
        with open(expected) as f:
            data = json.load(f)
        assert data.get('name') in ('E2EPlayer', 'E2EPlayer')


if __name__ == '__main__':
    run_e2e_test()

