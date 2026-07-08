"""commands/test_server.py

Standalone debug script for manually poking a running server on port 8888
(`python -m commands.test_server`) -- not a real Command class, despite
living in commands/. command_processor.discover('commands') imports every
.py file in this directory as a candidate command module; this file's
asyncio.run(test_guest()) used to sit at module level, so merely importing
it (discover() does exactly that) would either raise "asyncio.run() cannot
be called from a running event loop" (caught and logged, harmless -- the
common case, since discover() normally runs from within handle_connection's
already-running loop) or, if ever imported outside a running loop, actually
attempt a real, timeout-less connection to 127.0.0.1:8888 and hang forever
-- which happened intermittently in full pytest runs. Guarded behind
__main__ now so importing this module is always a no-op.
"""
import asyncio
from net_common import to_jsonb
async def test_guest():
    r,w = await asyncio.open_connection('127.0.0.1',8888)
    # read server init
    data = await r.readline()
    print('SERVER->', data.decode().strip())
    # send init matching server
    init = {'server_id':'test_server','server_key':'test_key','protocol_version':1,'translation':'petscii'}
    w.write(to_jsonb(init)+b'\n')
    await w.drain()
    # read handshake success
    data = await r.readline()
    print('SERVER->', data.decode().strip())
    # read login banner
    data = await r.readline()
    print('SERVER->', data.decode().strip())
    # send guest command
    msg = {'lines':['guest'], 'mode':'login'}
    w.write(to_jsonb(msg)+b'\n')
    await w.drain()
    print('sent guest')
    # read server responses
    for _ in range(6):
        d = await r.readline()
        if not d:
            print('server closed')
            break
        print('SERVER->', d.decode().strip())
    w.close(); await w.wait_closed()


if __name__ == '__main__':
    asyncio.run(test_guest())

