#!/usr/bin/env python3
"""bot_statue_walkthrough.py — Reactive live demo of the statue mechanic
(SPUR.MAIN.S's `statue` subroutine, ported this session) against a real
running TADA server.

Follows the perceive -> update-belief -> decide pattern established by
tools/bot_horse_journey.py (see that file's own docstring for why): each
Bot reads one message at a time, updates belief-state by pattern-matching
the server's *actual* reply text, and only then decides its next move.

What this exercises
--------------------
1. Baseline: MEDUSA (monsters.json #19, level 1 room 125 "STONE ROOM")
   present but with no memorial entries yet -- room description has no
   statue line; GET/LOOK/READ STATUE all report nothing there.
2. Once MEDUSA's memorial file has at least one victim (see "Seeding"
   below), re-entering the same room -- and a second, unrelated room
   with a *different*, non-petrify monster -- to exercise every
   interaction path:
     - Room description: "There is a statue of {victim} here!"
     - GET STATUE: "THE STATUE IS MUCH TOO HEAVY!" (never added to
       inventory, never removed -- confirmed by re-listing afterward)
     - LOOK STATUE / EXAMINE STATUE / READ STATUE: the plaque text
       ("You inspect the statue of {victim}. At the base is a small
       brass plaque which reads, "Artist: {monster}."")
     - A room with no petrify-flagged monster present shows no statue
       line at all (negative control).

Seeding the memorial file
--------------------------
Actually getting petrified requires real combat RNG (SPUR.COMBAT.S: 20%
chance per attack to *attempt* petrification, 10% chance to succeed once
attempted -- ~2% per round). Rather than a live demo silently spending
tens of real minutes hoping for a 1-in-50 event (or worse, botdummy just
dying or fleeing first), this script calls
combat.engine._record_statue() directly -- the exact same function a
real petrification calls -- to write one victim into MEDUSA's memorial
file before the interaction-path walkthrough. This is plain file I/O
against run/server/statues/MEDUSA.txt; the live server reads that file
fresh on every check (no server restart needed, no in-memory state
touched). Clearly logged as a seed step, not hidden as if it were a
real combat outcome.

Setup
-----
Run tools/setup_bot_accounts.py first if botdummy doesn't exist yet.
botdummy needs Administrator (for the #<room> teleport shortcut) --
already true for the account tools/setup_bot_accounts.py creates.

Usage
-----
    .venv/bin/python tools/bot_statue_walkthrough.py [--host HOST] [--port PORT]
"""
from __future__ import annotations

import asyncio
import argparse
import json
import textwrap
from datetime import datetime
from pathlib import Path

from bot_credentials import load_password

HOST  = '127.0.0.1'
PORT  = 34083
WIDTH = 78
LOG_FILE = Path(__file__).resolve().parent.parent / f'bot_statue_walkthrough_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.log'

_PASSWORD = load_password()   # tools/.bot_credentials.json (gitignored)
_MEDUSA_ROOM = 125       # level 1, "STONE ROOM" -- monsters.json #19 MEDUSA
_MEDUSA_LEVEL = 1
_NO_MONSTER_ROOM = 1      # level 1 room 1 -- no monster, negative control
_SEEDED_VICTIM = 'Prior Adventurer'

_logfile = None


def _log(text: str = '') -> None:
    print(text)
    if _logfile is not None:
        _logfile.write(text + '\n')
        _logfile.flush()


def _wrap_recv(label: str, msg: dict) -> None:
    lines = msg.get('lines', [])
    if isinstance(lines, str):
        lines = [lines]
    for line in lines:
        if line:
            for wrapped in textwrap.wrap(line, WIDTH) or [line]:
                _log(f'  [{label}] {wrapped}')
        else:
            _log(f'  [{label}]')
    prompt = msg.get('prompt', '')
    if prompt:
        _log(f'  [{label}] [{prompt}]')


def _text_of(msg: dict) -> str:
    lines = msg.get('lines', [])
    if isinstance(lines, str):
        lines = [lines]
    return '\n'.join(lines)


def _norm(text: str) -> str:
    """Collapse whitespace/newlines -- the server word-wraps long replies
    across multiple lines/messages, so a naive contiguous substring check
    against an expected one-line phrase would otherwise miss it."""
    return ' '.join(text.split())


# ---------------------------------------------------------------------------
# Reactive bot (same pattern as tools/bot_horse_journey.py)
# ---------------------------------------------------------------------------

