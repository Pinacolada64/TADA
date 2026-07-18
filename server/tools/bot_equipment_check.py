#!/usr/bin/env python3
"""Live check: starting equipment (shield/armor/weapon) + stats display."""
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
    reader, writer = await asyncio.open_connection(HOST, PORT)
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

    stamp = datetime.now().strftime('%H%M%S')
    user = f'ebot{stamp}'
    script = [
        ('new', 'login'),
        ('Ironclad', 'login'),   # name
        (user, 'login'),         # username
        ('', 'login'),           # prefs: accept
        ('m', 'login'),          # gender
        ('30', 'login'),         # age
        ('t', 'login'),          # birthday
        ('', 'login'),           # class list pagination page 1
        ('', 'login'),           # class list pagination page 2/end
        ('3', 'login'),          # class: Fighter
        ('1', 'login'),          # race: Human
        ('c', 'login'),          # guild
        ('y', 'login'),          # accept rolled stats
        ('', 'login'),           # quote: blank/silent
        ('', 'login'),           # final review pagination page 1
        ('', 'login'),           # final review pagination page 2/end
        ('y', 'login'),          # final review: accept
        ('hunter22', 'login'),   # password
        ('hunter22', 'login'),   # confirm password
    ]
    for cmd, mode in script:
        print(f"\n=== -> {cmd!r} ===")
        await _send(writer, {'lines': [cmd], 'mode': mode})
        msgs = await _recv_all(reader, timeout=4.0)
        _print(msgs)

    print("\n=== -> 'stats' ===")
    await _send(writer, {'lines': ['stats'], 'mode': 'game'})
    msgs = await _recv_all(reader, timeout=4.0)
    _print(msgs)

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


if __name__ == '__main__':
    asyncio.run(main())
