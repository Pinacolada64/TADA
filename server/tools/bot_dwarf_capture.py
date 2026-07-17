import asyncio, json, sys

HOST='127.0.0.1'; PORT=34083
OUT = open(sys.argv[1], 'w') if len(sys.argv) > 1 else sys.stdout

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
def _emit(msgs):
    for m in msgs:
        lines = m.get('lines', [])
        if isinstance(lines,str): lines=[lines]
        for l in lines: OUT.write(l + '\n')
        if m.get('prompt'): OUT.write(f'[{m["prompt"]}]\n')

async def main():
    r,w = await asyncio.open_connection(HOST,PORT)
    init = await _recv(r,5.0)
    await _send(w, {'server_id': init.get('server_id','test_server'), 'server_key': init.get('server_key','test_key')})
    while True:
        msgs = await _recv_all(r,3.0)
        if not msgs: break
        last = next((m.get('prompt','') for m in reversed(msgs) if m.get('prompt')), '')
        if last=='login> ': break
        if 'terminal type' in last.lower(): await _send(w, {'lines':['A'],'mode':'login'})
    await _send(w, {'lines':['connect botdummy puppy123'],'mode':'login'})
    await _recv_all(r,4.0)

    async def cmd(c, t=4.0):
        OUT.write(f'\n> {c}\n')
        await _send(w, {'lines':[c],'mode':'game'})
        _emit(await _recv_all(r,t))

    OUT.write('=== He is spotted ===\n')
    await cmd('look')

    OUT.write('\n=== First move: he robs your silver ===\n')
    await cmd('n')
    await cmd('s')

    OUT.write('\n=== Second move, no gold left: he takes an item instead ===\n')
    await cmd('n')
    await cmd('s')

    OUT.write('\n=== He is hunted down ===\n')
    await cmd('attack dwarf')
    for _ in range(15):
        await cmd('attack')

    OUT.write('\n=== Aftermath ===\n')
    await cmd('stats')

    w.close()
    try: await w.wait_closed()
    except Exception: pass
    OUT.flush()

asyncio.run(main())
