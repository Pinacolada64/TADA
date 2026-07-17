#!/usr/bin/env python3
"""Scripted bot demonstrating today's quit/resume character-creation work:

  Session 1: connects, starts 'new', hits 'quit' at Preferences (demonstrates
             the (A)bandon/(R)esume/(C)ontinue confirmation), chooses
             (C)ontinue, keeps going, then hits 'quit' again at the stat-roll
             step and chooses (R)esume later -- persists progress and
             disconnects.
  Session 2: reconnects, logs in with the same username/password, gets
             "Welcome back!" and resumes exactly at the stat-roll step,
             finishes creation normally, then quits the character/game.
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
    """Drain until the real blocking prompt (an empty-lines message that
    also carries a prompt) is reached -- see bot_new_character.py's note
    on why a naive 'any truthy prompt field' check stops one message too
    early (ordinary ctx.send() calls carry a stale leftover prompt too)."""
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


async def run_script(script: list[tuple[str, str]], label: str) -> None:
    print(f'\n{"#" * WIDTH}\n#  {label}\n{"#" * WIDTH}')
    reader, writer = await asyncio.open_connection(HOST, PORT)
    await _handshake(reader, writer)

    mode = 'login'
    for cmd, mode in script:
        print(f'\n{"=" * WIDTH}\n  -> {cmd!r}\n{"=" * WIDTH}')
        await _send(writer, {'lines': [cmd], 'mode': mode})
        msgs = await _recv_all(reader, timeout=4.0)
        _print_exchange(msgs)

    print(f'\n{"=" * WIDTH}\n  -> (draining trailing output)\n{"=" * WIDTH}')
    msgs = await _recv_all(reader, timeout=3.0)
    _print_exchange(msgs)

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


async def main() -> None:
    stamp = datetime.now().strftime('%H%M%S')
    user = f'quitbot{stamp}'
    pw   = 'hunter2'

    # --- Session 1: quit-and-continue, then quit-and-resume ---
    session1 = [
        ('new',  'login'),
        ('Wrenna', 'login'),      # name
        (user,   'login'),        # username
        ('quit', 'login'),        # typo'd quit at Preferences
        ('C',    'login'),        # continue -- keep going
        ('',     'login'),        # prefs: accept defaults
        ('m',    'login'),        # gender
        ('25',   'login'),        # age
        ('t',    'login'),        # birthday: today
        ('4',    'login'),        # client: TADA
        ('',     'login'),        # class list pagination page 1
        ('',     'login'),        # class list pagination page 2/end
        ('1',    'login'),        # class: Wizard
        ('1',    'login'),        # race: Human
        ('c',    'login'),        # guild: Civilian
        ('quit', 'login'),        # quit at stat-roll this time
        ('R',    'login'),        # resume later
        (pw,     'login'),        # password (needed to persist+resume)
        (pw,     'login'),        # confirm password
    ]
    await run_script(session1, 'SESSION 1 -- quit/continue, then quit/resume-later')

    await asyncio.sleep(0.3)

    # --- Session 2: reconnect, resume, finish ---
    session2 = [
        (f'connect {user} {pw}', 'login'),
        ('y',    'login'),        # accept rolled stats (resumed right here)
        ('',     'login'),        # quote: silent
        ('',     'login'),        # review summary pagination page 1
        ('',     'login'),        # review summary pagination page 2/end
        ('y',    'login'),        # accept review
        (pw,     'login'),        # password (re-asked at the true end -- harmless)
        (pw,     'login'),        # confirm password
    ]
    await run_script(session2, 'SESSION 2 -- reconnect and resume')

    # --- Session 2 continued: quit the finished character cleanly ---
    session3 = [
        (f'connect {user} {pw}', 'login'),
        ('quit', 'game'),
        ('Y',    'game'),
    ]
    await run_script(session3, 'SESSION 3 -- log back in as the finished character, quit')


if __name__ == '__main__':
    asyncio.run(main())
