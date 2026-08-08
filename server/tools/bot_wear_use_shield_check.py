#!/usr/bin/env python3
"""tools/bot_wear_use_shield_check.py — live check of WEAR/USE setting
active_armor_id/active_shield_id, and STAT showing the equipped item
names (2026-08-08 change).

Interactive exploration script -- prints raw server output at each step
so the exact editplayer prompt flow can be confirmed against the real
running server rather than assumed.
"""
import asyncio, json, sys

HOST = '127.0.0.1'
PORT = 34083
USER, PASSWORD = 'botdummy', 'puppy123'


async def _send(w, o):
    w.write(json.dumps(o).encode() + b'\n')
    await w.drain()


async def _recv(r, t=3.0):
    try:
        raw = await asyncio.wait_for(r.readline(), timeout=t)
        return json.loads(raw.strip()) if raw else None
    except asyncio.TimeoutError:
        return None


async def _recv_all(r, t=1.5):
    msgs = []
    while True:
        m = await _recv(r, t)
        if m is None:
            break
        msgs.append(m)
        lines = m.get('lines') or []
        if not lines and m.get('prompt'):
            break
    return msgs


def _print(msgs):
    for m in msgs:
        lines = m.get('lines', [])
        if isinstance(lines, str):
            lines = [lines]
        for l in lines:
            print(l)
        if m.get('prompt'):
            print(f'  [{m["prompt"]}]')


async def main():
    r, w = await asyncio.open_connection(HOST, PORT, limit=2 ** 20)
    init = await _recv(r, 5.0)
    await _send(w, {'server_id': init.get('server_id', 'test_server'),
                     'server_key': init.get('server_key', 'test_key')})
    while True:
        msgs = await _recv_all(r, 3.0)
        if not msgs:
            break
        last = next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')
        if last == 'login> ':
            break
        if 'terminal type' in last.lower():
            await _send(w, {'lines': ['A'], 'mode': 'login'})

    async def cmd(c, t=4.0, mode='game'):
        print(f"\n=== -> {c!r} ===")
        await _send(w, {'lines': [c], 'mode': mode})
        _print(await _recv_all(r, t))

    await cmd(f'connect {USER} {PASSWORD}', mode='login')

    steps = sys.argv[1:] if len(sys.argv) > 1 else ['inv', 'stat']
    for s in steps:
        await cmd(s)

    w.close()
    try:
        await w.wait_closed()
    except Exception:
        pass


asyncio.run(main())
