#!/usr/bin/env python3
"""tools/bot_crowd.py — a crowd of guest bots, each with its own habit,
for stress-testing a live server (and giving a watching client -- the
C128 client over SwiftLink, tada_client.py -- a busy world to show).

Each bot logs in as a guest on the JSON port and runs one persona:

  chatter    says something every few seconds
  wanderer   walks a random exit from the room it's in
  census     runs 'who'
  shouter    exclaims things (say ...!)
  greeter    answers other players' speech, rate-limited
  packrat    get guide / inv / drop guide
  bookworm   read guide / look
  clock      checks the time
  explorer   walks, then says the name of the room it reached
  idler      looks around now and then, otherwise sits

Every command waits for the server's full prompt (one ending in "> " --
the reply's lines come with a short "main" prompt first, then the real
"[HH:MM] main> " one; see bot_horse_journey.py's header on why exact
prompt matches don't work) before the bot decides its next move, and
any other prompt (-- More --, a shop menu) is answered with 'q' until
the bot is back at a game prompt. Bots connect a second apart so the
login rush doesn't all land at once.

Written 2026-09-29 for the C128 SwiftLink stress test.
Usage: python3 tools/bot_crowd.py [--host H] [--port P] [--count N]
                                  [--minutes M]
"""
import argparse
import asyncio
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot_client import _recv, _send

CHATTER = [
    'Anyone seen the Adventurer\'s Guide around here?',
    'I hear the market has good prices today.',
    'This lobby echoes a lot.',
    'Who left the torch burning?',
    'Watch your step near the stairs.',
    'Has anyone been past cavern head?',
    'My feet hurt from all this walking.',
    'I think I saw a rat in the annex.',
]
SHOUTS = [
    'Fresh adventurers, get your fresh adventurers',
    'Stress test in progress',
    'The Commodore 128 is watching',
    'Mind the gap',
    'Huzzah',
]
DIRS = {'north': 'n', 'south': 's', 'east': 'e', 'west': 'w',
        'up': 'u', 'down': 'd'}


def lines_of(msg: dict) -> list:
    lines = msg.get('lines') or []
    return [lines] if isinstance(lines, str) else lines