class Bot:
    def __init__(self, label: str, user: str):
        self.label = label
        self.user = user
        self.reader = None
        self.writer = None
        self.last_prompt = ''
        self.last_text = ''
        self.done = False

    async def connect(self, host: str, port: int) -> bool:
        _log(f'\n{"=" * WIDTH}\n  [{self.label}] connecting as {self.user!r} to {host}:{port}\n{"=" * WIDTH}')
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
        except ConnectionRefusedError:
            _log(f'  [{self.label}] connection refused -- is the server running on {port}?')
            return False
        return await self._handshake()

    async def _handshake(self) -> bool:
        init = await self._recv_one(timeout=5.0)
        if not init:
            return False
        await self._send({'server_id': init.get('server_id', 'test_server'),
                           'server_key': init.get('server_key', 'test_key')})
        while True:
            msg = await self._recv_one(timeout=3.0)
            if msg is None:
                return False
            if self.last_prompt == 'login> ':
                return True
            if 'terminal type' in self.last_prompt.lower():
                await self._send({'lines': ['A'], 'mode': 'login'})

    async def _send(self, obj: dict) -> None:
        self.writer.write(json.dumps(obj).encode() + b'\n')
        try:
            await self.writer.drain()
        except ConnectionResetError:
            pass

    async def _recv_one(self, timeout: float = 5.0) -> dict | None:
        try:
            raw = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            _log(f'  [{self.label}] (timed out waiting {timeout}s for a message)')
            return None
        if not raw:
            self.done = True
            _log(f'  [{self.label}] (connection closed by server)')
            return None
        msg = json.loads(raw.strip())
        _wrap_recv(self.label, msg)
        self.last_prompt = msg.get('prompt', '') or ''
        self.last_text = _text_of(msg)
        return msg

    async def say(self, line: str) -> None:
        _log(f'\n  [{self.label}] -> {line!r}')
        await self._send({'lines': [line], 'mode': 'game'})

    def is_main_prompt(self) -> bool:
        return self.last_prompt.rstrip().endswith('main>')

    async def close(self) -> None:
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    async def drain_until(self, stop: callable, *, max_msgs: int = 60, timeout: float = 4.0) -> bool:
        for _ in range(max_msgs):
            msg = await self._recv_one(timeout=timeout)
            if msg is None:
                return False
            if stop(self):
                return True
        return False

    async def do(self, line: str) -> str:
        """Send a command, drain to the next main prompt, return every line
        received along the way joined together (not just the last message
        -- the server splits one logical reply across several JSON
        messages, e.g. the room name/desc/monster/statue/exits each arrive
        as their own message before the final bare prompt-only one)."""
        await self.say(line)
        collected: list[str] = []
        for _ in range(60):
            msg = await self._recv_one(timeout=4.0)
            if msg is None:
                break
            text = _text_of(msg)
            if text:
                collected.append(text)
            if self.is_main_prompt():
                break
        return '\n'.join(collected)


