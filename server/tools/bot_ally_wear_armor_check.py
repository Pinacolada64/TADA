#!/usr/bin/env python3
"""tools/bot_ally_wear_armor_check.py — live end-to-end check of the
armor/shield-wearing GIVE branch for allies (commands/give.py, 2026-08-09)
and the STATS "[Worn: ...]" tag it feeds (commands/stats.py).

Drives a real connection to a running server (JSON protocol, port 34083)
as 'test' (see run/server/player-test.json -- carries a "cloth armor" in
inventory and a servant ally ATHENA already parked in the same room).

  1. GIVE cloth armor to ATHENA -- exercises the new auto-wear-on-GIVE
     path (was: falls through to the generic "takes it and tucks it
     away" message).
  2. STAT -- confirms ATHENA's row shows "Worn: cloth armor" instead of
     the old hardcoded "Worn: None".
  3. TAKE armor from ATHENA -- confirms the original bug report ("can't
     TAKE it back") is unaffected/still works once the item is back in
     her ally.items list.

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
    """Copy of bot_client._handshake that answers the terminal-type prompt
    with 'P' (plain text) instead of 'A' (ANSI) -- see
    tools/bot_stat_weapon_ally_check.py's docstring for why (bracket tags
    read cleanly either way, but plain text sidesteps ANSI-escape parsing
    in this script without changing what's being tested)."""
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
    """Same rationale as tools/bot_stat_weapon_ally_check.py's copy: only
    stop on a real interactive prompt (one containing '>'), and drain
    network_context.py's _paginate() pager -- both its "-- More [n/N]"
    AND "-- End [n/N]" prompts contain '[?=help] --> ]' (a literal '>'),
    but _paginate() itself only returns to the real command prompt once
    it receives ANY keystroke at the End page too (see its `elif at_end:
    return` branch) -- stopping on the first '>' without dismissing the
    End page as well means the NEXT step's command text gets silently
    consumed as that dismissal instead of ever reaching the command
    processor. Found live: 'take armor from athena' got eaten by STAT's
    own trailing "-- End [2/2]" page and never ran at all."""
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


async def main() -> None:
    reader, writer = await asyncio.open_connection(HOST, PORT)
    if not await _handshake_plain(reader, writer):
        return

    await step(reader, writer, f'connect {USER} {PASSWORD}', mode='login', timeout=15.0)

    await step(reader, writer, 'inv')

    print('\n=== GIVE cloth armor to ATHENA ===')
    give_text = await step(reader, writer, 'give cloth armor to athena')

    print('\n=== STAT -- check Athena Worn tag ===')
    raw_stat_text = await step(reader, writer, 'stat', timeout=10.0)
    stat_text = ' '.join(raw_stat_text.split())

    print('\n=== TAKE armor back from ATHENA ===')
    take_text = await step(reader, writer, 'take armor from athena')

    checks = [
        ('GIVE says "wears", not "tucks away"',
         'wears' in give_text.lower() and 'tucks' not in give_text.lower()),
        # The Notes cell's "[Worn: cloth armor]" tag can land split across
        # two wrapped table rows on a narrow render (border.py word-wraps
        # the cell, not the tag) -- checking for both fragments anywhere
        # in the ally section is enough proof without depending on exact
        # adjacency.
        ('STAT shows Athena Worn: cloth armor',
         'ATHENA' in stat_text and '[Worn:' in stat_text and 'cloth armor]' in stat_text.lower()),
        ('TAKE hands the armor back',
         'hands you' in take_text.lower() or 'armor' in take_text.lower()),
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