class Bot:
    def __init__(self, n: int, persona: str, host: str, port: int):
        self.n, self.persona = n, persona
        self.host, self.port = host, port
        self.name = f'bot{n}'           # replaced by "Guest N" at login
        self.exits: list = []
        self.room = ''
        self.heard: list = []           # (speaker) lines seen since last turn
        self.commands = 0

    def log(self, text: str) -> None:
        print(f'[{time.strftime("%H:%M:%S")}] {self.name:<9} {self.persona:<9} {text}',
              flush=True)

    def absorb(self, msg: dict) -> None:
        """Update beliefs from one message's lines."""
        for line in lines_of(msg):
            plain = re.sub(r'\x1b\[[0-9;]*m', '', line).strip()
            m = re.match(r'Welcome, (Guest \d+)', plain)
            if m:
                self.name = m.group(1)
            m = re.match(r'Ye may travel (.*)', plain)
            if m:
                self.exits = [DIRS[w.lower()] for w in
                              re.findall(r'\b(North|South|East|West|Up|Down)\b', m.group(1))]
            m = re.match(r'([A-Z][A-Z\' ]{2,})\s+\+', plain)
            if m:
                self.room = m.group(1).strip().title()
            m = re.match(r'(.+?) (says|exclaims|asks), "', plain)
            if m and m.group(1) != self.name:
                self.heard.append(m.group(1))

    async def turn(self, reader, writer, cmd: str, mode: str = 'game') -> bool:
        """Send *cmd*, then read until a full game prompt. False = gone."""
        await _send(writer, {'lines': [cmd], 'mode': mode})
        self.commands += 1
        for _ in range(12):             # prompts cleared before giving up
            deadline = time.monotonic() + 8
            prompt = None
            while time.monotonic() < deadline:
                msg = await _recv(reader, timeout=deadline - time.monotonic())
                if msg is None:
                    if reader.at_eof():
                        return False
                    continue
                self.absorb(msg)
                p = msg.get('prompt') or ''
                if p.endswith('> '):
                    prompt = p
                    break
            if prompt is None:
                return True             # quiet -- carry on regardless
            if prompt.rstrip().endswith('main>'):
                return True
            await _send(writer, {'lines': ['q'], 'mode': mode})   # More / menus
        return True

    async def login(self, reader, writer) -> bool:
        init = await _recv(reader, timeout=5)
        if init is None:
            return False
        await _send(writer, {'server_id': init.get('server_id', 'test_server'),
                             'server_key': init.get('server_key', 'test_key')})
        for _ in range(40):
            msg = await _recv(reader, timeout=5)
            if msg is None:
                break
            p = (msg.get('prompt') or '').lower()
            if 'login' in p:
                break
            if 'terminal type' in p:
                await _send(writer, {'lines': ['A'], 'mode': 'login'})
            elif 'more' in p:
                await _send(writer, {'lines': ['q'], 'mode': 'login'})
        return await self.turn(reader, writer, 'connect guest', 'login')

    def next_command(self) -> tuple:
        """(command, seconds to wait afterwards) for this persona."""
        p = self.persona
        if p == 'chatter':
            return f'say {random.choice(CHATTER)}', random.uniform(5, 10)
        if p == 'shouter':
            return f'say {random.choice(SHOUTS)}!', random.uniform(8, 15)
        if p == 'census':
            return 'who', random.uniform(12, 20)
        if p == 'clock':
            return 'time', random.uniform(10, 18)
        if p == 'packrat':
            return random.choice(['get guide', 'inv', 'drop guide', 'inv']), random.uniform(4, 8)
        if p == 'bookworm':
            return random.choice(['read guide', 'look']), random.uniform(8, 14)
        if p == 'idler':
            return 'look', random.uniform(20, 40)
        if p == 'greeter':
            if self.heard:
                who = self.heard.pop(0)
                self.heard.clear()
                return f'say Hello there, {who}!', random.uniform(6, 10)
            return 'look', random.uniform(4, 6)
        if p in ('wanderer', 'explorer'):
            if self.exits:
                return random.choice(self.exits), random.uniform(4, 9)
            return 'look', 2
        return 'look', 10

    async def run(self, until: float) -> None:
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
        except OSError as e:
            self.log(f'connect failed: {e}')
            return
        try:
            if not await self.login(reader, writer):
                self.log('login failed')
                return
            self.log('logged in')
            await self.turn(reader, writer, 'look')
            while time.monotonic() < until:
                cmd, pause = self.next_command()
                before = self.room
                self.log(cmd)
                if not await self.turn(reader, writer, cmd):
                    self.log('disconnected')
                    return
                if self.persona == 'explorer' and self.room and self.room != before:
                    await self.turn(reader, writer, f'say I made it to {self.room}.')
                await asyncio.sleep(pause)
            await self.turn(reader, writer, 'quit')
            self.log(f'quit after {self.commands} commands')
        finally:
            writer.close()


PERSONAS = ['chatter', 'wanderer', 'census', 'shouter', 'greeter',
            'packrat', 'bookworm', 'clock', 'explorer', 'idler']


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=35064,
                    help='JSON port (default: the stress-test server\'s 35064)')
    ap.add_argument('--count', type=int, default=10)
    ap.add_argument('--minutes', type=float, default=5)
    args = ap.parse_args()
    until = time.monotonic() + args.minutes * 60
    bots = [Bot(i + 1, PERSONAS[i % len(PERSONAS)], args.host, args.port)
            for i in range(args.count)]
    tasks = []
    for bot in bots:
        tasks.append(asyncio.create_task(bot.run(until)))
        await asyncio.sleep(1)
    await asyncio.gather(*tasks)
    print(f'done: {sum(b.commands for b in bots)} commands from {len(bots)} bots')


if __name__ == '__main__':
    asyncio.run(main())
