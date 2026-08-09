#!/usr/bin/env python3
"""tools/bot_editplayer_saddlebags_check.py — live check of the two
saddlebags fixes (2026-08-08):

  1. editplayer's [T]ransfer used to refuse to move the saddlebags item
     itself onto a mount ("has nowhere to carry it -- needs saddlebags
     first"), since a mount always has zero carrying capacity until it
     already has saddlebags. Transferring the bags themselves must now
     equip AllyFlags.SADDLEBAGS instead of hitting that capacity check.
  2. LOOK <mount> now reports saddlebags status plus a thin/fat build
     based on pack fullness.

Interactive exploration script -- prints raw server output at each step
so the exact editplayer prompt flow and LOOK text are confirmed against
the real running server rather than assumed.

Run against a disposable instance, e.g.:
    .venv/bin/python simple_server.py --port 34093 --petscii-port 34094 &
    .venv/bin/python tools/bot_editplayer_saddlebags_check.py
"""
import asyncio, json, sys

HOST = '127.0.0.1'
PORT = 34093
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
        msgs = await _recv_all(r, t)
        _print(msgs)
        text = '\n'.join(
            (l if isinstance(l, str) else '')
            for m in msgs
            for l in (m.get('lines') or ([m['lines']] if isinstance(m.get('lines'), str) else []))
        )
        return text

    await cmd(f'connect {USER} {PASSWORD}', mode='login')

    # --- editplayer: Character Names -> Horse -> Remove any existing
    # horse (fresh start -- a re-run of this script previously left a
    # horse with SADDLEBAGS already equipped) -> Add a fresh one ---
    await cmd('editplayer')
    await cmd('cn')
    cn_text = await cmd('h')
    if 'No horse owned' not in cn_text:
        await cmd('r')          # [R]emove horse
        await cmd('h')          # back into the now-empty horse prompt
    await cmd('a')               # [A]dd a horse
    name_text = await cmd('R')   # random name -- lands back on Character Names menu
    import re
    m = re.search(r'Random name chosen: (\S+)', name_text)
    horse_name = m.group(1) if m else 'HONEY'
    print(f'\n*** horse name: {horse_name} ***')
    await cmd('')             # back out of names submenu to Player Editor main menu

    # --- Inventory: give saddlebags to self ---
    await cmd('in')
    await cmd('o')           # [O]bject
    await cmd('saddlebags')  # search term -- single match, skips straight to recipient prompt
    await cmd('0')            # recipient: 0 = yourself
    await cmd('')            # quit inventory menu
    await cmd('')            # quit editplayer

    # --- LOOK before equipping: expect "has no saddlebags" ---
    await cmd(f'look {horse_name}')

    # --- editplayer again: Transfer the saddlebags to the horse ---
    await cmd('editplayer')
    await cmd('in')
    await cmd('t')           # [T]ransfer
    await cmd('1')           # item #1 (the saddlebags just given)
    await cmd('1')           # recipient: ally #1 (the mount)
    await cmd('y')           # confirm -- this used to fail with
                              # "has nowhere to carry it -- needs saddlebags first"
    await cmd('')            # quit inventory menu
    await cmd('')            # quit editplayer

    # --- LOOK at the mount: should now show saddlebags + thin build ---
    await cmd(f'look {horse_name}')

    w.close()
    try:
        await w.wait_closed()
    except Exception:
        pass


asyncio.run(main())
