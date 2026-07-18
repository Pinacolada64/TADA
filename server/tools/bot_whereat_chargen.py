#!/usr/bin/env python3
"""Live check: does WHEREAT show 'Creating a character' for someone mid-chargen?"""
import asyncio
import json
from datetime import datetime

HOST = '127.0.0.1'
PORT = 34083


async def _send(writer, obj):
    writer.write(json.dumps(obj).encode() + b'\n')
    await writer.drain()


async def _recv(reader, timeout=3.0):
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not raw:
            return None
        return json.loads(raw.strip())
    except asyncio.TimeoutError:
        return None


async def _recv_all(reader, timeout=1.5):
    msgs = []
    while True:
        msg = await _recv(reader, timeout=timeout)
        if msg is None:
            break
        msgs.append(msg)
        lines = msg.get('lines') or []
        if not lines and msg.get('prompt'):
            break
    return msgs


def _flat(msgs):
    out = []
    for m in msgs:
        lines = m.get('lines', [])
        if isinstance(lines, str):
            lines = [lines]
        out.extend(lines)
    return '\n'.join(out)


async def _handshake(reader, writer):
    init = await _recv(reader, timeout=5.0)
    await _send(writer, {'server_id': init.get('server_id', 'test_server'),
                          'server_key': init.get('server_key', 'test_key')})
    while True:
        msgs = await _recv_all(reader, timeout=3.0)
        if not msgs:
            break
        last = next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')
        if last == 'login> ':
            break
        if 'terminal type' in last.lower():
            await _send(writer, {'lines': ['A'], 'mode': 'login'})


async def main():
    # Bot 1: start creating a character, stop partway through (mid Class step)
    r1, w1 = await asyncio.open_connection(HOST, PORT)
    await _handshake(r1, w1)

    stamp = datetime.now().strftime('%H%M%S')
    user = f'vbot{stamp}'
    chargen_script = [
        ('new', 'login'),
        ('Loiterer', 'login'),
        (user, 'login'),
        ('', 'login'),   # prefs accept
        ('m', 'login'),  # gender
        ('25', 'login'), # age
        ('t', 'login'),  # birthday -> now sitting at Class step prompt
    ]
    for cmd, mode in chargen_script:
        await _send(w1, {'lines': [cmd], 'mode': mode})
        await _recv_all(r1, timeout=4.0)

    # Bot 2: admin login, check WHEREAT while bot 1 is still mid-chargen
    r2, w2 = await asyncio.open_connection(HOST, PORT)
    await _handshake(r2, w2)
    await _send(w2, {'lines': ['connect botdummy puppy123'], 'mode': 'login'})
    await _recv_all(r2, timeout=4.0)

    await _send(w2, {'lines': ['whereat'], 'mode': 'game'})
    msgs = await _recv_all(r2, timeout=4.0)
    out = _flat(msgs)
    print(out)
    print('\n--- CHECK ---')
    print('Loiterer shown:', 'Loiterer' in out)
    print("'Creating a character' shown:", 'Creating a character' in out)

    for w in (w1, w2):
        w.close()
    for w in (w1, w2):
        try:
            await w.wait_closed()
        except Exception:
            pass


if __name__ == '__main__':
    asyncio.run(main())
