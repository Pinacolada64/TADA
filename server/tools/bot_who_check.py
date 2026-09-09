#!/usr/bin/env python3
"""tools/bot_who_check.py — connect as the admin bot account and run
'who', for the CLAUDE.md-mandated "show Ryan who's online before
restarting the server" check.

Doesn't reuse bot_client.py's own _handshake() -- that helper doesn't
dismiss a paginated pre-login banner ("-- More [n/m] --"), so it can
return before actually reaching the login prompt, desyncing every
command sent afterward (see CLAUDE.md's own note on this exact bug
class). This drains through terminal-type negotiation *and* pagination
before ever sending 'connect'.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot_client import _recv_all, _send

HOST = '127.0.0.1'
PORT = 34083
USER = 'botdummy'
PASSWORD = 'puppy123'


def _print(msgs):
    for m in msgs:
        lines = m.get('lines', [])
        if isinstance(lines, str):
            lines = [lines]
        for l in lines:
            print(l)


async def main():
    reader, writer = await asyncio.open_connection(HOST, PORT)

    init = await _recv_all(reader, timeout=5.0)
    if init:
        await _send(writer, {'server_id': init[0].get('server_id', 'test_server'),
                              'server_key': init[0].get('server_key', 'test_key')})

    # Drain setup: terminal-type prompt -> 'A'; any "More" pagination
    # (the pre-login banner) -> 'q' to skip straight to the login
    # prompt, rather than stepping through every page.
    while True:
        batch = await _recv_all(reader, timeout=3.0)
        if not batch:
            break
        last_p = next((m.get('prompt', '') for m in reversed(batch) if m.get('prompt')), '')
        if last_p == 'login> ':
            break
        if 'terminal type' in last_p.lower():
            await _send(writer, {'lines': ['A'], 'mode': 'login'})
        elif 'more' in last_p.lower():
            await _send(writer, {'lines': ['q'], 'mode': 'login'})

    await _send(writer, {'lines': [f'connect {USER} {PASSWORD}'], 'mode': 'login'})
    while True:
        batch = await _recv_all(reader, timeout=3.0)
        if not batch:
            break
        last_p = next((m.get('prompt', '') for m in reversed(batch) if m.get('prompt')), '')
        if last_p == 'main> ':
            break
        if 'more' in last_p.lower():
            await _send(writer, {'lines': ['q'], 'mode': 'game'})

    await _send(writer, {'lines': ['who'], 'mode': 'game'})
    msgs = []
    while True:
        batch = await _recv_all(reader, timeout=3.0)
        if not batch:
            break
        msgs.extend(batch)
        last_p = next((m.get('prompt', '') for m in reversed(batch) if m.get('prompt')), '')
        if last_p == 'main> ':
            break
        if 'more' in last_p.lower():
            await _send(writer, {'lines': ['q'], 'mode': 'game'})
    _print(msgs)

    await _send(writer, {'lines': ['quit'], 'mode': 'game'})
    await _recv_all(reader, timeout=2.0)

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


if __name__ == '__main__':
    asyncio.run(main())
