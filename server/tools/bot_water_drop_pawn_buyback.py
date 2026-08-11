#!/usr/bin/env python3
"""bot_water_drop_pawn_buyback.py — Live end-to-end demo of the pawn-shop
buy-back feature: botdummy buys a metal weapon (or reuses one it already
owns), teleports to a water room, DROPs it so it sinks, then walks to Ye
Olde Pawn Shoppe and buys it back from the new [B]uy option.

Exercises, against a real running server (not a unit test double):
  - commands/drop.py's water-room sink path feeding shoppe/pawn.py's new
    server.pawn_stock (add_to_stock()).
  - shoppe/pawn.py's new [B]uy menu option and its price*40 buy-back.
  - The drop.py dropped_quantity fix (Inventory.remove() decrements
    entry.quantity IN PLACE -- reading it after remove() used to always
    see 0; every water-room-sunk item's pawn_stock entry would otherwise
    silently carry quantity=0, and inv.add(item, 0) is a silent no-op).

Setup
-----
Run tools/setup_bot_accounts.py first (creates botdummy). Point this at a
disposable server instance, same as bot_horse_journey.py -- it spends
botdummy's real gold and mutates its real inventory:

    .venv/bin/python simple_server.py --port 34090 --petscii-port 34091 &

Usage
-----
    .venv/bin/python tools/bot_water_drop_pawn_buyback.py [--host HOST] [--port PORT] [--room N]

--room overrides the water room used (default: level 2, room 7 --
"Underground Stream", level_2.json's flags: ["water"]).
"""
from __future__ import annotations

import asyncio
import argparse
import json
import re
import textwrap
from datetime import datetime
from pathlib import Path

from bot_credentials import load_password

HOST  = '127.0.0.1'
PORT  = 34083
WIDTH = 78
LOG_FILE = Path(__file__).resolve().parent.parent / f'bot_water_drop_pawn_buyback_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.log'

_PASSWORD    = load_password()
_WATER_LEVEL = 2
_WATER_ROOM  = 8     # "Underground Stream" -- level_2.json's 'number' field
                      # (not list index! level_2.json's rooms are a JSON list
                      # whose position != its own 'number' field -- #<level> <room>
                      # teleports by 'number', room 8 is index 7's neighbor)
_DAGGER_NUM  = 7     # weapons.json #7 DAGGER, 75s -- metal, sinks (drop.py's _SINK_KEYWORDS has no
                      # match on "DAGGER" itself, but WEAPON category + no wood keyword -> sinks)

_logfile = None


def _log(text: str = '') -> None:
    print(text)
    if _logfile is not None:
        _logfile.write(text + '\n')
        _logfile.flush()


def _plain(text: str) -> str:
    """Strip [X] hotkey brackets and lowercase, so a check like 'weaponry'
    in the prompt actually matches '[W]eaponry?' -- bot_horse_journey.py's
    lesson #1 ("'attack' in '[a]ttack'" is False) applies to every one of
    this shop's bracketed-hotkey menus (Armory, Buy/Sell, Pawn Shoppe),
    not just combat's [A]ttack."""
    return re.sub(r'[\[\]]', '', text).lower()


def _text_of(msg: dict) -> str:
    lines = msg.get('lines', [])
    if isinstance(lines, str):
        lines = [lines]
    return '\n'.join(str(l) for l in lines if l)


