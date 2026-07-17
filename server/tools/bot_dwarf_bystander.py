import asyncio, json

HOST='127.0.0.1'; PORT=34083

async def _send(w,o): w.write(json.dumps(o).encode()+b'\n'); await w.drain()
async def _recv(r,t=3.0):
    try:
        raw = await asyncio.wait_for(r.readline(), timeout=t)
        return json.loads(raw.strip()) if raw else None
    except asyncio.TimeoutError:
        return None
async def _recv_all(r,t=1.5):
    msgs=[]
    while True:
        m = await _recv(r,t)
        if m is None: break
        msgs.append(m)
        lines = m.get('lines') or []
        if not lines and m.get('prompt'): break
    return msgs
def _print(tag, msgs):
    for m in msgs:
        lines = m.get('lines', [])
        if isinstance(lines,str): lines=[lines]
        for l in lines: print(f'[{tag}] {l}')
        if m.get('prompt'): print(f'[{tag}]   [{m["prompt"]}]')

async def login(name, password):
    r,w = await asyncio.open_connection(HOST,PORT)
    init = await _recv(r,5.0)
    await _send(w, {'server_id': init.get('server_id','test_server'), 'server_key': init.get('server_key','test_key')})
    while True:
        msgs = await _recv_all(r,3.0)
        if not msgs: break
        last = next((m.get('prompt','') for m in reversed(msgs) if m.get('prompt')), '')
        if last=='login> ': break
        if 'terminal type' in last.lower(): await _send(w, {'lines':['A'],'mode':'login'})
    await _send(w, {'lines':[f'connect {name} {password}'],'mode':'login'})
    await _recv_all(r,4.0)
    return r, w

async def main():
    r1, w1 = await login('botdummy', 'puppy123')
    r2, w2 = await login('botlasso', 'puppy123')

    # Drain botlasso's own login/room-entry noise first.
    await _recv_all(r2, 2.0)

    print('=== botdummy moves (both should see the theft) ===')
    await _send(w1, {'lines':['e'], 'mode':'game'})
    m1 = await _recv_all(r1, 4.0)
    m2 = await _recv_all(r2, 3.0)
    _print('botdummy (actor)', m1)
    _print('botlasso (bystander)', m2)

    w1.close(); w2.close()
    try:
        await w1.wait_closed()
        await w2.wait_closed()
    except Exception:
        pass

asyncio.run(main())
