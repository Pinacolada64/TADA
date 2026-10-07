#!/usr/bin/env python3
"""tools/bot_leader_handoff.py — live check of PR #70's fight hand-off:
when a fight's leader drops out while another player is still in it, that
player's next ATTACK takes over the same wounded monster instead of
starting a fresh, full-HP fight.

Two admin bots (tools/setup_bot_accounts.py) on a real running server:

  1. botdruid and botlasso admin-teleport to level 1 room 116 (the
     GARGOYLE, 10 HP). Admin teleport doesn't roll the room-entry
     encounter, so the GARGOYLE waits to be attacked.
  2. botdruid ATTACKs (and leads); botlasso ATTACKs once to join. botlasso
     has no living allies, so its join is a single swing.
  3. botdruid swings until the GARGOYLE is hurt, then drops its connection
     at the combat prompt.
  4. botlasso ATTACKs: expects "You take the lead against the GARGOYLE!"
     and the combat prompt showing the HP botdruid last saw, not
     "Combat begins!" at full HP.
  5. botlasso drops too, which ends the fight. botdruid reconnects and
     ATTACKs: a fresh "Combat begins!" at full HP proves the old fight
     came out of active_combats rather than lingering leaderless.

Nobody kills the GARGOYLE, so it can be re-run.

Usage:
    .venv/bin/python3 tools/bot_leader_handoff.py [--host H] [--port P]

Prints PASS/FAIL per check and writes bot_leader_handoff_<timestamp>.log.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bot_credentials import load_password  # noqa: E402

LEADER, OTHER = 'botdruid', 'botlasso'
LEVEL, ROOM = 1, 116
MONSTER = 'GARGOYLE'
MAX_SWINGS = 30
ANSI = re.compile(r'\x1b\[[0-9;]*m')
HP_RE = re.compile(rf'{MONSTER} HP:(\d+)\)')

transcript: list[str] = []
results: list[tuple[bool, str]] = []


def log(text: str) -> None:
    transcript.append(text)


def check(ok: bool, label: str, detail: str = '') -> None:
    results.append((ok, label))
    line = f"{'PASS' if ok else 'FAIL'}  {label}" + (f'  -- {detail}' if detail and not ok else '')
    print(line)
    log(line)


def flat(text: str) -> str:
    """Collapse whitespace -- the server word-wraps to the client's width."""
    return ' '.join(text.split())


class Conn:
    def __init__(self, name, reader, writer):
        self.name, self.reader, self.writer = name, reader, writer
        self.eof = False

    async def send(self, text: str | None, mode: str = 'game') -> None:
        obj = {'lines': [] if text is None else [text], 'mode': mode}
        log(f'[{self.name}] >>> {text!r} ({mode})')
        self.writer.write(json.dumps(obj).encode() + b'\n')
        await self.writer.drain()

    async def read(self, *, quiet: float = 1.0, max_wait: float = 8.0):
        """Lines and the last prompt, until a prompt arrives and then
        `quiet` seconds pass. ctx.prompt() text arrives in "prompt", never
        "lines" (CLAUDE.md, Bot scripts)."""
        lines, prompt = [], ''
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(self.reader.readline(),
                                             timeout=quiet if prompt else max(0.1, deadline - time.time()))
            except asyncio.TimeoutError:
                if prompt:
                    break
                continue
            if not raw:
                self.eof = True
                break
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            got = msg.get('lines') or []
            if isinstance(got, str):
                got = [got]
            for line in got:
                line = ANSI.sub('', str(line))
                lines.append(line)
                log(f'[{self.name}]     {line}')
            if msg.get('prompt'):
                prompt = ANSI.sub('', str(msg['prompt']))
                log(f'[{self.name}]     [prompt] {prompt}')
        return flat('\n'.join(lines)), prompt

    async def step(self, text: str | None):
        await self.send(text)
        out, prompt = await self.read()
        while 'More' in prompt or 'End [' in prompt:
            await self.send('')
            more, prompt = await self.read()
            out += ' ' + more
        return out, prompt

    def drop(self) -> None:
        """Abrupt disconnect, like a dropped modem line."""
        log(f'[{self.name}] *** connection dropped')
        try:
            self.writer.transport.abort()
        except Exception:
            self.writer.close()