class Bot:
    """Perceive -> update-belief -> decide loop, same pattern as
    bot_horse_journey.py -- see that file's docstring for why this beats
    a fixed-line scripted send/sleep/assume bot."""

    def __init__(self, label: str, user: str):
        self.label = label
        self.user = user
        self.reader = None
        self.writer = None
        self.last_prompt = ''
        self.done = False
        # Belief state
        self.sank = False
        self.floated = False
        self.stock_seen: list[str] = []
        self.bought_ok = False
        self.silver_seen: int | None = None

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
        for line in ([msg.get('lines')] if isinstance(msg.get('lines'), str) else msg.get('lines', [])) or []:
            for wrapped in textwrap.wrap(str(line), WIDTH) or [str(line)]:
                _log(f'  [{self.label}] {wrapped}')
        prompt = msg.get('prompt', '') or ''
        if prompt:
            _log(f'  [{self.label}] [{prompt}]')
        self.last_prompt = prompt
        self._update_belief(_text_of(msg))
        return msg

    async def say(self, line: str) -> None:
        _log(f'\n  [{self.label}] -> {line!r}')
        await self._send({'lines': [line], 'mode': 'game'})

    @property
    def plain_prompt(self) -> str:
        return _plain(self.last_prompt)

    def is_main_prompt(self) -> bool:
        return self.last_prompt.rstrip().endswith('main>')

    def is_shoppe_prompt(self) -> bool:
        # Real wire value is "[HH:MM] Shoppe> ", same timestamp-prefix
        # gotcha bot_horse_journey.py's is_main_prompt() already documents
        # -- an exact 'shoppe' equality check silently never matches.
        return self.last_prompt.rstrip().lower().endswith('shoppe>')

    async def close(self) -> None:
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    def _update_belief(self, text: str) -> None:
        low = text.lower()
        if 'hits the water and sinks' in low:
            self.sank = True
        if 'floats on the surface' in low:
            self.floated = True
        if 'in the back room:' in low:
            self.stock_seen = []
        if low.strip().startswith(tuple(f'{n:>3}.' for n in range(1, 40))) or \
           (low.strip() and low.strip()[0].isdigit() and '.' in low[:6]):
            self.stock_seen.append(text.strip())
        if 'sold! ya-betcha!' in low:
            self.bought_ok = True

    async def drain_until(self, stop: callable, *, max_msgs: int = 60, timeout: float = 4.0) -> bool:
        for _ in range(max_msgs):
            msg = await self._recv_one(timeout=timeout)
            if msg is None:
                return False
            if stop(self):
                return True
        return False


async def _enter_shoppe(bot: Bot) -> bool:
    await bot.say('#1')
    if not await bot.drain_until(lambda b: b.is_main_prompt()):
        return False
    await bot.say('d')
    return await bot.drain_until(lambda b: b.is_shoppe_prompt())


async def _leave_shoppe(bot: Bot) -> bool:
    await bot.say('x')
    return await bot.drain_until(lambda b: b.is_main_prompt())


async def buy_dagger_if_needed(bot: Bot) -> bool:
    """Check inventory for an already-owned metal weapon; if none, buy a
    Dagger from the Armory. Returns True if botdummy is now carrying one."""
    await bot.say('inv')
    if not await bot.drain_until(lambda b: b.is_main_prompt()):
        return False
    # (We don't parse the inv listing precisely -- just try the Armory
    # buy path; if botdummy already owns 6 weapons, the shop's own "no
    # room, sell one?" branch will fire and we bail out cleanly below
    # rather than guessing which owned weapon to reuse.)

    if not await _enter_shoppe(bot):
        _log(f'  [{bot.label}] never reached the Shoppe prompt')
        return False

    await bot.say('a')
    if not await bot.drain_until(lambda b: 'weaponry' in b.plain_prompt):
        _log(f'  [{bot.label}] armory did not open as expected')
        return False
    await bot.say('w')
    if not await bot.drain_until(lambda b: 'buy' in b.plain_prompt and 'sell' in b.plain_prompt):
        return False
    await bot.say('b')
    got_choice = await bot.drain_until(
        lambda b: 'your choice' in b.plain_prompt or 'sell a weapon' in b.plain_prompt)
    if not got_choice:
        return False
    if 'sell a weapon' in bot.plain_prompt:
        _log(f'  [{bot.label}] weapon rack already full -- declining to sell, aborting buy step')
        await bot.say('n')
        await bot.drain_until(lambda b: b.is_shoppe_prompt())
        await _leave_shoppe(bot)
        return False

    await bot.say(str(_DAGGER_NUM))
    if not await bot.drain_until(lambda b: 'try it out' in b.plain_prompt):
        return False
    await bot.say('n')
    if not await bot.drain_until(lambda b: 'buy it' in b.plain_prompt):
        return False
    await bot.say('y')
    if not await bot.drain_until(lambda b: 'your choice' in b.plain_prompt):
        return False
    await bot.say('q')
    if not await bot.drain_until(lambda b: 'buy' in b.plain_prompt and 'sell' in b.plain_prompt):
        return False
    await bot.say('q')
    if not await bot.drain_until(lambda b: b.is_shoppe_prompt()):
        return False
    return await _leave_shoppe(bot)


