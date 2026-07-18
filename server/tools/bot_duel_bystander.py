#!/usr/bin/env python3
"""Three bots: two duel, one (botdummy) watches from the same room as a bystander."""
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
    userA, userB = f'wa{stamp}', f'wb{stamp}'

    rA, wA = await asyncio.open_connection(HOST, PORT)
    await _handshake(rA, wA)
    rB, wB = await asyncio.open_connection(HOST, PORT)
    await _handshake(rB, wB)
    rC, wC = await asyncio.open_connection(HOST, PORT)
    await _handshake(rC, wC)

    chargen = lambda name, user: [
        ('new', 'login'), (name, 'login'), (user, 'login'), ('', 'login'),
        ('m', 'login'), ('25', 'login'), ('t', 'login'),
        ('', 'login'), ('', 'login'),
        ('3', 'login'), ('1', 'login'), ('c', 'login'),
        ('y', 'login'), ('', 'login'), ('', 'login'), ('', 'login'),
        ('y', 'login'), ('hunter22', 'login'), ('hunter22', 'login'),
    ]

    userC = f'wc{stamp}'
    await _run_script(rA, wA, chargen('Warin', userA), 'A')
    await _run_script(rB, wB, chargen('Xanthe', userB), 'B')
    # Bystander: a third fresh character -- CREATION_ROOM (5) isn't a real
    # game_map room, so an admin TELEPORT can't reach it; a normal 'new'
    # character lands there the same way Warin/Xanthe just did.
    await _run_script(rC, wC, chargen('Yorick', userC), 'C')

    await _run_script(rA, wA, [('ready', 'game'), ('1', 'game')], 'A')
    await _run_script(rB, wB, [('ready', 'game'), ('1', 'game')], 'B')

    await _run_script(rA, wA, [('duel Xanthe', 'game')], 'A')

    print('--- C (bystander) drains after challenge ---')
    print(_flat(await _recv_all(rC, timeout=3.0)))
    print()

    await _run_script(rB, wB, [('duel accept', 'game')], 'B')
    await _recv_all(rA, timeout=3.0)  # drain A's push

    print('--- C (bystander) drains after accept ---')
    print(_flat(await _recv_all(rC, timeout=3.0)))
    print()

    for i in range(1, 6):
        await _send(wA, {'lines': ['duel attack'], 'mode': 'game'})
        msgs_a1 = await _recv_all(rA, timeout=3.0)
        print(f'[A] round {i} -> duel attack')
        print(_flat(msgs_a1))
        print()

        await _send(wB, {'lines': ['duel attack'], 'mode': 'game'})
        msgs_b = await _recv_all(rB, timeout=3.0)
        print(f'[B] round {i} -> duel attack')
        print(_flat(msgs_b))
        print()

        msgs_a2 = await _recv_all(rA, timeout=3.0)
        print(f'[A] round {i} (push)')
        print(_flat(msgs_a2))
        print()

        c_msgs = await _recv_all(rC, timeout=3.0)
        print(f'--- C (bystander) round {i} ---')
        print(_flat(c_msgs))
        print()

        if 'vanquished' in _flat(msgs_b).lower():
            break

    for w in (wA, wB, wC):
        w.close()
    for w in (wA, wB, wC):
        try:
            await w.wait_closed()
        except Exception:
            pass


if __name__ == '__main__':
    asyncio.run(main())
