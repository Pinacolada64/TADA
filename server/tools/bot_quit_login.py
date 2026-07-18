#!/usr/bin/env python3
"""Verify 'quit' works at the bare login prompt (before connect/new)."""
import asyncio
import json

HOST = '127.0.0.1'
PORT = 34083


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

    async def send(obj):
        writer.write(json.dumps(obj).encode() + b'\n')
        await writer.drain()

    init = await _recv(reader, timeout=5.0)
    await send({'server_id': init.get('server_id', 'test_server'),
                'server_key': init.get('server_key', 'test_key')})
    while True:
        msgs = await _recv_all(reader, timeout=3.0)
        if not msgs:
            break
        _print(msgs)
        last = next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')
        if last == 'login> ':
            break
        if 'terminal type' in last.lower():
            await send({'lines': ['A'], 'mode': 'login'})

    print("\n=== -> 'quit' (at bare login prompt) ===")
    await send({'lines': ['quit'], 'mode': 'login'})
    msgs = await _recv_all(reader, timeout=4.0)
    _print(msgs)

    # Confirm the socket is actually closed now (EOF).
    print("\n=== checking for EOF ===")
    raw = await asyncio.wait_for(reader.readline(), timeout=3.0)
    print('EOF (connection closed)' if not raw else f'unexpected data: {raw}')

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


if __name__ == '__main__':
    asyncio.run(main())
