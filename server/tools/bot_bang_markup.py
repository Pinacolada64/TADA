#!/usr/bin/env python3
"""bot_bang_markup.py -- live check that '!' works like '|' as color markup
on every terminal (markup_tokens.py), over real sockets.

Self-contained, same pattern as tools/bot_follow_me.py: seeds two throwaway
characters into a fresh temporary save directory, starts its own
tools/run_throwaway_server.py on it, runs the scenario, shuts it down.

  botansi   connects as an ANSI terminal
  botplain  connects as a plain-text terminal
Both stand in level 1 room 41.

Checks:
  A  botplain SAYs "!red!a ruby!reset! -- Wow!great! Welcome, Alice!";
     botansi receives real ANSI red/reset codes around "a ruby", and the
     ordinary '!'s ("Wow!great!", "Alice!") arrive untouched
  B  botplain's own echo is clean plain text: no markup, '!'s intact
  C  '|red|' and '!red!' give byte-identical ANSI output
  D  an escaped "!!red!!" arrives as the literal "!red!" for both

Usage:
    .venv/bin/python tools/bot_bang_markup.py [--port 34198] [--keep-dir]

Written 2026-10-07.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))
sys.path.insert(0, str(_SERVER_DIR / 'tools'))

from bot_helpstaff import start_server   # same throwaway-server launcher

PASSWORD = 'bang-markup-bots'
ROOM = 41
RED = '\x1b[31m'

transcript: list[str] = []
failures: list[str] = []


def log(text: str = '') -> None:
    print(text)
    transcript.append(text)


def check(label: str, ok: bool, detail: str = '') -> None:
    log(f'{"PASS" if ok else "FAIL"}  {label}' + (f'\n      {detail}' if detail else ''))
    if not ok:
        failures.append(label)


def seed_accounts(save_dir: Path) -> None:
    import net_common
    net_common.run_server_dir = str(save_dir)
    from base_classes import Gender, PlayerClass
    from player import Player
    (save_dir / 'net').mkdir(parents=True, exist_ok=True)
    for name in ('botansi', 'botplain'):
        player = Player(id=name, name=name, char_class=PlayerClass.FIGHTER,
                        gender=Gender.MALE, map_level=1, map_room=ROOM)
        player.creation_done = True
        player.hit_points = 500
        player.unsaved_changes = True
        if not player.save(force=True):
            raise RuntimeError(f'could not save {name}')
        (save_dir / 'net' / f'login-{name}.json').write_text(
            json.dumps({'password': net_common.hash_password(PASSWORD)}))


class Bot:
    """Minimal JSON-protocol client; `terminal` is the letter answered at
    the terminal-type prompt ('A' ANSI, 'P' plain)."""

    def __init__(self, name: str, terminal: str):
        self.name, self.terminal = name, terminal
        self.lines: list[str] = []
        self.last_prompt = ''

    async def recv(self, timeout: float):
        try:
            raw = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        if not raw:
            return None
        msg = json.loads(raw)
        lines = msg.get('lines', [])
        for line in [lines] if isinstance(lines, str) else lines:
            if line:
                self.lines.append(line)
                log(f'  [{self.name}] {line!r}')
        self.last_prompt = msg.get('prompt', '') or ''
        return msg

    async def send(self, line: str, mode: str = 'game') -> None:
        log(f'  [{self.name}] -> {line!r}')
        self.writer.write(json.dumps({'lines': [line], 'mode': mode}).encode() + b'\n')
        await self.writer.drain()

    def at_main(self) -> bool:
        return self.last_prompt.rstrip().endswith('main>')

    async def connect(self, port: int) -> None:
        self.reader, self.writer = await asyncio.open_connection('127.0.0.1', port)
        init = await self.recv(5)
        self.writer.write(json.dumps({'server_id': init.get('server_id', 'test_server'),
                                      'server_key': init.get('server_key', 'test_key')}).encode() + b'\n')
        for _ in range(60):
            if self.last_prompt.rstrip().endswith('login>'):
                break
            if await self.recv(5) is None:
                raise RuntimeError(f'{self.name}: no login prompt')
            low = self.last_prompt.lower()
            if 'terminal type' in low:
                await self.send(self.terminal, 'login')
            elif '-- more' in low or '-- end' in low:
                await self.send('', 'login')
        await self.send(f'connect {self.name} {PASSWORD}')
        for _ in range(60):
            if await self.recv(6) is None:
                raise RuntimeError(f'{self.name}: login stalled')
            if self.at_main():
                return
            if self.last_prompt and self.last_prompt.strip() not in ('main', 'login'):
                await self.send('')

    async def settle(self, quiet: float = 1.0) -> list[str]:
        start = len(self.lines)
        while await self.recv(quiet) is not None:
            pass
        return self.lines[start:]

    async def quit(self) -> None:
        await self.send('quit')
        for _ in range(20):
            if await self.recv(3) is None:
                break
            if 'leave' in self.last_prompt.lower():
                await self.send('Y')
        self.writer.close()


def joined(lines) -> str:
    return ' '.join(' '.join(lines).split())


async def scenario(port: int) -> None:
    ansi, plain = Bot('botansi', 'A'), Bot('botplain', 'P')
    for b in (ansi, plain):
        log(f'\n== {b.name} logs in')
        await b.connect(port)
    for b in (ansi, plain):
        await b.settle(0.5)

    log('\n== A/B: botplain says it with !red!')
    said = '!red!a ruby!reset! -- Wow!great! Welcome, Alice!'
    await plain.send(f'say {said}')
    echo = await plain.settle()
    heard = await ansi.settle()
    # |reset| returns to the player's own PREFS text color (e.g. \x1b[37m),
    # not necessarily the terminal default \x1b[39m -- any SGR code counts.
    import re
    check('A the ANSI player gets real red/reset codes around "a ruby"',
          any(re.search(re.escape(RED) + r'a ruby\x1b\[\d+m', l) for l in heard), repr(heard))
    check("A ordinary '!'s arrive untouched for the ANSI player",
          'Wow!great! Welcome, Alice!' in joined(heard) and '!red!' not in joined(heard),
          repr(heard))
    check("B the plain-text echo is clean, '!'s intact",
          'a ruby -- Wow!great! Welcome, Alice!' in joined(echo)
          and '!red!' not in joined(echo) and '\x1b' not in joined(echo), repr(echo))

    log("\n== C: '|red|' and '!red!' give identical ANSI output")
    await plain.send('say |red|same|reset| x')
    pipe = [l for l in await ansi.settle() if 'same' in l]
    await plain.settle(0.3)
    await plain.send('say !red!same!reset! x')
    bang = [l for l in await ansi.settle() if 'same' in l]
    await plain.settle(0.3)
    check("C identical bytes for | and !", bool(pipe) and pipe == bang, f'{pipe!r} vs {bang!r}')

    log('\n== D: an escaped !!red!! shows literally')
    await ansi.send('say Type !!red!!word!!reset!! for red')
    ansi_echo = await ansi.settle()
    plain_heard = await plain.settle()
    check('D both see the literal "!red!word!reset!"',
          '!red!word!reset!' in joined(ansi_echo) and '!red!word!reset!' in joined(plain_heard)
          and RED not in joined(ansi_echo), f'{ansi_echo!r} | {plain_heard!r}')

    for b in (ansi, plain):
        await b.quit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Live check: '!' markup on every terminal")
    parser.add_argument('--port', type=int, default=34198)
    parser.add_argument('--keep-dir', action='store_true')
    args = parser.parse_args()

    save_dir = Path(tempfile.mkdtemp(prefix='tada-bang-markup-'))
    seed_accounts(save_dir)
    server = start_server(save_dir, args.port)
    try:
        asyncio.run(scenario(args.port))
    finally:
        server.terminate()
        server.wait(timeout=10)
        (save_dir / 'bot_bang_markup.log').write_text('\n'.join(transcript) + '\n')
        if args.keep_dir:
            print(f'\nsave dir and log kept: {save_dir}')
        else:
            shutil.rmtree(save_dir, ignore_errors=True)

    print('\nall passed' if not failures else f'\n{len(failures)} failed: {failures}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
