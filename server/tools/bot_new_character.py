#!/usr/bin/env python3
"""Scripted bot that drives a full 'new' character creation session over
the wire, to visually verify the 4d6-drop-lowest explanation and the
race/class bonus report added to commands/new_player.py's _roll_stats().

Reuses the same handshake/wire helpers as bot_client.py.
"""
import asyncio
import json
import sys
import textwrap
from datetime import datetime

HOST  = '127.0.0.1'
PORT  = 34083
WIDTH = 80


async def _send(writer, obj: dict) -> None:
    writer.write(json.dumps(obj).encode() + b'\n')
    await writer.drain()


async def _recv(reader, timeout: float = 3.0) -> dict | None:
    try:
        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not raw:
            return None
        return json.loads(raw.strip())
    except asyncio.TimeoutError:
        return None


async def _recv_all(reader, timeout: float = 1.5) -> list[dict]:
    """Drain messages until the server's actual blocking read is reached.

    GameContext.prompt() sends preamble text as an ordinary ctx.send()
    (lines=[...], with a *stale* leftover prompt field from ctx.set_prompt())
    followed by a SEPARATE message that is the real blocking prompt:
    lines=[] with the live prompt text. Stopping on any truthy 'prompt'
    (as bot_client.py does) stops one message too early, since ordinary
    sends carry a nonempty prompt field too -- only an *empty-lines*
    message marks the actual wait-for-input point.
    """
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


def _print_exchange(msgs: list[dict]) -> None:
    for msg in msgs:
        lines = msg.get('lines', [])
        if isinstance(lines, str):
            lines = [lines]
        for line in lines:
            if line:
                for w in textwrap.wrap(line, WIDTH) or [line]:
                    print(f'  {w}')
            else:
                print()
        prompt = msg.get('prompt', '')
        if prompt:
            print(f'  [{prompt}]')


async def _handshake(reader, writer) -> None:
    server_init = await _recv(reader, timeout=5.0)
    await _send(writer, {
        'server_id':  server_init.get('server_id',  'test_server'),
        'server_key': server_init.get('server_key', 'test_key'),
    })
    while True:
        msgs = await _recv_all(reader, timeout=3.0)
        if not msgs:
            break
        last_prompt = next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')
        if last_prompt == 'login> ':
            break
        if 'terminal type' in last_prompt.lower():
            await _send(writer, {'lines': ['A'], 'mode': 'login'})


async def main() -> None:
    reader, writer = await asyncio.open_connection(HOST, PORT)
    await _handshake(reader, writer)

    stamp = datetime.now().strftime('%H%M%S')
    name_hint = f'bot{stamp}'

    script = [
        ('new', 'login'),
        ('',    'login'),   # exit prefs menu
        ('4',   'login'),   # client type: TADA Client
        ('25',  'login'),   # age
        ('T',   'login'),   # birthday: today
        ('M',   'login'),   # gender
        ('R',   'login'),   # random name
        ('y',   'login'),   # accept random name
        ('',    'login'),   # class list pagination page 1
        ('',    'login'),   # class list pagination page 2/end
        ('1',   'login'),   # class: Wizard
        ('1',   'login'),   # race: Human (valid w/ Wizard)
        ('C',   'login'),   # guild: Civilian
        ('y',   'login'),   # >>> ACCEPT ROLLED STATS <<<
        ('',    'login'),   # quote: silent
        ('',    'login'),   # final review summary pagination page 1
        ('',    'login'),   # final review summary pagination page 2/end
        ('',    'login'),   # final review: accept
        ('',    'login'),   # username: accept default
        ('R',   'login'),   # password: random
        ('y',   'login'),   # accept random password
    ]

    mode = 'login'
    for cmd, mode in script:
        print(f'\n{"=" * WIDTH}\n  -> {cmd!r}\n{"=" * WIDTH}')
        await _send(writer, {'lines': [cmd], 'mode': mode})
        msgs = await _recv_all(reader, timeout=4.0)
        _print_exchange(msgs)

    # Drain anything else (welcome message, room description, 'main> ')
    print(f'\n{"=" * WIDTH}\n  -> (draining post-creation output)\n{"=" * WIDTH}')
    msgs = await _recv_all(reader, timeout=4.0)
    _print_exchange(msgs)

    # Clean up: quit so the account doesn't linger connected.
    print(f'\n{"=" * WIDTH}\n  -> quit\n{"=" * WIDTH}')
    await _send(writer, {'lines': ['quit'], 'mode': 'game'})
    msgs = await _recv_all(reader, timeout=4.0)
    _print_exchange(msgs)
    if any('leave' in (m.get('prompt') or '').lower() for m in msgs):
        await _send(writer, {'lines': ['Y'], 'mode': 'game'})
        msgs = await _recv_all(reader, timeout=4.0)
        _print_exchange(msgs)

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


if __name__ == '__main__':
    asyncio.run(main())
