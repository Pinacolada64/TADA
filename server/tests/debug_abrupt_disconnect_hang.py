"""tests/debug_abrupt_disconnect_hang.py — manual repro script for the
test_abrupt_disconnect_saves_player() hang.

NOT a pytest test (deliberately not named test_*.py — pytest test collection
imports every test_*.py module, which would execute the asyncio.run() call
below as a side effect of collection and hang the whole suite). Run directly:

    python3 tests/debug_abrupt_disconnect_hang.py

Wraps each step of the scenario in asyncio.wait_for(..., timeout=N) with a
print after every await, so whichever step never completes shows up as the
last printed line instead of a silent, unlocalized hang.

Context: simple_server.Server.start() didn't expose a `self.server`
attribute, which several tests polled to discover the bound ephemeral port.
That's been fixed (see presence/simple_server commit history), but running
test_abrupt_disconnect.py afterward still hangs indefinitely -- this script
exists to find out exactly where, without leaving a zombie pytest process
bound to the fixed PETSCII port (kill it with `kill -9` if this script itself
is interrupted).
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    import net_common
    net_common.run_server_dir = '/tmp/debug_run'

    from simple_server import Server
    from simple_client import perform_handshake, send_message, receive_message
    from net_common import Message, Mode

    server = Server('127.0.0.1', 0)
    print("server constructed", flush=True)
    server_task = asyncio.create_task(server.start())
    for _ in range(200):
        if getattr(server, 'server', None) and server.server.sockets:
            break
        await asyncio.sleep(0.01)
    else:
        print("TIMED OUT waiting for server.server", flush=True)
        return
    port = server.server.sockets[0].getsockname()[1]
    print("bound port", port, flush=True)

    reader, writer = await asyncio.wait_for(asyncio.open_connection('127.0.0.1', port), timeout=5)
    print("connected", flush=True)
    await asyncio.wait_for(perform_handshake(reader, writer), timeout=5)
    print("handshake done", flush=True)
    await asyncio.wait_for(send_message(writer, Message(lines=['guest'], mode=Mode.login)), timeout=5)
    print("guest msg sent", flush=True)

    start = time.time()
    while time.time() - start < 3:
        msg = await asyncio.wait_for(receive_message(reader), timeout=3)
        print("got msg:", msg, flush=True)
        if not msg:
            break

    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass
    print("done", flush=True)


if __name__ == '__main__':
    asyncio.run(main())
