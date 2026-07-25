#!/usr/bin/env python3
"""tools/bot_board_options_demo.py — Live smoke test for the BOARD
subsystem's Prompt Mode reader (commands/board_reply.py): posts a
thread, seeds a second message, then walks it interactively exercising
every end-of-message option -- '?' to show the menu, [L]ist to see the
thread's message index, jumping ahead, and [R]eplying with a quote
(including the quote-picker's own [L]ist lines option).

Run against the live server:
    python tools/bot_board_options_demo.py
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

    print('\n\n########## POSTING THE DEMO THREAD ##########')
    await _say(writer, reader, 'board post')
    await _say(writer, reader, 'Board Options Demo')  # title
    await _say(writer, reader, 'n')                     # anonymous? no
    await _say(writer, reader, 'First message in the demo thread.')
    await _say(writer, reader, '.s')

    # Find the new thread's id from the listing.
    listing = await _say(writer, reader, 'board')
    await _say(writer, reader, '')
    text = '\n'.join(str(l) for m in listing for l in (m.get('lines') or []))
    thread_id = None
    for line in text.splitlines():
        if 'Board Options Demo' in line:
            thread_id = line.strip().split('.')[0].strip()
            break
    print(f'\n>>> new thread id: {thread_id}')

    print('\n\n########## SEEDING A SECOND MESSAGE (flat reply) ##########')
    await _say(writer, reader, f'board reply {thread_id}')
    await _say(writer, reader, 'n')   # anonymous? no
    await _say(writer, reader, '')    # reply title -- blank keeps the default
    await _say(writer, reader, 'A simple reply, seeded before the interactive demo.')
    await _say(writer, reader, '.s')

    print('\n\n########## TOGGLING PROMPT MODE ON ##########')
    # 'pm' is a toggle -- don't assume which way it lands (a prior run
    # may have left it on already). Flip it, check which way it went,
    # flip again if needed so we're guaranteed On for the reader demo.
    msgs = await _say(writer, reader, 'pm')
    state_text = '\n'.join(str(l) for m in msgs for l in (m.get('lines') or []))
    if 'On.' not in state_text:
        await _say(writer, reader, 'pm')

    print('\n\n########## READING THE THREAD INTERACTIVELY ##########')
    await _say(writer, reader, f'board {thread_id}')

    print("\n=== root message shown -- typing '?' to recall the option list ===")
    await _say(writer, reader, '?')

    print("\n=== typing 'l' to list every message in the thread ===")
    await _say(writer, reader, 'l')

    print('\n=== Enter to advance to the reply ===')
    await _say(writer, reader, '')

    print("\n=== 'r' to reply with a quote ===")
    await _say(writer, reader, 'r')

    print("\n=== at the quote-range prompt, 'l' to list numbered lines ===")
    await _say(writer, reader, 'l')

    print('\n=== quoting line 1 ===')
    await _say(writer, reader, '1')
    await _say(writer, reader, 'y')   # confirm quote preview
    await _say(writer, reader, 'n')   # anonymous? no
    await _say(writer, reader, '')    # reply title -- blank keeps the default
    await _say(writer, reader, 'Nice quote-picker, by the way.')
    await _say(writer, reader, '.s')

    # The reader's own 'messages' list is fixed at however many replies
    # existed when 'board <id>' was first typed -- posting this reply
    # advances idx past that length, so the loop already exits back to
    # 'main' on its own. No extra blank Enter needed here.

    print('\n\n########## TOGGLING PROMPT MODE BACK OFF ##########')
    await _say(writer, reader, 'pm')

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
