#!/usr/bin/env python3
"""Two bots: create/login both, ready weapons, room A duels room B."""
import asyncio, json
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


async def _run_script(reader, writer, script, label):
    for cmd, mode in script:
        await _send(writer, {'lines': [cmd], 'mode': mode})
        msgs = await _recv_all(reader, timeout=4.0)
        print(f'[{label}] -> {cmd!r}')
        print(_flat(msgs))
        print()


async def main():
    stamp = datetime.now().strftime('%H%M%S')
    userA, userB = f'da{stamp}', f'db{stamp}'

    rA, wA = await asyncio.open_connection(HOST, PORT)
    await _handshake(rA, wA)
    rB, wB = await asyncio.open_connection(HOST, PORT)
    await _handshake(rB, wB)

    chargen = lambda name, user: [
        ('new', 'login'), (name, 'login'), (user, 'login'), ('', 'login'),
        ('m', 'login'), ('25', 'login'), ('t', 'login'),
        ('', 'login'), ('', 'login'),  # class list pagination
        ('3', 'login'),  # Fighter
        ('1', 'login'),  # Human
        ('c', 'login'),  # civilian guild
        ('y', 'login'),  # accept stats
        ('', 'login'),   # quote silent
        ('', 'login'), ('', 'login'),  # review pagination
        ('y', 'login'),  # accept
        ('hunter22', 'login'), ('hunter22', 'login'),
    ]

    await _run_script(rA, wA, chargen('Ardent', userA), 'A')
    await _run_script(rB, wB, chargen('Belwin', userB), 'B')

    # Both start in the same room (CREATION_ROOM) -- ready weapons, then duel.
    await _run_script(rA, wA, [('ready', 'game'), ('1', 'game')], 'A')
    await _run_script(rB, wB, [('ready', 'game'), ('1', 'game')], 'B')

    await _run_script(rA, wA, [('duel Belwin', 'game')], 'A')
    await _run_script(rB, wB, [('duel accept', 'game')], 'B')

    # Unprompted push to A announcing the duel has begun.
    msgs = await _recv_all(rA, timeout=3.0)
    print('[A] (post-accept push)')
    print(_flat(msgs))
    print()

    # Both sides just attack every round until someone wins.
    done = False
    for round_no in range(1, 21):
        await _send(wA, {'lines': ['duel attack'], 'mode': 'game'})
        msgs_a1 = await _recv_all(rA, timeout=3.0)
        print(f'[A] round {round_no} -> duel attack')
        print(_flat(msgs_a1))
        print()

        await _send(wB, {'lines': ['duel attack'], 'mode': 'game'})
        msgs_b = await _recv_all(rB, timeout=3.0)
        print(f'[B] round {round_no} -> duel attack')
        print(_flat(msgs_b))
        print()

        msgs_a2 = await _recv_all(rA, timeout=3.0)
        print(f'[A] round {round_no} (push)')
        print(_flat(msgs_a2))
        print()

        combined = _flat(msgs_b) + _flat(msgs_a2)
        if 'vanquished' in combined.lower() or 'flees' in combined.lower():
            done = True
            break

    print('DONE' if done else 'DID NOT FINISH')

    for w in (wA, wB):
        w.close()
    for w in (wA, wB):
        try:
            await w.wait_closed()
        except Exception:
            pass


if __name__ == '__main__':
    asyncio.run(main())
