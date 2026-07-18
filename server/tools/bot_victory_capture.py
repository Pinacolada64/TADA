import asyncio, json, sys

HOST='127.0.0.1'; PORT=34083
OUT = open(sys.argv[1], 'a') if len(sys.argv) > 1 else sys.stdout
STAGE = sys.argv[2] if len(sys.argv) > 2 else '1'

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

    async def cmd(c, t=4.0, label=None):
        OUT.write(f'\n> {c}\n')
        await _send(w, {'lines':[c],'mode':'game'})
        _emit(await _recv_all(r,t))

    if STAGE == '1':
        OUT.write('=== Attempt #1: Wraith King still alive ===\n')
        await cmd('look')
        await cmd('config victory_type gold')
        await cmd('config victory_gold_amount 100')
        await cmd('u')
    elif STAGE == '2':
        OUT.write('\n=== Attempt #2: Wraith King dead, victory_type=gold, silver in hand met ===\n')
        await cmd('u')
    elif STAGE == '3':
        OUT.write('\n=== Attempt #3: victory_type=item, item not carried ===\n')
        await cmd('config victory_type item')
        await cmd('config victory_item_number 35')
        await cmd('u')
    elif STAGE == '4':
        OUT.write('\n=== Attempt #4: victory_type=item, item carried ===\n')
        await cmd('u')

    w.close()
    try: await w.wait_closed()
    except Exception: pass
    OUT.flush()

asyncio.run(main())