async def login(host: str, port: int, name: str) -> Conn:
    reader, writer = await asyncio.open_connection(host, port)
    conn = Conn(name, reader, writer)
    first = json.loads(await asyncio.wait_for(reader.readline(), timeout=5))
    writer.write(json.dumps({'server_id': first.get('server_id', 'test_server'),
                             'server_key': first.get('server_key', 'test_key')}).encode() + b'\n')
    await writer.drain()
    _, prompt = await conn.read()
    for _ in range(10):
        if prompt.endswith('login> '):
            break
        await conn.send('A' if 'terminal type' in prompt.lower() else 'q', 'login')
        _, prompt = await conn.read()
    await conn.send(f'connect {name} {load_password(name)}', 'login')
    _, prompt = await conn.read()
    for _ in range(10):
        if prompt.endswith('main> '):
            break
        await conn.send('', 'game')
        _, prompt = await conn.read()
    return conn


def at_combat_prompt(prompt: str) -> bool:
    return prompt.rstrip().endswith('Command>')


def last_hp(text: str) -> int | None:
    hps = HP_RE.findall(text)
    return int(hps[-1]) if hps else None


async def run(host: str, port: int) -> None:
    leader = await login(host, port, LEADER)
    other = await login(host, port, OTHER)
    for conn in (leader, other):
        out, _ = await conn.step(f'teleport {LEVEL} {ROOM}')
        if 'Freeze Adventurer' in out:
            # A live 'tough' monster blocks admin teleport out of its room
            # (commands/teleport.py) -- e.g. the GUARDIAN in level 5 room
            # 125, where botlasso/botdummy are parked. Walk out first (north
            # of 125 is The Oasis, no monster -- same move as
            # tools/bot_epic_battle.py), then teleport.
            await conn.step('north')
            out, _ = await conn.step(f'teleport {LEVEL} {ROOM}')
    check(MONSTER in out, f'both bots in room {ROOM} with the {MONSTER}', out[-300:])

    out, prompt = await leader.step('attack')
    check('Combat begins!' in out and at_combat_prompt(prompt), f'{LEADER} starts the fight', out[-300:])
    full_hp = last_hp(out)

    out, _ = await other.step('attack')
    check('Combat begins!' not in out, f'{OTHER} joins (no second fight)', out[-300:])

    # The leader swings until the monster is visibly hurt; HP shows on each prompt.
    hp_seen, text = None, ''
    for _ in range(MAX_SWINGS):
        text, prompt = await leader.step('a')
        hp = last_hp(text)
        if hp is not None and full_hp is not None and hp < full_hp and at_combat_prompt(prompt):
            hp_seen = hp
            break
    check(hp_seen is not None, f'{MONSTER} hurt below full HP ({full_hp})', text[-300:])
    if hp_seen is None:
        return
    log(f'--- {MONSTER} at {hp_seen}/{full_hp} HP; dropping {LEADER}')
    leader.drop()
    await asyncio.sleep(1.5)
    await other.read(max_wait=2.0)

    out, prompt = await other.step('attack')
    check(f'You take the lead against the {MONSTER}!' in out,
          f'{OTHER} takes the lead after {LEADER} drops', out[-300:])
    check('Combat begins!' not in out, 'no fresh fight opened', out[-300:])
    check(last_hp(out) == hp_seen, f'same wounded {MONSTER}: HP {hp_seen} carried over',
          f'saw {last_hp(out)} in {out[-300:]!r}')
    check(at_combat_prompt(prompt), f'{OTHER} now at the combat prompt', prompt)

    other.drop()
    await asyncio.sleep(1.5)

    # Last fighter gone: the fight must have ended and been cleaned up.
    leader = await login(host, port, LEADER)
    out, prompt = await leader.step('attack')
    check('Combat begins!' in out and last_hp(out) == full_hp,
          'fight cleaned up: a new ATTACK starts fresh at full HP', out[-300:])
    leader.drop()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=34083)
    args = ap.parse_args()
    try:
        asyncio.run(asyncio.wait_for(run(args.host, args.port), timeout=180))
    finally:
        path = Path(f'bot_leader_handoff_{datetime.now():%Y-%m-%d_%H%M%S}.log')
        path.write_text('\n'.join(transcript) + '\n')
        passed = sum(ok for ok, _ in results)
        print(f'\n{passed}/{len(results)} checks passed -- transcript: {path}')


if __name__ == '__main__':
    main()
