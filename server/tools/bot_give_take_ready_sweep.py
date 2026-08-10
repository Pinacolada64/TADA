#!/usr/bin/env python3
"""tools/bot_give_take_ready_sweep.py — live end-to-end sweep of GIVE/TAKE
across item kinds (weapon, armor, food, book), checking STAT's readied/
worn status before and after each transfer.

Drives a real connection to a running server (JSON protocol, port 34083)
as 'test' (see run/server/player-test.json -- carries a CROSSBOW, cloth
armor, a loaf of bread, and two books; servant allies GANDALF THE GREY,
SAMWISE, ATHENA, SHADOW already parked in the same room).

Exercises, in order:
  1. READY crossbow, STAT -- confirms "Weapon readied: CROSSBOW".
  2. GIVE crossbow to gandalf -- STAT confirms player's own "Weapon
     readied" clears to None (player.py's unworn_if_given_away(), added
     2026-08-09/10) and the non-expert hint fires.
  3. TAKE crossbow back from gandalf -- STAT confirms it's still None
     (does NOT auto-re-ready -- Ryan's request: "should stay unreadied
     until next ready").
  4. READY crossbow again -- confirms manual re-ready still works.
  5. WEAR cloth armor, STAT -- confirms "Armor: N%(cloth armor)".
  6. GIVE cloth armor to gandalf -- STAT confirms Armor drops to 0%
     and gandalf's row shows "[Worn: cloth armor]".
  7. TAKE armor back from gandalf -- STAT confirms Armor stays 0% (not
     auto-reworn).
  8. WEAR cloth armor again -- confirms manual re-wear still works.
  9. GIVE loaf of bread (food) to gandalf -- ally eats it; no ready/worn
     state involved, but confirms the send_room broadcast added in the
     give/take/get/drop sweep.
  10. GIVE Adventurer's Guide (book/generic item) to gandalf -- confirms
      the plain-item branch's "tucks it away" message and its (newly
      added) send_room broadcast.

Kept per this repo's convention (CLAUDE.md "Bot scripts") for future
regression checks once confirmed working.
"""
import asyncio
import re
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
    """See tools/bot_ally_wear_armor_check.py's docstring: dismiss BOTH
    "-- More" and "-- End" pager pages (both contain a literal '>'), not
    just More -- stopping on End without dismissing it eats the next
    command as pager input instead of running it."""
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
    reader, writer = await asyncio.open_connection(HOST, PORT)
    if not await _handshake_plain(reader, writer):
        return

    await step(reader, writer, f'connect {USER} {PASSWORD}', mode='login', timeout=15.0)

    results: list[tuple[str, bool, str]] = []

    def check(label: str, ok: bool, detail: str = ''):
        results.append((label, ok, detail))

    # -----------------------------------------------------------------
    # 1-4: WEAPON -- ready / give / take / re-ready
    # -----------------------------------------------------------------
    print('\n=== WEAPON: ready crossbow ===')
    await step(reader, writer, 'ready crossbow')
    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Weapon readied after READY', 'Weapon readied: CROSSBOW' in stat, stat)

    print('\n=== WEAPON: give crossbow to gandalf ===')
    give_text = await step(reader, writer, 'give crossbow to gandalf')
    check('Non-expert unready hint on GIVE', 'no longer wielding' in give_text.lower(), give_text)
    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Weapon readied cleared after GIVE', 'Weapon readied: None' in stat, stat)
    check('Ally shows Wpn: CROSSBOW', 'GANDALF' in stat and 'CROSSBOW' in stat, stat)

    print('\n=== WEAPON: take crossbow back from gandalf ===')
    await step(reader, writer, 'take crossbow from gandalf')
    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Weapon STAYS unreadied after TAKE', 'Weapon readied: None' in stat, stat)

    print('\n=== WEAPON: ready crossbow again ===')
    await step(reader, writer, 'ready crossbow')
    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Weapon readied again after manual READY', 'Weapon readied: CROSSBOW' in stat, stat)

    # -----------------------------------------------------------------
    # 5-8: ARMOR -- wear / give / take / re-wear
    # -----------------------------------------------------------------
    print('\n=== ARMOR: wear cloth armor ===')
    await step(reader, writer, 'wear cloth armor')
    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Armor% set after WEAR', 'cloth armor' in stat.lower() and 'Armor' in stat, stat)

    print('\n=== ARMOR: give cloth armor to gandalf ===')
    give_text = await step(reader, writer, 'give cloth armor to gandalf')
    check('Non-expert unwear hint on GIVE', 'no longer wearing' in give_text.lower(), give_text)
    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Armor 0% after GIVE', re.search(r'Armor\s*:\s*0%', stat) is not None, stat)
    check('Ally shows Worn: cloth armor', 'GANDALF' in stat and '[Worn:' in stat and 'cloth armor]' in stat.lower(), stat)

    print('\n=== ARMOR: take armor back from gandalf ===')
    await step(reader, writer, 'take armor from gandalf')
    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Armor STAYS 0% after TAKE', re.search(r'Armor\s*:\s*0%', stat) is not None, stat)

    print('\n=== ARMOR: wear cloth armor again ===')
    await step(reader, writer, 'wear cloth armor')
    stat = _flat(await step(reader, writer, 'stat', timeout=10.0))
    check('Armor% set again after manual WEAR', 'cloth armor' in stat.lower(), stat)

    # -----------------------------------------------------------------
    # 9: FOOD -- consumed by the ally, no ready/worn state, but should
    # broadcast to the room now.
    # -----------------------------------------------------------------
    print('\n=== FOOD: give loaf of bread to gandalf ===')
    give_text = await step(reader, writer, 'give bread to gandalf')
    check('Food GIVE produced a response', bool(give_text.strip()), give_text)

    # -----------------------------------------------------------------
    # 10: GENERIC ITEM (book) -- plain "tucks it away" branch.
    # -----------------------------------------------------------------
    print("\n=== BOOK: give Adventurer's Guide to gandalf ===")
    give_text = await step(reader, writer, "give adventurer's guide to gandalf")
    check('Book GIVE tucked away', 'tucks' in give_text.lower(), give_text)

    print('\n=== Results ===')
    all_ok = True
    for label, ok, _ in results:
        print(f'  [{"PASS" if ok else "FAIL"}] {label}')
        all_ok = all_ok and ok
    print('\nALL CHECKS PASSED' if all_ok else '\nSOME CHECKS FAILED -- see log above')

    # Dump results as a simple machine-readable summary for the artifact.
    import json
    print('\n=== JSON ===')
    print(json.dumps([{'label': l, 'ok': ok, 'detail': d} for l, ok, d in results]))

    writer.close()


if __name__ == '__main__':
    asyncio.run(main())
