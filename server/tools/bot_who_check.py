#!/usr/bin/env python3
"""One-shot: connect as admin botdummy, run 'who', print it, disconnect.
Handles the timestamped prompt prefix and the post-login paginated news
screen ('-- End [n/n] [?=help] -->')."""
import asyncio, json

HOST, PORT = '127.0.0.1', 34083


async def _send(w, obj):
    w.write(json.dumps(obj).encode() + b'\n')
    await w.drain()


async def _recv(r, timeout=3.0):
    try:
        raw = await asyncio.wait_for(r.readline(), timeout=timeout)
        return json.loads(raw.strip()) if raw else None
    except (asyncio.TimeoutError, json.JSONDecodeError):
        return None


async def _recv_all(r, timeout=1.5):
    msgs = []
    while True:
        m = await _recv(r, timeout=timeout)
        if m is None:
            break
        msgs.append(m)
        if m.get('prompt'):
            break
    return msgs


def _last_prompt(msgs):
    return next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')


async def _advance_to(r, w, target, timeout=4.0):
    """Drain until a prompt ending with *target*, auto-dismissing pager
    prompts ('-->' / '[?=help]' / 'more') with Enter along the way."""
    allm = []
    while True:
        msgs = await _recv_all(r, timeout=timeout)
        if not msgs:
            break
        allm.extend(msgs)
        p = _last_prompt(msgs).rstrip()
        if p.endswith(target):
            break
        if p.endswith('-->') or '[?=help]' in p or 'more' in p.lower():
            await _send(w, {'lines': [''], 'mode': 'game'})
    return allm


def _dump(msgs):
    for m in msgs:
        ln = m.get('lines', [])
        for l in ([ln] if isinstance(ln, str) else ln):
            print(l)
        if m.get('prompt'):
            print(f'  [{m["prompt"]}]')


async def main():
    r, w = await asyncio.open_connection(HOST, PORT)
    init = await _recv(r, timeout=5.0)
    await _send(w, {'server_id': init.get('server_id', 'test_server'),
                    'server_key': init.get('server_key', 'test_key')})
    while True:
        msgs = await _recv_all(r, timeout=3.0)
        if not msgs:
            break
        last = _last_prompt(msgs).rstrip()
        if last.endswith('login> '):
            break
        if 'terminal type' in last.lower():
            await _send(w, {'lines': ['A'], 'mode': 'login'})

    await _send(w, {'lines': ['connect botdummy puppy123'], 'mode': 'login'})
    await _advance_to(r, w, 'main> ', timeout=6.0)

    await _send(w, {'lines': ['who'], 'mode': 'game'})
    print('===== who =====')
    _dump(await _advance_to(r, w, 'main> ', timeout=4.0))
    print('===============')

    await _send(w, {'lines': ['quit'], 'mode': 'game'})
    await _recv_all(r, timeout=2.0)
    w.close()


asyncio.run(main())
