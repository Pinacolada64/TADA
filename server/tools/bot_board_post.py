#!/usr/bin/env python3
"""tools/bot_board_post.py — Live smoke test for the BOARD command
(commands/board.py, the threaded message board): posts a new thread,
lists the board, and reads it back.

Run against the live server:
    python tools/bot_board_post.py
"""
import argparse
import asyncio
import json

from bot_credentials import load_password

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


async def _say(writer, reader, cmd, mode='game', timeout=4.0):
    print(f"\n=== -> {cmd!r} ===")
    await _send(writer, {'lines': [cmd], 'mode': mode})
    msgs = await _recv_all(reader, timeout=timeout)
    _print(msgs)
    while msgs and 'more' in (msgs[-1].get('prompt') or '').lower():
        await _send(writer, {'lines': ['Q'], 'mode': mode})
        more = await _recv_all(reader, timeout=timeout)
        _print(more)
        msgs += more
    return msgs


async def main(host: str, port: int, user: str, password: str) -> None:
    reader, writer = await asyncio.open_connection(host, port)
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

    await _say(writer, reader, f'connect {user} {password}', 'login')

    await _say(writer, reader, 'board post')
    await _say(writer, reader, 'Testing the threaded board')  # title
    await _say(writer, reader, 'n')                             # anonymous? no
    await _say(writer, reader, "Just kicking the tires on BOARD -- posting from a bot script.")
    await _say(writer, reader, '.s')                            # save

    print('\n\n########## BOARD LISTING ##########')
    await _say(writer, reader, 'board')
    await _say(writer, reader, '')  # leave listing

    print('\n\n########## READING THE NEW THREAD BACK ##########')
    msgs = await _say(writer, reader, 'board')
    # Find the newest thread's number from the listing and read it.
    listing_text = '\n'.join(str(l) for m in msgs for l in (m.get('lines') or []))
    await _say(writer, reader, '1')  # threads list newest-first in most boards; adjust if needed
    await _say(writer, reader, '')

    await _say(writer, reader, 'quit')
    await _say(writer, reader, 'Y')

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--user', default='botdummy')
    parser.add_argument('--password', default=None)
    args = parser.parse_args()
    password = args.password or load_password(args.user)
    asyncio.run(main(args.host, args.port, args.user, password))
