#!/usr/bin/env python3
"""tools/bot_text_editor_news.py — Live smoke test for text_editor.py wired
into commands/news.py, and for per-viewer re-rendering of a saved news
post's Justification/Border (formatting.py's serialize_lines()/
render_lines(), see news.py's module docstring).

Posts a news item with a centered line and a bordered line as the admin
'tester' account, reads it back at 80 columns, switches that same
session's screen width via PREFS to 30 columns, and reads it back again
-- confirming the box/centering re-renders narrower instead of staying
frozen at whatever width was active when it was saved.

Run against the text-editor-port worktree's own test server (NOT the
main checkout's server on the default port):
    python tools/bot_text_editor_news.py --port 34090
"""
import argparse
import asyncio
import json

HOST = '127.0.0.1'
PORT = 34090


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


async def _run_script(writer, reader, script):
    for cmd, mode in script:
        print(f"\n=== -> {cmd!r} ===")
        await _send(writer, {'lines': [cmd], 'mode': mode})
        msgs = await _recv_all(reader, timeout=4.0)
        # Dismiss any '-- More --' pagination prompts (e.g. PREFS' own
        # settings table at a narrow screen width) by jumping to the end,
        # so they don't eat the next scripted command as their answer.
        while msgs and 'more' in (msgs[-1].get('prompt') or '').lower():
            await _send(writer, {'lines': ['Q'], 'mode': mode})
            more_msgs = await _recv_all(reader, timeout=4.0)
            msgs += more_msgs
        _print(msgs)


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

    await _run_script(writer, reader, [
        (f'connect {user} {password}', 'login'),
        ('prefs', 'game'),
        ('m', 'game'),      # toggle More Prompt off -- keeps pagination
        ('', 'game'),       # out of the way at narrow screen widths
        ('prefs', 'game'),
        ('t', 'game'),
        ('5', 'game'),     # custom
        ('80', 'game'),    # columns
        ('24', 'game'),    # rows
        ('A', 'game'),     # ANSI
        ('', 'game'),      # exit prefs
    ])

    await _run_script(writer, reader, [
        ('news post', 'game'),
        ('Per-viewer rendering test', 'game'),   # title
        ('permanent', 'game'),                   # lifetime
        ('Plain top line.', 'game'),
        ('.j c', 'game'),                        # future lines centered
        ('This line is centered.', 'game'),
        ('.b', 'game'),                          # border the whole buffer
        ('.s', 'game'),                          # save
    ])

    print('\n\n########## READING BACK AT 80 COLUMNS ##########')
    await _run_script(writer, reader, [
        ('news', 'game'),
        ('1', 'game'),
        ('', 'game'),  # leave the listing
    ])

    await _run_script(writer, reader, [
        ('prefs', 'game'),
        ('t', 'game'),
        ('5', 'game'),
        ('30', 'game'),
        ('24', 'game'),
        ('A', 'game'),
        ('', 'game'),
    ])

    print('\n\n########## READING BACK AT 30 COLUMNS (same saved item) ##########')
    await _run_script(writer, reader, [
        ('news', 'game'),
        ('1', 'game'),
        ('', 'game'),
    ])

    await _run_script(writer, reader, [
        ('quit', 'game'),
        ('Y', 'game'),
    ])

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--user', default='tester')
    parser.add_argument('--password', default='puppy123')
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.user, args.password))
