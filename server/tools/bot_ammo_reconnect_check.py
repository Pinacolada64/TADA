#!/usr/bin/env python3
"""tools/bot_ammo_reconnect_check.py — live check that loaded ammo
(player.ammo_rounds/ammo_max/ammo_damage) and an unused ammo box's own
item_flags both survive a real QUIT + reconnect cycle, not just an
in-session RELOAD.

Drives two separate connections to a running server (JSON protocol,
port 34083) as 'test' (see run/server/player-test.json -- carries a
CROSSBOW and two boxes of "bolts" ammo, added for this check: bolts is
weapons.json-catalog ammo for crossbow, rounds=4/damage=2).

Session A:
  1. READY crossbow.
  2. USE bolts -- loads player.ammo_rounds/max/damage, consumes one of
     the two stacked boxes (inventory.py's InventoryEntry stacking, so
     one box remains).
  3. STAT -- confirms "CROSSBOW 4/4 rounds" while readied.
  4. QUIT -- saves and disconnects for real (not just a RELOAD).

Session B (fresh connection):
  5. STAT -- readied_weapon is session-only (player.py's _SESSION_ONLY,
     an intentional SPUR-fidelity choice: you don't stay "readied"
     across a reconnect), so this should show "Weapon readied: None".
  6. READY crossbow again -- if ammo_rounds/max/damage genuinely
     persisted through the save/load round trip, STAT should now show
     the same "4/4 rounds" immediately, with no second USE needed.
  7. USE bolts (the box that was never touched in session A) -- confirms
     its own item_flags (rounds/damage/used_with) survived the round
     trip too, not just the player-level ammo counters.

Kept per this repo's convention (CLAUDE.md "Bot scripts") for future
regression checks once confirmed working.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot_client import _send, _recv, _print_exchange, _print_send

HOST, PORT = '127.0.0.1', 34083
USER, PASSWORD = 'test', 'test'


async def _handshake_plain(reader, writer) -> bool:
    server_init = await _recv(reader, timeout=5.0)
    if not server_init:
        print('No Init from server.')
        return False
    await _send(writer, {
        'server_id':  server_init.get('server_id',  'test_server'),
        'server_key': server_init.get('server_key', 'test_key'),
    })
    while True:
        msgs = []
        while True:
            msg = await _recv(reader, timeout=3.0)
            if msg is None:
                break
            msgs.append(msg)
            if msg.get('prompt'):
                break
        if not msgs:
            break
        _print_exchange('Setup', msgs)
        last_prompt = next((m.get('prompt', '') for m in reversed(msgs) if m.get('prompt')), '')
        if last_prompt == 'login> ':
            break
        if 'terminal type' in last_prompt.lower():
            await _send(writer, {'lines': ['P'], 'mode': 'login'})
    return True


async def _robust_recv(reader, writer, overall_timeout: float = 10.0) -> list[dict]:
    """Dismiss BOTH "-- More" and "-- End" pager pages -- see
    tools/bot_ally_wear_armor_check.py's docstring for why stopping on
    the first '>' without dismissing End eats the next command."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + overall_timeout
    all_msgs: list[dict] = []
    while loop.time() < deadline:
        msg = await _recv(reader, timeout=min(2.0, deadline - loop.time()))
        if msg is None:
            continue
        all_msgs.append(msg)
        prompt = msg.get('prompt') or ''
        if '-- more' in prompt.lower() or '-- end' in prompt.lower():
            await _send(writer, {'lines': [''], 'mode': 'game'})
            continue
        if '>' in prompt:
            break
    return all_msgs


async def step(reader, writer, cmd: str, mode: str = 'game', timeout: float = 8.0) -> str:
    _print_send(cmd)
    await _send(writer, {'lines': [cmd], 'mode': mode})
    msgs = await _robust_recv(reader, writer, overall_timeout=timeout)
    _print_exchange('Response', msgs)
    return '\n'.join(str(l) for m in msgs for l in (m.get('lines') or []))


def _flat(text: str) -> str:
    return ' '.join(text.split())


async def main() -> None:
    results: list[tuple[str, bool, str]] = []

    def check(label: str, ok: bool, detail: str = ''):
        results.append((label, ok, detail))
        print(f'  [{"PASS" if ok else "FAIL"}] {label}')

    # ---------------------------------------------------------------
    # Session A: load ammo, confirm it's live, then QUIT for real.
    # ---------------------------------------------------------------
    print('=== Session A: connect, ready, load ammo, QUIT ===')
    reader, writer = await asyncio.open_connection(HOST, PORT)
    if not await _handshake_plain(reader, writer):
        return
    await step(reader, writer, f'connect {USER} {PASSWORD}', mode='login', timeout=15.0)

    await step(reader, writer, 'ready crossbow')
    use_text = await step(reader, writer, 'use bolts')
    check('USE bolts loads 4 rounds', '4 ROUNDS NOW READY' in use_text.upper(), use_text)

    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('STAT shows loaded ammo before quit', 'CROSSBOW 4/4 rounds' in stat, stat)

    inv_text = _flat(await step(reader, writer, 'inv'))
    check('One box of bolts remains after one USE', 'bolts' in inv_text.lower(), inv_text)

    await step(reader, writer, 'quit')
    writer.close()
    await asyncio.sleep(1.0)   # let the server finish the save before reconnecting

    # ---------------------------------------------------------------
    # Session B: brand-new connection -- did it survive the round trip?
    # ---------------------------------------------------------------
    print('\n=== Session B: fresh connection after QUIT ===')
    reader, writer = await asyncio.open_connection(HOST, PORT)
    if not await _handshake_plain(reader, writer):
        return
    await step(reader, writer, f'connect {USER} {PASSWORD}', mode='login', timeout=15.0)

    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Weapon unreadied after reconnect (SPUR fidelity)', 'Weapon readied: None' in stat, stat)

    await step(reader, writer, 'ready crossbow')
    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Ammo counters survived QUIT/reconnect (4/4 rounds, no re-USE)',
          'CROSSBOW 4/4 rounds' in stat, stat)

    use_text = await step(reader, writer, 'use bolts')
    check("Remaining bolts box' own flags survived the round trip too",
          '4 ROUNDS NOW READY' in use_text.upper(), use_text)

    writer.close()

    print('\n=== Results ===')
    all_ok = all(ok for _, ok, _ in results)
    print('\nALL CHECKS PASSED' if all_ok else '\nSOME CHECKS FAILED -- see log above')


if __name__ == '__main__':
    asyncio.run(main())
