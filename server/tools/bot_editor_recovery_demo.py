#!/usr/bin/env python3
"""tools/bot_editor_recovery_demo.py — Live smoke test for the
shutdown/disconnect editor-recovery feature (text_editor.py's
save_recovery_file()/find_recovery_file(), Server.graceful_shutdown(),
commands/edit.py's EditCommand).

Two phases against the real running server (default port 34083, same as
simple_server.py's live JSON port -- NOT a throwaway test server, since
this needs to actually trigger a real SHUTDOWN):

  --phase crash    Connection A (botdummy) starts 'news post', types a
                    title/lifetime/body line, but never saves. Connection
                    B (botlasso) issues 'shutdown #time now', which fires
                    Server.graceful_shutdown() and (per this feature)
                    should catch connection A's live editor buffer, save
                    it to a recovery file, and notify A before the
                    connection drops. This phase ends the live server
                    process -- restart it (see CLAUDE.md's screen restart
                    convention) before running --phase resume.

  --phase resume    Reconnect as botdummy. Login should show "you were
                    posting news ... (type 'edit' to resume)". Run 'edit',
                    confirm the resume prompt, and let it dispatch back
                    into news_store directly. Then 'news' to confirm the
                    item was actually posted (not just saved to a scratch
                    file), and that the recovery file is gone so it isn't
                    offered again.
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


def _print(tag, msgs):
    for m in msgs:
        lines = m.get('lines', [])
        if isinstance(lines, str):
            lines = [lines]
        for l in lines:
            print(f'[{tag}] {l}')
        if m.get('prompt'):
            print(f'[{tag}]   [{m["prompt"]}]')


async def _login(host, port, user, password):
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

    await _send(writer, {'lines': [f'connect {user} {password}'], 'mode': 'login'})
    msgs = await _recv_all(reader, timeout=4.0)
    _print(user, msgs)
    return reader, writer


async def _say(tag, writer, reader, cmd, mode='game', timeout=4.0):
    print(f"\n=== [{tag}] -> {cmd!r} ===")
    await _send(writer, {'lines': [cmd], 'mode': mode})
    msgs = await _recv_all(reader, timeout=timeout)
    _print(tag, msgs)
    return msgs


async def phase_crash(host, port):
    a_reader, a_writer = await _login(host, port, 'botdummy', load_password('botdummy'))
    b_reader, b_writer = await _login(host, port, 'botlasso', load_password('botlasso'))

    await _say('A', a_writer, a_reader, 'news post')
    await _say('A', a_writer, a_reader, 'Recovery Demo')          # title
    await _say('A', a_writer, a_reader, 'permanent')              # lifetime
    await _say('A', a_writer, a_reader, 'Testing crash recovery.')  # body line
    print("\n=== [A] deliberately NOT saving -- still mid-edit ===")

    print("\n=== [B] firing 'shutdown #time now' ===")
    await _send(b_writer, {'lines': ['shutdown #time now'], 'mode': 'game'})
    b_msgs = await _recv_all(b_reader, timeout=4.0)
    _print('B', b_msgs)

    print("\n=== [A] watching for the recovery notice before the connection drops ===")
    a_msgs = await _recv_all(a_reader, timeout=4.0)
    _print('A', a_msgs)
    got_notice = any('saved to a temporary file' in str(m).lower() for m in a_msgs)
    print(f'\n>>> recovery notice seen: {got_notice}')

    for w in (a_writer, b_writer):
        w.close()
        try:
            await w.wait_closed()
        except Exception:
            pass


async def phase_resume(host, port):
    reader, writer = await _login(host, port, 'botdummy', load_password('botdummy'))

    await _say('A', writer, reader, 'edit')
    await _say('A', writer, reader, 'y')  # confirm resume
    save_msgs = await _say('A', writer, reader, '.s')  # save -> dispatches back to news_store
    dispatched = any('news item' in str(m).lower() and 'posted' in str(m).lower()
                      for m in save_msgs)
    print(f'\n>>> dispatch-completion message seen: {dispatched}')

    msgs = await _say('A', writer, reader, 'news')
    listing = str(msgs).lower()
    print(f'\n>>> "recovery demo" appears in news listing: {"recovery demo" in listing}')

    await _say('A', writer, reader, '')  # leave listing
    await _say('A', writer, reader, 'quit')
    await _say('A', writer, reader, 'Y')

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


async def main(host, port, phase):
    if phase == 'crash':
        await phase_crash(host, port)
    else:
        await phase_resume(host, port)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--phase', choices=['crash', 'resume'], required=True)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.phase))
