#!/usr/bin/env python3
"""tools/bot_quiver_check.py — live end-to-end check of the new Quiver
ammo carrier at Olly's (objects.json #167, shoppe/ollys.py's
_CARRIER_RANGE; see MECHANICS.md's "Quiver (TADA addition)" entry).

Drives a real connection to a running server (JSON protocol, port
34083) as botdummy: reloads the affected module, funds the character
via editplayer's Money menu, buys a LONG BOW and readies it, then walks
the quiver lifecycle at Olly's -- same pattern as
tools/bot_ammo_carrier_check.py, just for the bow instead of the musket:

  1. Buy a quiver (carrier) -- must arrive full (10 arrows) and refuse a
     second purchase of the same type.
  2. USE the quiver -- rounds load into the bow, quiver stays in the
     pack, now empty.
  3. Buy raw arrows matching the now-empty quiver -- must top it back
     off instead of sitting as its own stack.
  4. INV at each step to confirm the "[N rounds xM]" / "[cur/cap
     rounds]" display.

Kept per this repo's convention (CLAUDE.md "Bot scripts") for future
regression checks.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot_client import _handshake, _send, _recv, _print_exchange, _print_send

HOST, PORT = '127.0.0.1', 34083
USER, PASSWORD = 'botdummy', 'puppy123'


async def _robust_recv(reader, overall_timeout: float = 10.0) -> list[dict]:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + overall_timeout
    all_msgs: list[dict] = []
    while loop.time() < deadline:
        msg = await _recv(reader, timeout=min(2.0, deadline - loop.time()))
        if msg is None:
            continue
        all_msgs.append(msg)
        if '>' in (msg.get('prompt') or ''):
            break
    return all_msgs


async def step(reader, writer, cmd: str, mode: str = 'game', timeout: float = 8.0) -> str:
    _print_send(cmd)
    await _send(writer, {'lines': [cmd], 'mode': mode})
    msgs = await _robust_recv(reader, overall_timeout=timeout)
    _print_exchange('Response', msgs)
    return '\n'.join(str(l) for m in msgs for l in (m.get('lines') or []))


async def main() -> None:
    reader, writer = await asyncio.open_connection(HOST, PORT)
    if not await _handshake(reader, writer):
        return

    await step(reader, writer, f'connect {USER} {PASSWORD}', mode='login', timeout=3.0)

    # Reload the modified module so this run exercises current code even
    # though the server process predates today's edits.
    await step(reader, writer, 'reload shoppe.ollys commands.use commands.inv')

    # Fund via editplayer's Money menu -- setup_bot_accounts.py only
    # seeds 1,000 in hand, not enough for the 2,000s LONG BOW.
    await step(reader, writer, 'editplayer')
    await step(reader, writer, '11')   # Money submenu
    await step(reader, writer, 'ih')   # In Hand
    await step(reader, writer, '100000')
    await step(reader, writer, '')     # back out of Money submenu
    await step(reader, writer, '')     # quit editplayer

    # Get to the Shoppe: room 1 (MERCHANT LOBBY) has a "Down to Shoppe" exit.
    await step(reader, writer, '#1')
    await step(reader, writer, 'd')

    # Armory: buy LONG BOW (weapons.json #6, 2000s, projectile/ammo weapon).
    await step(reader, writer, 'a')   # Armory
    await step(reader, writer, 'w')   # Weaponry
    await step(reader, writer, 'b')   # Buy
    await step(reader, writer, '6')   # LONG BOW
    await step(reader, writer, 'n')   # skip try-out
    await step(reader, writer, 'y')   # buy it
    await step(reader, writer, 'q')   # leave buy loop
    await step(reader, writer, 'q')   # leave weaponry (buy/sell prompt)

    # Ready it.
    await step(reader, writer, 'x')   # leave shoppe back to the map
    await step(reader, writer, 'ready long bow')
    await step(reader, writer, 'inv')

    # Back to the Shoppe for Olly's.
    await step(reader, writer, '#1')
    await step(reader, writer, 'd')
    await step(reader, writer, 'o')   # Olly's Ammo & Traps
    await step(reader, writer, 'a')   # Ammo section

    print('\n=== Ammo/carrier listing -- confirm quiver appears ===')
    await step(reader, writer, '?')

    print('\n=== Buying quiver -- should arrive full (10 arrows) ===')
    await step(reader, writer, '19')
    await step(reader, writer, 'y')

    print('\n=== Buying a second quiver -- should be refused ===')
    await step(reader, writer, '19')
    await step(reader, writer, 'y')

    await step(reader, writer, 'i')   # inventory shortcut inside the shop
    await step(reader, writer, '')    # leave the Pack tool (blank, not q/x)
    await step(reader, writer, 'q')   # leave the ammo section
    await step(reader, writer, 'q')   # leave Olly's
    await step(reader, writer, 'x')   # leave shoppe

    print('\n=== USE the quiver -- should load the bow and stay in the pack, now empty ===')
    await step(reader, writer, 'use quiver')
    await step(reader, writer, 'inv')

    # Back to Olly's to top off the now-empty quiver.
    await step(reader, writer, '#1')
    await step(reader, writer, 'd')
    await step(reader, writer, 'o')
    await step(reader, writer, 'a')

    print('\n=== Buying "arrows" (shop #3, bow ammo) -- should top off the quiver, not stack ===')
    await step(reader, writer, '3')
    await step(reader, writer, 'y')
    await step(reader, writer, 'q')
    await step(reader, writer, 'q')
    await step(reader, writer, 'x')

    await step(reader, writer, 'inv')

    writer.close()


if __name__ == '__main__':
    asyncio.run(main())
