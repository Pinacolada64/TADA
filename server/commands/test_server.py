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
asyncio.run(test_guest())