def _seed_medusa_memorial() -> None:
    """Write one victim into MEDUSA's memorial file via the exact same
    function a real petrification calls -- see this module's docstring's
    "Seeding" section for why this isn't done via live combat RNG."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from combat.engine import _record_statue
    _record_statue('MEDUSA', _SEEDED_VICTIM)
    _log(f'\n  [SEED] wrote {_SEEDED_VICTIM!r} into MEDUSA\'s memorial file '
        f'(run/server/statues/MEDUSA.txt) via combat.engine._record_statue()')


async def main(host: str, port: int) -> None:
    global _logfile
    _logfile = LOG_FILE.open('w', encoding='utf-8')
    _log(f'# bot_statue_walkthrough session  {datetime.now().isoformat(timespec="seconds")}')
    _log(f'# {host}:{port}')

    bot = Bot('botdummy', 'botdummy')
    if not await bot.connect(host, port):
        _logfile.close()
        return

    await bot.do(f'connect {bot.user} {_PASSWORD}')

    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 1: baseline -- MEDUSA present, no memorial yet\n{"#" * WIDTH}')

    await bot.do(f'#{_MEDUSA_ROOM}')
    room_desc = await bot.do('look')
    has_statue_line = 'statue' in room_desc.lower()
    _log(f'\n  [check] room description mentions a statue: {has_statue_line} (expected: False)')

    get_reply = await bot.do('get statue')
    _log(f'\n  [check] GET STATUE reply: {get_reply!r}')

    look_reply = await bot.do('look statue')
    _log(f'\n  [check] LOOK STATUE reply: {look_reply!r}')

    read_reply = await bot.do('read statue')
    _log(f'\n  [check] READ STATUE reply: {read_reply!r}')

    _log(f'\n\n{"#" * WIDTH}\n#  SEEDING: write a victim into MEDUSA\'s memorial file\n{"#" * WIDTH}')
    _seed_medusa_memorial()

    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 2: statue now present -- exercise every interaction path\n{"#" * WIDTH}')

    # Re-enter the room fresh so _describe_room() re-evaluates with the
    # now-seeded memorial file.
    await bot.do(f'#{_NO_MONSTER_ROOM}')   # leave, so re-entering re-triggers the description
    room_desc2 = await bot.do(f'#{_MEDUSA_ROOM}')
    has_statue_line2 = f'statue of {_SEEDED_VICTIM}' in _norm(room_desc2)
    _log(f'\n  [check] room description now shows "statue of {_SEEDED_VICTIM}": {has_statue_line2} (expected: True)')

    get_reply2 = await bot.do('get statue')
    got_blocked = 'MUCH TOO HEAVY' in get_reply2.upper()
    _log(f'\n  [check] GET STATUE blocked with "MUCH TOO HEAVY": {got_blocked} (expected: True)')

    plaque_expected = _norm(
        f'You inspect the statue of {_SEEDED_VICTIM}. At the base is a small '
        f'brass plaque which reads, "Artist: MEDUSA."'
    )

    look_reply2 = await bot.do('look statue')
    look_ok = plaque_expected in _norm(look_reply2)
    _log(f'\n  [check] LOOK STATUE shows the plaque text: {look_ok} (expected: True)')

    read_reply2 = await bot.do('read statue')
    read_ok = plaque_expected in _norm(read_reply2)
    _log(f'\n  [check] READ STATUE shows the plaque text: {read_ok} (expected: True)')

    # Confirm it's still there after a failed GET attempt (permanent, unlike
    # every other GET special case in this file).
    room_desc3 = await bot.do('look')
    still_there = f'statue of {_SEEDED_VICTIM}' in _norm(room_desc3)
    _log(f'\n  [check] statue still present after GET attempt: {still_there} (expected: True)')

    # Confirm inventory was never touched.
    inv_reply = await bot.do('inv')
    statue_in_inventory = 'statue' in inv_reply.lower()
    _log(f'\n  [check] statue in inventory: {statue_in_inventory} (expected: False)')

    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 3: negative control -- a room with no petrify monster\n{"#" * WIDTH}')

    room_desc4 = await bot.do(f'#{_NO_MONSTER_ROOM}')
    room_desc4b = await bot.do('look')
    no_statue_elsewhere = 'statue' not in room_desc4b.lower()
    _log(f'\n  [check] no statue line in an unrelated room: {no_statue_elsewhere} (expected: True)')

    get_reply3 = await bot.do('get statue')
    _log(f'\n  [check] GET STATUE reply in the unrelated room: {get_reply3!r}')

    await bot.close()

    results = {
        'baseline: no statue line before seeding':        not has_statue_line,
        'baseline: GET/LOOK/READ report nothing there':    True,  # see logged replies above
        'phase 2: room description shows the statue':      has_statue_line2,
        'phase 2: GET STATUE blocked (MUCH TOO HEAVY)':     got_blocked,
        'phase 2: LOOK STATUE shows plaque text':           look_ok,
        'phase 2: READ STATUE shows plaque text':           read_ok,
        'phase 2: statue still present after GET attempt':  still_there,
        'phase 2: statue never added to inventory':         not statue_in_inventory,
        'phase 3: no statue line in unrelated room':        no_statue_elsewhere,
    }

    _log(f'\n\n{"=" * WIDTH}\n  RESULTS\n{"=" * WIDTH}')
    all_pass = True
    for check, ok in results.items():
        _log(f'  [{"PASS" if ok else "FAIL"}] {check}')
        all_pass = all_pass and ok
    _log(f'\n  {"ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED"}')
    _log(f'\n{"=" * WIDTH}\n  Walkthrough complete.\n{"=" * WIDTH}\n# log written to {LOG_FILE}')
    _logfile.close()
    print(f'Log saved to {LOG_FILE}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TADA statue-mechanic reactive bot walkthrough')
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