async def drop_in_water(bot: Bot, level: int, room: int) -> bool:
    await bot.say(f'#{level} {room}')
    if not await bot.drain_until(lambda b: b.is_main_prompt()):
        return False
    await bot.say('drop dagger')
    await bot.drain_until(lambda b: b.is_main_prompt())
    return bot.sank


async def buy_back_at_pawn_shop(bot: Bot) -> bool:
    if not await _enter_shoppe(bot):
        _log(f'  [{bot.label}] never reached the Shoppe prompt')
        return False

    await bot.say('v')
    # botdummy is ADMIN/debug-mode-flagged -- debug_tools.debug_toggle_once_per_day()
    # asks "Add 'pawn shoppe' to once-per-day activities? Y/N" the first time this
    # session before the real menu shows. Answering N (declining) falls through to
    # the normal menu; not anticipating this prompt at all desyncs every send after
    # it, same failure mode bot_horse_journey.py's docstring warns about.
    if not await bot.drain_until(lambda b: ('sell' in b.plain_prompt and 'buy' in b.plain_prompt)
                                  or 'y/n' in b.plain_prompt):
        _log(f'  [{bot.label}] pawn shoppe prompt never showed [B]uy -- did it close for today?')
        return False
    if 'y/n' in bot.plain_prompt:
        await bot.say('n')
        if not await bot.drain_until(lambda b: 'sell' in b.plain_prompt and 'buy' in b.plain_prompt):
            _log(f'  [{bot.label}] pawn shoppe prompt never showed [B]uy after declining debug prompt')
            return False

    await bot.say('b')
    if not await bot.drain_until(lambda b: 'buy which item' in b.plain_prompt
                                  or "nothing's turned up" in b.plain_prompt
                                  or 'nothing' in b.plain_prompt):
        return False
    if 'buy which item' not in bot.plain_prompt:
        _log(f'  [{bot.label}] back room was empty -- the sunk Dagger never made it into stock')
        return False

    _log(f'  [{bot.label}] back-room stock seen: {bot.stock_seen}')
    await bot.say('1')
    if not await bot.drain_until(lambda b: 'hoky-doky' in b.plain_prompt):
        return False
    await bot.say('y')
    if not await bot.drain_until(lambda b: 'sell' in b.plain_prompt and 'buy' in b.plain_prompt):
        return False
    await bot.say('q')
    if not await bot.drain_until(lambda b: b.is_shoppe_prompt()):
        return False
    await _leave_shoppe(bot)
    return bot.bought_ok


async def main(host: str, port: int, level: int, room: int) -> None:
    global _logfile
    _logfile = LOG_FILE.open('w', encoding='utf-8')
    _log(f'# bot_water_drop_pawn_buyback session  {datetime.now().isoformat(timespec="seconds")}')
    _log(f'# {host}:{port}  water room: level {level}, room {room}')

    bot = Bot('botdummy', 'botdummy')
    if not await bot.connect(host, port):
        return
    await bot.say(f'connect {bot.user} {_PASSWORD}')
    await bot.drain_until(lambda b: b.is_main_prompt())

    have_dagger = await buy_dagger_if_needed(bot)
    _log(f'\n  [botdummy] *** dagger in hand: {have_dagger} ***')
    if not have_dagger:
        await bot.close()
        _log('\n  Aborted -- could not acquire a Dagger to sink.')
        return

    sank = await drop_in_water(bot, level, room)
    _log(f'\n  [botdummy] *** drop in water room {level}:{room} sank: {sank} ***')

    bought = await buy_back_at_pawn_shop(bot) if sank else False
    _log(f'\n  [botdummy] *** pawn-shop buy-back {"SUCCEEDED" if bought else "FAILED"} ***')

    await bot.say('inv')
    await bot.drain_until(lambda b: b.is_main_prompt())

    await bot.close()
    _log(f'\n{"=" * WIDTH}\n  Session complete.\n{"=" * WIDTH}\n# log written to {LOG_FILE}')
    _logfile.close()
    print(f'Log saved to {LOG_FILE}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TADA water-drop / pawn-shop buy-back live demo')
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--level', type=int, default=_WATER_LEVEL)
    parser.add_argument('--room', type=int, default=_WATER_ROOM)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.level, args.room))
