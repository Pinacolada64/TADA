#!/usr/bin/env python3
"""tools/bot_swarm.py — 10 concurrent reactive bots hammering a live server
at once: wandering, PvE combat, PvP duels, page, whisper, groups, shout,
give, loot, item pickup. Built to surface concurrency bugs (races between
simultaneous attackers on the same monster, simultaneous saves, message
interleaving on shared broadcasts) that a single- or two-bot script like
bot_epic_battle.py can't reach.

Ten throwaway accounts (tools/setup_swarm_accounts.py): botswarm01..10,
ADMIN-flagged (for '#<level> <room>' teleport), 500 HP, mixed classes, each
carrying a LONG SWORD (readied live right after login -- see connect flow
below) and 3 large rubies to give away.

Each bot runs its own perceive -> update-belief -> decide loop
(same reactive style as bot_epic_battle.py / bot_horse_journey.py), picking
a weighted-random action every time it's back at the main prompt:
  teleport to a room from ROOM_POOL, attack a monster if one's present,
  walk a bare compass direction, page another random bot (occasionally the
  #friends group instead), whisper to whoever's in the room, shout, look,
  get the room's item, check stats, give a ruby to another bot, loot
  another player in the room, challenge another bot to a duel, or check
  WHO's online / WHEREAT everyone currently is.
Combat is handled generically: whichever bot's 'attack' opens the fight
becomes its leader and answers its own Command> menu with a mostly-attack
policy (occasional flee) until the monster or the bot dies; any other bot
that also sends 'attack' in the same room joins as a bystander instead.
DUEL is handled the same reactive way: a pending challenge auto-accepts
(mostly) or declines, and once a duel is active the bot answers whichever
tactic prompt it's shown (attack/parry/bash, or stand/roll if knocked
down) every time it's back at the main prompt -- see combat/duel.py's
_tactic_prompt(), which re-sends after every round until the duel ends.

Sending a bare 'down' from room 1 (part of the normal 'move' action) can
also land a bot in the Merchant Shoppe menu (commands/movement.py's rc==2
branch) -- handled reactively too: mostly 'X' to leave, occasionally 'E'
to detour through the elevator, which answers its combination prompt with
every account's seeded combo (setup_swarm_accounts.py) and then leaves
via the post-combination floor picker.

Targets tools/run_throwaway_server.py's isolated instance (default
127.0.0.1:34190) -- never the real run/server save directory.

Usage:
    .venv/bin/python tools/run_throwaway_server.py &
    .venv/bin/python tools/setup_swarm_accounts.py
    .venv/bin/python tools/bot_swarm.py [--host HOST] [--port PORT]
                                         [--actions N] [--seed N]

Writes a human-readable transcript to bot_swarm_<timestamp>.log and a
per-bot action-count summary to stdout at the end.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import textwrap
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

HOST  = '127.0.0.1'
PORT  = 34190
WIDTH = 78
_STAMP = datetime.now().strftime("%Y-%m-%d_%H%M%S")
LOG_FILE = Path(__file__).resolve().parent.parent / f'bot_swarm_{_STAMP}.log'

_PASSWORD = 'puppy123'
_BOTS = [f'botswarm{i:02}' for i in range(1, 11)]

# Matches setup_swarm_accounts.py's _ELEVATOR_COMBO -- shoppe/elevator.py's
# get_combination() prompt (Combination [attempt N/5]) shows up whenever a
# bot's random wandering takes it onto an elevator's 'rc' exit.
_ELEVATOR_COMBO = '11-22-33'

# level-1 rooms confirmed in setup: a few social/no-monster rooms plus the
# regular-monster rooms documented in tools/BOT_README.md sec. 6.
ROOM_POOL = [1, 2, 3, 4, 6, 10, 13, 15, 16, 20, 23, 27, 33, 43]

_DIRECTIONS = ['north', 'south', 'east', 'west', 'up', 'down']

_logfile = None
_lock = asyncio.Lock()  # serializes _log() writes across concurrent bots


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


class Bot:
    def __init__(self, label: str):
        self.label = label
        self.user = label
        self.reader = None
        self.writer = None

        self.alive = True
        self.in_combat = False
        self.monster_present = False
        self.monster_dead = False
        self.room_mates: set[str] = set()
        self.last_prompt = ''
        self.done = False
        self.round_no = 0
        self.actions = Counter()

        # PvP duel state (combat/duel.py) -- see _tactic_prompt()'s text,
        # matched in _update_belief below.
        self.duel_pending = False   # someone challenged us; awaiting accept/decline
        self.duel_active = False    # a duel is underway; awaiting our tactic
        self.duel_down = False      # knocked down -- only STAND/ROLL are legal

        self.rubies_left = 3        # matches setup_swarm_accounts.py's _seed_gear
        self.loot_tries = 0

    async def connect(self, host: str, port: int) -> bool:
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
        except ConnectionRefusedError:
            _log(f'  [{self.label}] connection refused -- is the throwaway server running on {port}?')
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
            return None
        if not raw:
            self.done = True
            async with _lock:
                _log(f'  [{self.label}] (connection closed by server)')
            return None
        msg = json.loads(raw.strip())
        async with _lock:
            _wrap_recv(self.label, msg)
        self.last_prompt = msg.get('prompt', '') or ''
        self._update_belief(_text_of(msg))

        # See tools/BOT_README.md / bot_epic_battle.py's docstring: this
        # ctx.prompt() fires mid-round right after any kill and, if left
        # unanswered, desyncs every command sent on this connection for the
        # rest of the run.
        if 'let them join' in self.last_prompt.lower():
            await self._send({'lines': ['N'], 'mode': 'game'})

        return msg

    async def say(self, line: str) -> None:
        async with _lock:
            _log(f'  [{self.label}] -> {line!r}')
        await self._send({'lines': [line], 'mode': 'game'})

    def is_main_prompt(self) -> bool:
        return self.last_prompt.rstrip().endswith('main>')

    def is_command_prompt(self) -> bool:
        return self.last_prompt.rstrip().lower().endswith('command>')

    async def close(self) -> None:
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    def _update_belief(self, text: str) -> None:
        low = text.lower()
        if 'has been slain by' in low and self.user.lower() in low:
            self.alive = False
            self.in_combat = False
        if 'the blast was fatal' in low:
            self.alive = False
        if 'combat begins!' in low:
            self.in_combat = True
        if "you're not in a fight" in low or "you're not fighting anything" in low:
            self.in_combat = False
        if 'there is' in low:
            self.monster_present = True
        if ('have slain' in low or 'slays' in low or 'is slain!' in low
                or 'turns to stone as it dies' in low):
            self.monster_dead = True
            self.in_combat = False
            self.monster_present = False

        # --- PvP duel (combat/duel.py) ---
        if 'challenges you to a duel' in low:
            self.duel_pending = True
        if 'choose: duel attack' in low:
            self.duel_active = True
            self.duel_down = False
        if "you're on the ground!" in low:
            self.duel_active = True
            self.duel_down = True
        if ('vanquished' in low or 'flees the duel' in low
                or 'snickers, and waves you on' in low
                or 'declines your challenge' in low):
            self.duel_pending = False
            self.duel_active = False
            self.duel_down = False

    async def drain_until(self, stop: callable, *, max_msgs: int = 200, timeout: float = 5.0) -> bool:
        for _ in range(max_msgs):
            msg = await self._recv_one(timeout=timeout)
            if msg is None:
                return False
            if stop(self):
                return True
        return False


# ---------------------------------------------------------------------------
# Reactive per-bot loop
# ---------------------------------------------------------------------------

async def handle_combat_menu(bot: Bot, rng: random.Random) -> None:
    """Answer one round of the Command> menu (only reachable as a fight's
    leader). Mostly attacks; occasionally flees to exercise that path too."""
    choice = 'f' if rng.random() < 0.05 else 'a'
    await bot.say(choice)


async def do_action(bot: Bot, rng: random.Random) -> None:
    """Pick and perform one weighted-random action from the main prompt."""
    choices = [
        ('teleport', 0.28),
        ('attack',   0.18 if bot.monster_present and not bot.monster_dead else 0.0),
        ('move',     0.14),
        ('page',     0.10),
        ('whisper',  0.09),
        ('look',     0.07),
        ('duel',     0.05 if not bot.duel_active and not bot.duel_pending else 0.0),
        ('get',      0.03),
        ('give',     0.03 if bot.rubies_left > 0 else 0.0),
        ('loot',     0.02 if bot.loot_tries < 2 else 0.0),
        ('who',      0.02),
        ('wa',       0.02),
        ('shout',    0.01),
        ('stats',    0.01),
    ]
    total = sum(w for _, w in choices)
    r = rng.random() * total
    upto = 0.0
    action = 'look'
    for name, w in choices:
        upto += w
        if r <= upto:
            action = name
            break

    bot.actions[action] += 1

    if action == 'teleport':
        room = rng.choice(ROOM_POOL)
        bot.monster_dead = False
        bot.monster_present = False
        await bot.say(f'#1 {room}')
    elif action == 'attack':
        await bot.say('attack')
    elif action == 'move':
        await bot.say(rng.choice(_DIRECTIONS))
    elif action == 'page':
        target = '#friends' if rng.random() < 0.3 else rng.choice([b for b in _BOTS if b != bot.label])
        await bot.say(f'page {target}=hey, anyone else out here?')
    elif action == 'whisper':
        target = '#friends' if rng.random() < 0.3 else rng.choice([b for b in _BOTS if b != bot.label])
        await bot.say(f'whisper {target}=you around?')
    elif action == 'look':
        bot.monster_present = False
        await bot.say('look')
    elif action == 'get':
        await bot.say('get all')
    elif action == 'give':
        target = rng.choice([b for b in _BOTS if b != bot.label])
        bot.rubies_left -= 1
        await bot.say(f'give large ruby to {target}')
    elif action == 'loot':
        bot.loot_tries += 1
        await bot.say('loot')
    elif action == 'duel':
        target = rng.choice([b for b in _BOTS if b != bot.label])
        await bot.say(f'duel {target}')
    elif action == 'who':
        await bot.say('who')
    elif action == 'wa':
        await bot.say('wa')
    elif action == 'shout':
        await bot.say('shout swarm test in progress')
    elif action == 'stats':
        await bot.say('stats')


async def bot_loop(bot: Bot, num_actions: int, seed: int) -> None:
    rng = random.Random(seed)
    stall_count = 0
    while bot.round_no < num_actions and bot.alive and not bot.done:
        msg = await bot._recv_one(timeout=8.0)
        if msg is None:
            if bot.done:
                return
            stall_count += 1
            # Nothing arrived for a while and we're not mid-fight -- nudge
            # the connection back to a known state instead of hanging.
            if stall_count > 2:
                await bot.say('look')
                stall_count = 0
            continue
        stall_count = 0

        low_prompt = bot.last_prompt.lower()
        if bot.is_command_prompt():
            await handle_combat_menu(bot, rng)
        elif 'loot which adventurer' in low_prompt or 'take which item number' in low_prompt:
            # commands/loot.py's two ctx.prompt() selections -- always grab
            # whoever/whatever is first in the list.
            await bot.say('1')
        elif 'combination [attempt' in low_prompt:
            # shoppe/elevator.py's get_combination() -- every swarm account
            # was seeded with the same elevator combo (setup_swarm_accounts.py),
            # so this always succeeds on the first attempt.
            await bot.say(_ELEVATOR_COMBO)
        elif low_prompt.rstrip().endswith('shoppe>'):
            # commands/movement.py's rc==2 'down' from room 1 lands here
            # (shoppe/main.py's menu), not directly at the elevator -- 'E'
            # is what actually reaches the combination prompt above. Mostly
            # leave immediately so shop visits don't eat the whole action
            # budget; occasionally detour through the elevator instead.
            await bot.say('E' if rng.random() < 0.25 else 'X')
        elif 'level (or l to leave)' in low_prompt:
            # shoppe/elevator.py's post-combination floor picker -- always
            # leave. Picking a level would change the bot's map_level, which
            # nothing else here (ROOM_POOL, room-mate assumptions) accounts for.
            await bot.say('L')
        elif bot.is_main_prompt():
            # Bounding every main-prompt reaction (not just do_action's own
            # picks) under the same round_no budget matters here: a duel
            # depends on BOTH sides cooperating (session.submit() only
            # resolves once both bots have chosen a tactic), so without
            # this a bot whose opponent has already exhausted its own
            # budget and stopped submitting would otherwise resubmit
            # 'duel attack' forever, waiting on a partner that'll never
            # answer again until this run's final close() forces a
            # forfeit -- deadlocking this bot's loop indefinitely instead
            # of just finishing its budget and moving on.
            bot.round_no += 1
            if bot.duel_pending:
                bot.duel_pending = False
                await bot.say('duel accept' if rng.random() < 0.85 else 'duel decline')
            elif bot.duel_active:
                if bot.duel_down:
                    await bot.say(rng.choice(['duel stand', 'duel roll']))
                else:
                    await bot.say(rng.choices(
                        ['duel attack', 'duel parry', 'duel bash'], weights=[3, 2, 1])[0])
            else:
                await do_action(bot, rng)
        # Otherwise: some other prompt (a Y/N confirm from an action we
        # didn't expect, e.g. a room boundary check) -- just wait for the
        # next message; most of these self-resolve or fall through to a
        # main prompt shortly. The stall-count nudge above covers the case
        # where nothing follows at all.


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_swarm(host: str, port: int, num_actions: int, seed: int) -> list[Bot]:
    bots = [Bot(name) for name in _BOTS]

    for i, b in enumerate(bots):
        if not await b.connect(host, port):
            _log(f'  [{b.label}] could not connect -- aborting swarm setup')
            return bots
        await b.say(f'connect {b.user} {_PASSWORD}')
        await b.drain_until(lambda x: x.is_main_prompt())

        # readied_weapon is session-only (player.py's _SESSION_ONLY) --
        # doesn't survive a save/load, so it must be readied fresh here
        # every run. Both sides of a DUEL need one readied.
        await b.say('ready long sword')
        await b.drain_until(lambda x: x.is_main_prompt())

        # A #friends group per bot (2 other bots, wrapping around the
        # roster) so page/whisper's #friends branch has something to hit.
        mate_a = _BOTS[(i + 1) % len(_BOTS)]
        mate_b = _BOTS[(i + 2) % len(_BOTS)]
        await b.say(f'groups #add friends {mate_a} {mate_b}')
        await b.drain_until(lambda x: x.is_main_prompt())

    _log(f'\n{"=" * WIDTH}\n  All {len(bots)} bots connected -- starting {num_actions} actions each\n{"=" * WIDTH}')

    await asyncio.gather(*(
        bot_loop(b, num_actions, seed + i) for i, b in enumerate(bots)
    ))

    for b in bots:
        await b.close()
    return bots


async def main(host: str, port: int, num_actions: int, seed: int) -> None:
    global _logfile
    _logfile = LOG_FILE.open('w', encoding='utf-8')
    _log(f'# bot_swarm session  {datetime.now().isoformat(timespec="seconds")}')
    _log(f'# {host}:{port}  actions/bot={num_actions}  seed={seed}')

    t0 = time.monotonic()
    bots = await run_swarm(host, port, num_actions, seed)
    elapsed = time.monotonic() - t0

    _log(f'\n{"=" * WIDTH}\n  SWARM SUMMARY ({elapsed:.1f}s)\n{"=" * WIDTH}')
    for b in bots:
        status = 'alive' if b.alive else 'DEAD'
        action_summary = ', '.join(f'{k}={v}' for k, v in sorted(b.actions.items()))
        _log(f'  {b.label:12s} {status:5s} rounds={b.round_no:3d}  {action_summary}')

    totals = Counter()
    for b in bots:
        totals.update(b.actions)
    _log(f'\n  totals: {dict(totals)}')

    _log(f'\n# log written to {LOG_FILE}')
    _logfile.close()
    print(f'Log saved to {LOG_FILE}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TADA 10-bot concurrent swarm stress test')
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--actions', type=int, default=40, help='actions per bot')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.actions, args.seed))
