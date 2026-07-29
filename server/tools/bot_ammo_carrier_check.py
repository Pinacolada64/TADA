#!/usr/bin/env python3
"""tools/bot_ammo_carrier_check.py — live end-to-end check of the ammo
carrier auto-load mechanic (shoppe/ollys.py, commands/use.py, commands/
inv.py; see MECHANICS.md's "Ammo carriers auto-load" entry).

Drives a real connection to a running server (JSON protocol, port 34083)
as botdummy: reloads the affected modules (so the check exercises live
code even against a server process that predates the change), funds the
character via editplayer's Money menu, buys a MUSKET and readies it,
then walks the full carrier lifecycle at Olly's:

  1. Buy a cartridge box (carrier) -- must arrive full and refuse a
     second purchase of the same type.
  2. USE the carrier -- rounds load into the weapon, carrier stays in
     the pack, now empty.
  3. Buy raw ammo (balls) matching the now-empty carrier -- must top it
     back off instead of sitting as its own stack.
  4. INV at each step to confirm the "[N rounds xM]" / "[cur/cap
     rounds]" display.

Kept per this repo's convention (CLAUDE.md "Bot scripts") for future
regression checks once it's confirmed working.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot_client import _handshake, _send, _recv, _print_exchange, _print_send

HOST, PORT = '127.0.0.1', 34083
USER, PASSWORD = 'botdummy', 'puppy123'


async def _robust_recv(reader, overall_timeout: float = 10.0) -> list[dict]:
    """Like bot_client._recv_all, but only stops on a real interactive
    prompt (one containing '>', e.g. "[13:04] main> ") rather than any
    truthy prompt field -- ambient messages (news, tips, room text) are
    also tagged with a bare context name ("main") as they stream by, so
    _recv_all's "stop at the first truthy prompt" rule quits early and
    leaves later parts of the same response to be misread as the answer
    to whatever command gets sent next."""
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

    # Reload the modified modules so this run exercises current code even
    # if the server process predates today's edits (Python doesn't
    # hot-reload .py files on its own).
    await step(reader, writer, 'reload shoppe.ollys commands.use commands.give commands.inv')

    # tools/setup_bot_accounts.py seeds botdummy with 100,000 silver and a
    # fresh, empty inventory each time it's re-run -- no in-game funding
    # step needed as long as it's been re-run before this script.

    # Get to the Shoppe: room 1 (MERCHANT LOBBY) has a "Down to Shoppe" exit.
    await step(reader, writer, '#1')
    await step(reader, writer, 'd')

    # Armory: buy MUSKET (weapons.json #36, 430s, projectile/ammo weapon).
    await step(reader, writer, 'a')   # Armory
    await step(reader, writer, 'w')   # Weaponry
    await step(reader, writer, 'b')   # Buy
    await step(reader, writer, '36')  # MUSKET
    await step(reader, writer, 'n')   # skip try-out
    await step(reader, writer, 'y')   # buy it
    await step(reader, writer, 'q')   # leave buy loop
    await step(reader, writer, 'q')   # leave weaponry (buy/sell prompt)

    # Ready it.
    await step(reader, writer, 'x')   # leave shoppe back to the map
    await step(reader, writer, 'ready musket')
    await step(reader, writer, 'inv')

    # Back to the Shoppe for Olly's.
    await step(reader, writer, '#1')
    await step(reader, writer, 'd')
    await step(reader, writer, 'o')   # Olly's Ammo & Traps
    await step(reader, writer, 'a')   # Ammo section

    print('\n=== Buying cartridge box (carrier, shop #15) -- should arrive full ===')
    await step(reader, writer, '15')
    await step(reader, writer, 'y')

    print('\n=== Buying a second cartridge box -- should be refused ===')
    await step(reader, writer, '15')
    await step(reader, writer, 'y')

    await step(reader, writer, 'i')   # inventory shortcut inside the shop
    await step(reader, writer, 'q')   # leave the ammo section
    await step(reader, writer, 'q')   # leave Olly's
    await step(reader, writer, 'x')   # leave shoppe

    print('\n=== USE the carrier -- should load the weapon and stay in the pack, now empty ===')
    await step(reader, writer, 'use cartridge box')
    await step(reader, writer, 'inv')

    # Back to Olly's to top off the now-empty carrier.
    await step(reader, writer, '#1')
    await step(reader, writer, 'd')
    await step(reader, writer, 'o')
    await step(reader, writer, 'a')

    print('\n=== Buying "balls" (shop #6, musket ammo) -- should top off the carrier, not stack ===')
    await step(reader, writer, '6')
    await step(reader, writer, 'y')
    await step(reader, writer, 'q')
    await step(reader, writer, 'q')
    await step(reader, writer, 'x')

    await step(reader, writer, 'inv')

    writer.close()


if __name__ == '__main__':
    asyncio.run(main())
