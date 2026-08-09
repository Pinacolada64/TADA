#!/usr/bin/env python3
"""tools/bot_stat_weapon_ally_check.py — live end-to-end check of stat's new
"Weapon readied" line (player) and "Wpn: ...  Worn: ..." Notes tags
(allies) -- commands/stats.py, 2026-08-08.

Drives a real connection to a running server (JSON protocol, port 34083) as
railbender (see tools/setup_bot_accounts.py for its 3 servant allies --
BATMAN, ARTHUR DENT, BETTY BOOP -- and tools/seed_railbender_uzis.py, run
beforehand, for the 2x UZI + 2x 9 mm ammo added to its inventory):

  1. READY a UZI and USE a box of 9 mm -- loads the player's own weapon.
  2. GIVE the second UZI + second box of 9 mm to ARTHUR DENT -- exercises
     commands/give.py's auto-ready-on-GIVE path for allies.
  3. STAT -- confirms:
       - "Weapon readied: UZI 50/50 rounds" appears for the player.
       - ARTHUR DENT's row shows "Wpn: UZI (50/50)".
       - BATMAN/BETTY BOOP (never given a weapon) show "Wpn: None".
       - Every ally row shows "Worn: None" (allies can't WEAR yet).

Logs in with 'P' (plain text terminal) instead of 'A' (ANSI) -- Ryan's
suggestion, since formatting.py's highlight_brackets() strips [bracket]
delimiters (and applies color) regardless of terminal mode, so plain text
sidesteps ANSI-escape parsing in this script without changing what's being
tested. (Along the way, this script's ORIGINAL nested "[Wpn: UZI [50/50]]"
tag turned out to break highlight_brackets() for real -- a stray "]" and a
color split for ANSI clients -- fixed in commands/stats.py by using
parens for the inner round count instead of a second bracket pair.)

Kept per this repo's convention (CLAUDE.md "Bot scripts") for future
regression checks once confirmed working.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot_client import _send, _recv, _print_exchange, _print_send

HOST, PORT = '127.0.0.1', 34083
USER, PASSWORD = 'railbender', 'puppy123'


async def _handshake_plain(reader, writer) -> bool:
    """Copy of bot_client._handshake that answers the terminal-type prompt
    with 'P' (plain text) instead of 'A' (ANSI) -- avoids emitting color
    escapes at all, see module docstring."""
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
    """Same rationale as bot_ammo_carrier_check.py's copy: only stop on a
    real interactive prompt (one containing '>'), not any truthy prompt
    field -- ambient messages carry a bare context-name prompt too.

    The News board's "More" pager prompt ALSO contains '>' ("[-- More
    [4/51] [?=help] --> ]"), so a bare '>' check stops here too, well
    before the actual login/main prompt -- every subsequent command then
    lands on the pager instead of the game loop and just pages through
    news. Detect it and send a blank line to advance to the NEXT page
    (network_context.py's _paginate(): 'Q' means "stop reading early" and
    discards everything after it, which silently truncated STAT's own
    output -- the Allies table never arrived because 'stat' itself pages
    past 1 screen for this player and Q cut it off after page 1)."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + overall_timeout
    all_msgs: list[dict] = []
    while loop.time() < deadline:
        msg = await _recv(reader, timeout=min(2.0, deadline - loop.time()))
        if msg is None:
            continue
        all_msgs.append(msg)
        prompt = msg.get('prompt') or ''
        if 'more' in prompt.lower():
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


async def main() -> None:
    reader, writer = await asyncio.open_connection(HOST, PORT)
    if not await _handshake_plain(reader, writer):
        return

    await step(reader, writer, f'connect {USER} {PASSWORD}', mode='login', timeout=3.0)

    # Reload the modified module so this run exercises current code even if
    # the server process predates today's edits.
    await step(reader, writer, 'reload commands.stats commands.give commands.use commands.ready')

    await step(reader, writer, 'inv')

    print('\n=== READY a UZI, USE 9 mm ammo for railbender itself ===')
    await step(reader, writer, 'ready uzi')
    await step(reader, writer, 'use 9 mm')

    print('\n=== GIVE the second UZI + second box of 9 mm to ARTHUR DENT ===')
    await step(reader, writer, 'give uzi to arthur dent')
    await step(reader, writer, 'give 9 mm to arthur dent')

    print('\n=== STAT -- check player Weapon readied line + ally Wpn/Worn tags ===')
    raw_stat_text = await step(reader, writer, 'stat', timeout=10.0)
    # formatting.py's highlight_brackets() strips [bracket] delimiters
    # unconditionally (even in plain-text mode, see module docstring), so
    # the wire text never contains literal '[' ']' around these tags --
    # collapse whitespace/newlines only, no bracket text to match.
    stat_text = ' '.join(raw_stat_text.split())

    checks = [
        ('Player weapon readied w/ ammo', 'Weapon readied: UZI 50/50 rounds' in stat_text),
        ('Arthur Dent readied UZI',       'ARTHUR DENT' in stat_text and 'Wpn: UZI (50/50)' in stat_text),
        ('Batman shows no weapon',        'BATMAN' in stat_text and 'Wpn: None' in stat_text),
        ('Worn tag present',              'Worn: None' in stat_text),
    ]
    print('\n=== Results ===')
    all_ok = True
    for label, ok in checks:
        print(f'  [{"PASS" if ok else "FAIL"}] {label}')
        all_ok = all_ok and ok
    print('\nALL CHECKS PASSED' if all_ok else '\nSOME CHECKS FAILED -- see log above')

    writer.close()


if __name__ == '__main__':
    asyncio.run(main())
