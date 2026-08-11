#!/usr/bin/env python3
"""bot_desert_compass.py — Live demo of encounters/desert.py's desert/
labyrinth compass-navigation mechanic against a real running TADA server.

Reactive: reads one message at a time, updates a small belief-state by
pattern-matching the server's actual reply text, and only then decides its
next move -- same perceive/update-belief/decide loop as bot_horse_journey.py
(see that module's docstring for why: a fixed-sleep scripted bot silently
desyncs from the server's real timing and RNG the moment anything doesn't
go exactly as guessed).

What this demonstrates, phase by phase
---------------------------------------
1. No compass, in "The Desert" (level 5 room 2): exits are hidden --
   "You lost your sense of direction." -- instead of "Ye may travel: ...".
2. USE compass, look again: exits reappear, prefixed with the
   "[COMPASS READ]"-equivalent... actually this port doesn't print that
   flavor line (see encounters/desert.py), just the exit list itself.
3. Walk east several times through more Desert rooms (still compassed) and
   watch for "You sweat in the heat." -- SPUR.MAIN.S's ~30%-per-move thirst
   drain, DESERT-room-only.
4. Move into room 54 ("The Desert", monster #77 SCORPION) and fight with
   the compass still active, watching for "Compass damaged!" -- SPUR.COMBAT.S
   "druid" label's 5%-per-landed-hit compass-destruction roll. Probabilistic:
   the bot budgets a generous number of rounds, but honestly reports
   "not observed" rather than assuming/faking a hit if the roll never lands.
5. Toggle Debug Mode on (DBG command) and confirm exits are visible in the
   Desert with no compass at all -- the port-only debug bypass
   encounters/desert.py's can_sense_direction() grants, no SPUR precedent.

Setup
-----
Run tools/setup_bot_accounts.py first (creates botdesert pre-seeded with a
compass + DAGGER, standing in level 5 room 2 "The Desert", Debug Mode off,
Wisdom+Intelligence forced to 14+14 so the low-stat "always at risk"
branch doesn't confound the demo). Point this at a server instance you
don't mind mutating -- safest against a disposable second instance:

    .venv/bin/python simple_server.py --port 34090 --petscii-port 34091 &

Usage
-----
    .venv/bin/python tools/bot_desert_compass.py [--host HOST] [--port PORT]
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
PORT  = 34090
WIDTH = 78
LOG_FILE = Path(__file__).resolve().parent.parent / f'bot_desert_compass_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.log'

_PASSWORD = load_password()   # tools/.bot_credentials.json (gitignored)
_FIGHT_ROOM = 54              # level 5, "The Desert", monster #77 SCORPION
_MAX_FIGHT_ROUNDS = 120       # budget for the compass-damage roll (~5%/hit)

_logfile = None


def _log(text: str = '') -> None:
    print(text)
    if _logfile is not None:
        _logfile.write(text + '\n')
        _logfile.flush()


def _wrap_send(label: str, text: str) -> None:
    _log(f'\n  [{label}] -> {text!r}')


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


# ---------------------------------------------------------------------------
# Reactive bot
# ---------------------------------------------------------------------------

class Bot:
    """One connection, driven by a perceive -> update-belief -> decide loop."""

    def __init__(self, label: str, user: str):
        self.label = label
        self.user = user
        self.reader = None
        self.writer = None

        # Belief state, updated only from real message content.
        self.alive = True
        self.in_combat = False
        self.last_prompt = ''
        self.done = False

        # Desert-mechanic-specific belief flags -- reset before each phase
        # that checks for them, so a stale True from an earlier phase can't
        # be mistaken for this phase's own evidence.
        self.saw_lost_direction = False
        self.saw_star_blackness = False
        self.saw_exits_line = False
        self.saw_sweat = False
        self.saw_compass_damaged = False
        self.compass_active = False

    # -- transport -----------------------------------------------------

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
        """Read exactly one message, update belief-state from its content, log it."""
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
        self._update_belief(_text_of(msg))
        return msg

    async def say(self, line: str) -> None:
        _wrap_send(self.label, line)
        await self._send({'lines': [line], 'mode': 'game'})

    def is_main_prompt(self) -> bool:
        """The real wire value bakes a '[HH:MM] ' timestamp into the prompt
        string (e.g. '[17:32] main> ') -- an exact-equality check against
        'main> ' silently never matches. See bot_horse_journey.py's own
        note on this same gotcha."""
        return self.last_prompt.rstrip().endswith('main>')

    async def close(self) -> None:
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    # -- belief update ---------------------------------------------------

    def _update_belief(self, text: str) -> None:
        low = text.lower()
        if 'combat begins!' in low:
            self.in_combat = True
        if 'has been slain by' in low and self.user.lower() in low:
            self.alive = False
            self.in_combat = False
        if 'you lost your sense of direction' in low:
            self.saw_lost_direction = True
        if 'star-filled blackness engulfs you' in low:
            self.saw_star_blackness = True
        if 'ye may travel' in low:
            self.saw_exits_line = True
        if 'you sweat in the heat' in low:
            self.saw_sweat = True
        if 'compass damaged' in low:
            self.saw_compass_damaged = True
            self.compass_active = False
        if 'compass used' in low:
            self.compass_active = True
        if 'compass placed in pack' in low:
            self.compass_active = False

    async def drain_until(self, stop: callable, *, max_msgs: int = 60, timeout: float = 4.0) -> bool:
        """Same contract as bot_horse_journey.py's Bot.drain_until(): keeps
        reading until `stop(self)` fires, and returns False (not True) on a
        timeout/quiet-stream/closed-connection give-up -- callers must check
        this before treating "no error" as "the thing we waited for happened".

        Transparently answers network_context.py's MORE_PROMPT pagination
        ("-- More [1/2] [?=help] --", Enter/Q to continue/skip) with 'Q' --
        botdesert's news feed at login is long enough to paginate, and a
        naive drain_until would just sit there re-reading the same "-- More
        --" prompt over and over until it exhausts max_msgs/timeout, never
        reaching the real main prompt underneath it.
        """
        for _ in range(max_msgs):
            msg = await self._recv_one(timeout=timeout)
            if msg is None:
                return False
            if stop(self):
                return True
            low_prompt = self.last_prompt.lower()
            if '-- more' in low_prompt or '-- end' in low_prompt:
                await self.say('Q')
        return False


# ---------------------------------------------------------------------------
# Demo phases
# ---------------------------------------------------------------------------

async def phase_no_compass(bot: Bot) -> bool:
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 1: no compass, in The Desert -- exits should be hidden\n{"#" * WIDTH}')
    bot.saw_lost_direction = False
    bot.saw_exits_line = False
    await bot.say('look')
    await bot.drain_until(lambda b: b.is_main_prompt())

    ok = bot.saw_lost_direction and not bot.saw_exits_line
    _log(f'\n  *** PHASE 1 {"PASSED" if ok else "FAILED"}: '
         f'saw "lost your sense of direction"={bot.saw_lost_direction}, '
         f'saw "Ye may travel"={bot.saw_exits_line} ***')
    return ok


async def phase_with_compass(bot: Bot) -> bool:
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 2: USE compass, look again -- exits should reappear\n{"#" * WIDTH}')
    await bot.say('use compass')
    await bot.drain_until(lambda b: b.is_main_prompt())

    if not bot.compass_active:
        _log(f'  [{bot.label}] *** compass never registered as active -- aborting phase 2 ***')
        return False

    bot.saw_lost_direction = False
    bot.saw_exits_line = False
    await bot.say('look')
    await bot.drain_until(lambda b: b.is_main_prompt())

    ok = bot.saw_exits_line and not bot.saw_lost_direction
    _log(f'\n  *** PHASE 2 {"PASSED" if ok else "FAILED"}: '
         f'saw "Ye may travel"={bot.saw_exits_line}, '
         f'saw "lost your sense of direction"={bot.saw_lost_direction} ***')
    return ok


async def phase_sweat(bot: Bot) -> bool:
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 3: walk east repeatedly through Desert rooms -- watch for the heat/thirst drain\n{"#" * WIDTH}')
    bot.saw_sweat = False
    sweat_count = 0
    moves = 8   # room 2 -> room 9, the real east-exit chain through desert terrain (level_5.json)
    for i in range(moves):
        bot.saw_sweat = False
        await bot.say('e')
        await bot.drain_until(lambda b: b.is_main_prompt())
        if bot.saw_sweat:
            sweat_count += 1

    rate = sweat_count / moves
    _log(f'\n  *** PHASE 3 complete: "You sweat in the heat." fired {sweat_count}/{moves} moves '
         f'({rate:.0%}, SPUR expects ~30%) ***')
    return sweat_count > 0


async def _fight_once(bot: Bot, room: int, round_budget: int) -> int:
    """Fight whatever's in *room* until it ends, replying 'N' to any ally
    join-offer that follows a kill so it doesn't dangle unanswered into the
    next phase. Returns rounds actually swung (<= round_budget)."""
    await bot.say(f'#{room}')
    await bot.drain_until(lambda b: b.is_main_prompt())
    await bot.say('ready dagger')
    await bot.drain_until(lambda b: b.is_main_prompt())

    await bot.say('attack')
    rounds = 0
    combat_seen = False
    while rounds < round_budget:
        msg = await bot._recv_one(timeout=3.0)
        if msg is None or bot.done:
            break
        if bot.in_combat:
            combat_seen = True
        if not bot.alive:
            _log(f'  [{bot.label}] died mid-fight')
            break
        if combat_seen and bot.is_main_prompt():
            break   # monster died, fled, or fight otherwise ended
        # Deliberately keep fighting to a natural conclusion even after
        # saw_compass_damaged fires -- breaking out mid-fight would leave
        # the CombatSession open, and the next phase's first command would
        # get swallowed as a combat round input instead of a real command
        # (bit a live run this same session: 'dbg' sent into a still-open
        # fight just became another attack round).
        #
        # combat/engine.py's per-round prompt is 'Command> ' (ctx.prompt(
        # 'Command', ...)); blank input defaults to Attack (combat/engine.py:
        # cmd = (raw.strip().lower() or 'a')[0]).
        if 'command' in bot.last_prompt.lower():
            await bot.say('')
            rounds += 1

    # A kill can trigger an ally join-offer ("Let them join? (Y/N)") that
    # otherwise dangles unanswered and desyncs every command sent after it
    # (see this repo's CLAUDE.md note on exactly this failure mode) --
    # decline it so the next room/phase starts from a clean main prompt.
    if 'join' in bot.last_prompt.lower() and '(y/n)' in bot.last_prompt.lower():
        await bot.say('N')
        await bot.drain_until(lambda b: b.is_main_prompt())

    return rounds


async def phase_compass_damage(bot: Bot) -> bool:
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 4: fight Desert monsters with compass active -- watch for "Compass damaged!"\n{"#" * WIDTH}')
    if not bot.compass_active:
        _log(f'  [{bot.label}] *** compass not active going into the fight -- results would not be meaningful ***')
        return False

    # Each SCORPION/monster only yields a handful of swings before dying,
    # and the compass-damage roll is only ~5% per landed hit -- one fight's
    # worth of hits gives poor odds of ever seeing it fire. Chain through
    # several known Desert-with-monster rooms (level_5.json) to get a much
    # larger sample of hits within one demo run.
    candidate_rooms = (54, 301, 344, 371)   # all "The Desert", each with a live monster
    total_rounds = 0
    for room in candidate_rooms:
        if bot.saw_compass_damaged or total_rounds >= _MAX_FIGHT_ROUNDS:
            break
        budget = _MAX_FIGHT_ROUNDS - total_rounds
        total_rounds += await _fight_once(bot, room, budget)

    _log(f'\n  *** PHASE 4 complete after ~{total_rounds} rounds across up to {len(candidate_rooms)} rooms: '
         f'"Compass damaged!" {"OBSERVED" if bot.saw_compass_damaged else "not observed"} '
         f'(probabilistic -- SPUR expects ~5% per landed hit, not a guarantee within any fixed budget) ***')
    return bot.saw_compass_damaged


async def phase_debug_bypass(bot: Bot) -> bool:
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 5: toggle Debug Mode on -- exits should be visible even with no compass\n{"#" * WIDTH}')
    if bot.compass_active:
        await bot.say('use compass')   # toggle off -- USE compass is a straight on/off flip
        await bot.drain_until(lambda b: b.is_main_prompt())
    if bot.compass_active:
        _log(f'  [{bot.label}] *** compass still shows active -- phase 5 results would not be meaningful ***')

    await bot.say('dbg')
    await bot.drain_until(lambda b: b.is_main_prompt())

    bot.saw_lost_direction = False
    bot.saw_exits_line = False
    await bot.say('look')
    await bot.drain_until(lambda b: b.is_main_prompt())

    ok = bot.saw_exits_line and not bot.saw_lost_direction
    _log(f'\n  *** PHASE 5 {"PASSED" if ok else "FAILED"}: '
         f'saw "Ye may travel"={bot.saw_exits_line}, '
         f'saw "lost your sense of direction"={bot.saw_lost_direction} '
         f'(no compass, Debug Mode on) ***')
    return ok


async def main(host: str, port: int) -> None:
    global _logfile
    _logfile = LOG_FILE.open('w', encoding='utf-8')
    _log(f'# bot_desert_compass session  {datetime.now().isoformat(timespec="seconds")}')
    _log(f'# {host}:{port}')

    bot = Bot('botdesert', 'botdesert')
    if not await bot.connect(host, port):
        _logfile.close()
        return
    await bot.say(f'connect {bot.user} {_PASSWORD}')
    await bot.drain_until(lambda b: b.is_main_prompt())

    results = {}
    results['no_compass_hides_exits'] = await phase_no_compass(bot)
    results['compass_reveals_exits']  = await phase_with_compass(bot)
    results['desert_heat_drain']      = await phase_sweat(bot)
    results['compass_combat_damage']  = await phase_compass_damage(bot)
    results['debug_bypass']           = await phase_debug_bypass(bot)

    await bot.close()

    _log(f'\n{"=" * WIDTH}\n  SUMMARY\n{"=" * WIDTH}')
    for name, ok in results.items():
        _log(f'  {"PASS" if ok else "FAIL/NOT OBSERVED"}  {name}')
    _log(f'\n# log written to {LOG_FILE}')
    _logfile.close()
    print(f'Log saved to {LOG_FILE}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TADA desert-compass reactive bot demo')
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
