#!/usr/bin/env python3
"""tools/bot_monster_initiative.py — live check of PR #69's combat changes
(monsters strike first, SPUR round order, commands at the combat prompt,
bye mid-fight) against a real running TADA server.

Walks botdruid (a clean, non-expert admin bot -- see
tools/setup_bot_accounts.py) south from level 1 room 1 into room 13's
TROLL until the monster engages on its own (a surprise or charm roll can
avoid the fight, so it steps back north and re-enters, up to MAX_TRIES).
Then, at the combat prompt:

  - the monster swung before the first prompt ("Combat begins!  The
    TROLL attacks you!" followed by a swing line)
  - INV, LOOK, a refused move (n) and a typo are free: no monster swing
  - e[X]it and USE each spend the turn: the monster swings again
  - a client Mode.bye ends the session with no parting player swing, and
    the server closes the connection

Then it reconnects, confirms the save put it in room 13, and walks back
north to room 1 so the next run starts clean. The TROLL is never
attacked, so it stays alive for re-runs.

Usage:
    .venv/bin/python3 tools/bot_monster_initiative.py [--host H] [--port P]

Prints PASS/FAIL per check and writes a transcript to
bot_monster_initiative_<timestamp>.log.
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

USER = 'botdruid'
MAX_TRIES = 12
ANSI = re.compile(r'\x1b\[[0-9;]*m')
# combat/engine.py _narrate_monster_swing() / turn-to-stone lines.
MONSTER_SWING = re.compile(r'misses you\.|hits you for|TURN TO STONE|off the hook|'
                           r'channels strange energy|day off')
# combat/engine.py _narrate_player_swing() lines.
PLAYER_SWING = re.compile(r'You strike|MISSED|You miss over|Fire flashes from|is ineffective against')

transcript: list[str] = []
results: list[tuple[bool, str]] = []


def log(text: str) -> None:
    transcript.append(text)


def check(ok: bool, label: str, detail: str = '') -> None:
    results.append((ok, label))
    line = f"{'PASS' if ok else 'FAIL'}  {label}" + (f'  -- {detail}' if detail and not ok else '')
    print(line)
    log(line)


class Conn:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.eof = False

    async def send(self, text: str | None, mode: str = 'game') -> None:
        obj = {'lines': [] if text is None else [text], 'mode': mode}
        log(f'>>> {text!r} ({mode})')
        self.writer.write(json.dumps(obj).encode() + b'\n')
        await self.writer.drain()

    async def read(self, *, quiet: float = 1.2, max_wait: float = 8.0):
        """Lines and the last prompt, until a prompt arrives and then
        `quiet` seconds pass with nothing more. ctx.prompt() text arrives
        in "prompt", never "lines" (CLAUDE.md, Bot scripts)."""
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
                log(f'    {line}')
            if msg.get('prompt'):
                prompt = ANSI.sub('', str(msg['prompt']))
                log(f'    [prompt] {prompt}')
        return '\n'.join(lines), prompt

    async def step(self, text: str | None, mode: str = 'game'):
        await self.send(text, mode)
        out, prompt = await self.read()
        # Page through any "-- More --" so the next command lands on a real prompt.
        while 'More' in prompt or 'End [' in prompt:
            await self.send('', mode)
            more, prompt = await self.read()
            out += '\n' + more
        return out, prompt


async def login(host: str, port: int) -> tuple[Conn, str]:
    reader, writer = await asyncio.open_connection(host, port)
    conn = Conn(reader, writer)
    first = json.loads(await asyncio.wait_for(reader.readline(), timeout=5))
    writer.write(json.dumps({'server_id': first.get('server_id', 'test_server'),
                             'server_key': first.get('server_key', 'test_key')}).encode() + b'\n')
    await writer.drain()
    text, prompt = await conn.read()
    for _ in range(10):
        if prompt.endswith('login> '):
            break
        reply = 'A' if 'terminal type' in prompt.lower() else 'q'
        await conn.send(reply, 'login')
        more, prompt = await conn.read()
        text += '\n' + more
    await conn.send(f'connect {USER} {load_password(USER)}', 'login')
    out, prompt = await conn.read()
    for _ in range(10):
        if prompt.endswith('main> '):
            break
        await conn.send('', 'game')
        more, prompt = await conn.read()
        out += '\n' + more
    return conn, out


def flat(text: str) -> str:
    """Collapse whitespace -- the server word-wraps to the client's
    width, so a message can arrive split across lines."""
    return ' '.join(text.split())


def is_combat_prompt(prompt: str) -> bool:
    return prompt.rstrip().endswith('Command>')


async def run(host: str, port: int) -> None:
    conn, _ = await login(host, port)
    await conn.step('teleport 1')

    engaged_text = ''
    for attempt in range(1, MAX_TRIES + 1):
        out, prompt = await conn.step('s')
        if 'Combat begins!' in out and is_combat_prompt(prompt):
            engaged_text = out
            log(f'--- engaged on attempt {attempt}')
            break
        # Surprised/charmed/no fight: step back out (answering any charm
        # join offer with N) and try again.
        out, prompt = await conn.step('n')
        while 'Y' in prompt and '/' in prompt:
            out, prompt = await conn.step('n')
    check(bool(engaged_text), 'TROLL engages on room entry', f'no fight in {MAX_TRIES} tries')
    if not engaged_text:
        return

    begins = engaged_text.index('Combat begins!')
    first_swing = MONSTER_SWING.search(engaged_text, begins)
    check('The TROLL attacks you!' in flat(engaged_text), 'opening line says the TROLL attacks')
    check(first_swing is not None, 'monster swings before the first prompt', engaged_text[-400:])
    check('(Or USE, CAST, EAT, DRINK, INV...)' in flat(engaged_text),
          'non-expert preamble lists mid-fight commands')

    for cmd, label in (('i', 'INV is free'), ('look', 'LOOK is free'),
                       ('n', 'moving is refused for free'), ('xyzzy', 'a typo is free')):
        out, prompt = await conn.step(cmd)
        check(MONSTER_SWING.search(out) is None and is_combat_prompt(prompt), label,
              f'prompt={prompt!r} out={out[-300:]!r}')
        if cmd == 'n':
            check("You can't do that in the middle of a fight!" in flat(out), 'refusal message shown')
        if cmd == 'xyzzy':
            check('Huh?' in out, 'typo answered with Huh?')

    out, prompt = await conn.step('x')
    check(MONSTER_SWING.search(out) is not None and is_combat_prompt(prompt),
          'e[X]it costs the turn (monster swings)', out[-300:])

    out, prompt = await conn.step('use')
    for _ in range(3):                       # back out of any USE sub-prompt
        if is_combat_prompt(prompt) or conn.eof:
            break
        more, prompt = await conn.step('')
        out += '\n' + more
    check(MONSTER_SWING.search(out) is not None and is_combat_prompt(prompt),
          'USE costs the turn (monster swings)', out[-300:])

    # bye mid-fight: no parting swing, and the server hangs up.
    await conn.send(None, 'bye')
    out, _ = await conn.read(max_wait=6.0)
    check(PLAYER_SWING.search(out) is None, 'bye mid-fight: no parting player swing', out[-300:])
    check(conn.eof, 'bye mid-fight: server closes the connection')
    conn.writer.close()

    # Reconnect: saved in room 13, then walk back out for the next run.
    await asyncio.sleep(1.0)
    conn, out = await login(host, port)
    # Debug Mode shows the room number after the title, e.g. "[13]"; room
    # 1's exit line reads "[to #13]", which doesn't match.
    check('[13]' in out, 'reconnect lands in room 13 (save happened)', out[-400:])
    out, prompt = await conn.step('n')
    while 'Y' in prompt and '/' in prompt:
        out, prompt = await conn.step('n')
    check('[1]' in out, 'walked back to room 1', out[-300:])
    await conn.send(None, 'bye')
    conn.writer.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=34083)
    args = ap.parse_args()
    try:
        asyncio.run(asyncio.wait_for(run(args.host, args.port), timeout=180))
    finally:
        path = Path(f'bot_monster_initiative_{datetime.now():%Y-%m-%d_%H%M%S}.log')
        path.write_text('\n'.join(transcript) + '\n')
        passed = sum(ok for ok, _ in results)
        print(f'\n{passed}/{len(results)} checks passed -- transcript: {path}')


if __name__ == '__main__':
    main()
