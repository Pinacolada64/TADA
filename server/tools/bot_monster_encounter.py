#!/usr/bin/env python3
"""bot_monster_encounter.py — Reactive live demo of a full monster encounter
against a real running TADA server: ORDER deployment, the crystal pendant
petrify counter, the tactical ambush check, and ranged-weapon combat
(READY a .357 MAGNUM, USE a box of ammo to load it), all in one fight.

Same perceive -> update-belief -> decide loop style as bot_horse_journey.py
(see that file's docstring for why a reactive bot beats a fixed-delay
script) -- see tools/BOT_README.md for the research this script is built
from (room/monster placement, ORDER's exact prompt flow, and the greppable
strings combat/engine.py prints when the crystal pendant / tactical ambush
checks actually fire).

Setup
-----
Run tools/setup_bot_accounts.py first (creates botdummy/botlasso/botdruid/
railbender). railbender comes pre-seeded with 3 purchased servant allies
(BATMAN [ELITE], ARTHUR DENT, BETTY BOOP) so this script can go straight to
ORDER without a live Fat Olaf shop transaction.

Point this at a server instance you don't mind mutating -- it teleports
around as an admin, picks up the Crystal Pendant, deploys servants, and
fights a real monster (MEDUSA, room 125, "STONE ROOM"):

    .venv/bin/python simple_server.py --port 34090 --petscii-port 34091 &

Usage
-----
    .venv/bin/python tools/bot_monster_encounter.py [--host HOST] [--port PORT]

Writes a human-readable transcript to bot_monster_encounter_<timestamp>.log
and a structured JSON event timeline (for the artifact viewer) to
bot_monster_encounter_<timestamp>.events.json.
"""
from __future__ import annotations

import asyncio
import argparse
import json
import textwrap
import time
from datetime import datetime
from pathlib import Path

HOST  = '127.0.0.1'
PORT  = 34083
WIDTH = 78
_STAMP = datetime.now().strftime("%Y-%m-%d_%H%M%S")
LOG_FILE    = Path(__file__).resolve().parent.parent / f'bot_monster_encounter_{_STAMP}.log'
EVENTS_FILE = Path(__file__).resolve().parent.parent / f'bot_monster_encounter_{_STAMP}.events.json'

_PASSWORD    = 'puppy123'
_MONSTER_ROOM = 125   # STONE ROOM: MEDUSA (#19, petrify) + Crystal Pendant (item 82)

_logfile = None
_events: list[dict] = []
_t0 = time.monotonic()

# Greppable markers from combat/engine.py -- see tools/BOT_README.md #5.
_PENDANT_BLOCKED  = 'preventing turn to stone by'
_PENDANT_COUNTERED = 'happens to see you are'
_AMBUSH_SHOUTS    = ("to the front!", "on the flank!", "to the rear!")
_AMBUSH_CAUGHT    = 'was caught off guard!'
_AMBUSH_YOU_CAUGHT = 'you are caught off guard!'
_AMBUSH_ELITE_IMMUNE = 'is too clever to be caught off guard.'
_AMBUSH_DESERT_PHRASES = ('runs away screaming!', 'jumps overboard and swims away!', 'fires retros, and flees!')

# Ranged-weapon greppable markers (commands/use.py / combat/engine.py --
# see tools/BOT_README.md's follow-up notes on the ammo-loading fix).
_AMMO_LOADED          = 'rounds now ready'
_AMMO_EMPTY           = 'try use to load ammunition'
_MISSILE_FIRST_STRIKE = 'missile: first strike!'


def _log(text: str = '') -> None:
    print(text)
    if _logfile is not None:
        _logfile.write(text + '\n')
        _logfile.flush()


def _record(phase: str, actor: str, text: str) -> None:
    """Append one entry to the structured timeline the artifact renders."""
    _events.append({
        't': round(time.monotonic() - _t0, 2),
        'phase': phase,
        'actor': actor,
        'text': text,
    })


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
        self.is_attacker = False
        self.monster_present = False
        self.monster_dead = False
        self.last_prompt = ''
        self.done = False

        # Encounter-flow flags this script cares about.
        self.pendant_blocked = False
        self.pendant_countered = False
        self.ambush_fired = False
        self.ambush_caught_self = False
        self.ambush_ally_caught = False
        self.ambush_ally_deserted = False
        self.ambush_elite_immune = False
        self.order_deployed = False
        self.ammo_loaded = False
        self.ammo_ran_out = False
        self.missile_first_strike = False

    # -- transport -----------------------------------------------------

    async def connect(self, host: str, port: int) -> bool:
        _log(f'\n{"=" * WIDTH}\n  [{self.label}] connecting as {self.user!r} to {host}:{port}\n{"=" * WIDTH}')
        _record('connect', self.label, f'connecting as {self.user!r} to {host}:{port}')
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
        except ConnectionRefusedError:
            _log(f'  [{self.label}] connection refused -- is the server running on {port}?')
            _record('connect', self.label, 'connection refused')
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
        _record('send', self.label, line if line else '(blank/Enter)')
        await self._send({'lines': [line], 'mode': 'game'})

    def is_main_prompt(self) -> bool:
        """The wire prompt bakes in a "[HH:MM] " timestamp -- match the suffix."""
        return self.last_prompt.rstrip().endswith('main>')

    async def close(self) -> None:
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    # -- belief update: the whole point of "reactive" ------------------

    def _update_belief(self, text: str) -> None:
        low = text.lower()

        if 'has been slain by' in low and self.user.lower() in low:
            self.alive = False
            self.in_combat = False
        if 'combat begins!' in low:
            self.in_combat = True
            _record('combat', self.label, 'Combat begins!')
        if "you're not in a fight" in low or "you're not fighting anything" in low:
            self.is_attacker = False
            self.in_combat = False
        if 'joins ' in low and 'in fighting the' in low:
            self.is_attacker = True
        if 'you miss the' in low or 'you strike the' in low or 'you strike over' in low or 'you miss over' in low:
            self.is_attacker = True
        if 'there is' in low and 'medusa' in low:
            self.monster_present = True
        if 'have slain the' in low or 'slays the' in low or 'turns to stone as it dies' in low:
            self.monster_dead = True
            self.in_combat = False
            _record('combat', self.label, 'monster defeated')

        # Crystal pendant (see tools/BOT_README.md #5).
        if _PENDANT_BLOCKED in low:
            self.pendant_blocked = True
            _record('pendant', self.label, text.strip())
        if _PENDANT_COUNTERED in low:
            self.pendant_countered = True
            _record('pendant', self.label, text.strip())

        # Tactical ambush (see tools/BOT_README.md #5).
        if any(shout in low for shout in _AMBUSH_SHOUTS):
            self.ambush_fired = True
            _record('ambush', self.label, text.strip())
        if _AMBUSH_YOU_CAUGHT in low:
            self.ambush_caught_self = True
            _record('ambush', self.label, text.strip())
        if _AMBUSH_CAUGHT in low:
            self.ambush_ally_caught = True
            _record('ambush', self.label, text.strip())
        if _AMBUSH_ELITE_IMMUNE in low:
            self.ambush_elite_immune = True
            _record('ambush', self.label, text.strip())
        if any(phrase in low for phrase in _AMBUSH_DESERT_PHRASES):
            self.ambush_ally_deserted = True
            _record('ambush', self.label, text.strip())

        # Ranged weapon: ammo loading, running dry, first-strike bonus.
        if _AMMO_LOADED in low:
            self.ammo_loaded = True
            _record('use', self.label, text.strip())
        if _AMMO_EMPTY in low:
            self.ammo_ran_out = True
            _record('use', self.label, text.strip())
        if _MISSILE_FIRST_STRIKE in low:
            self.missile_first_strike = True
            _record('combat', self.label, text.strip())

        # Petrify death (MEDUSA's actual turn-to-stone attack landing) --
        # separate from the crystal pendant's block/counter above, since
        # this is what happens when nobody blocked it (no pendant on the
        # struck player, or the 10% counter roll).
        if 'casts turn to stone on you' in low or 'turned to stone by' in low:
            _record('death', self.label, text.strip())
        if 'you have died' in low:
            _record('death', self.label, 'You have died!')

        # Round-by-round exchange narration (compact -- not every belief
        # flag, just what the artifact timeline shows as the fight ticks).
        if any(p in low for p in ('strikes the', 'misses the', 'strike the', 'miss the', 'medusa misses')):
            _record('exchange', self.label, text.strip())

    # -- driving a prompt loop until a real exit condition --------------

    async def drain_until(self, stop: callable, *, max_msgs: int = 300, timeout: float = 4.0) -> bool:
        """Receive at least one new message, then keep going until `stop(self)`
        is true. Returns True if `stop` actually fired, False if we gave up.
        The check comes AFTER a receive -- see bot_horse_journey.py's
        drain_until docstring for why checking first would risk matching a
        stale belief-state field left over from an earlier exchange."""
        for _ in range(max_msgs):
            msg = await self._recv_one(timeout=timeout)
            if msg is None:
                return False
            if stop(self):
                return True
        return False


# ---------------------------------------------------------------------------
# ORDER: deploy railbender's 3 servants as Point/Flank/Rear
# ---------------------------------------------------------------------------

async def deploy_order(bot: Bot) -> None:
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE: ORDER -- tactical deployment ({bot.label})\n{"#" * WIDTH}')
    _record('order', bot.label, 'issuing ORDER command')

    await bot.say('order')
    await bot.drain_until(lambda b: 'change this' in b.last_prompt.lower())
    await bot.say('Y')

    # Point Man, Flank Guard, Rear Guard -- always pick "1" (top of the
    # remaining list) at each slot; ORDER removes the picked ally from the
    # pool for the next slot, so "1" three times in a row deploys all three.
    for _ in range(3):
        await bot.drain_until(
            lambda b: 'new point man' in b.last_prompt.lower()
            or 'new flank guard' in b.last_prompt.lower()
            or 'new rear guard' in b.last_prompt.lower()
        )
        await bot.say('1')

    await bot.drain_until(lambda b: b.is_main_prompt())
    bot.order_deployed = True
    _record('order', bot.label, 'servants deployed: Point/Flank/Rear')
    _log(f'\n  [{bot.label}] *** ORDER deployment complete ***')


async def ready_weapon(bot: Bot) -> None:
    """Equip whatever weapon slot 1 is -- unarmed fighters barely scratch
    MEDUSA (lots of "inflict no damage" rounds), so ready a weapon first to
    keep the demo fight from dragging on for dozens of rounds."""
    await bot.say('ready')
    await bot.drain_until(lambda b: b.is_main_prompt() or 'weapon' in b.last_prompt.lower())
    had_weapons = not bot.is_main_prompt()
    if had_weapons:
        await bot.say('1')
        await bot.drain_until(lambda b: b.is_main_prompt())
    if had_weapons:
        _record('ready', bot.label, 'readied a weapon')


async def load_ammo(bot: Bot, ammo_name: str) -> None:
    """USE a box of ammo to load it into the just-readied weapon --
    exercises commands/use.py's ammo branch (fixed this session: shop-
    bought ammo used to lose its rounds/damage/used_with flags on
    purchase -- and, deeper still, ANY item's flags were dropped on every
    save/load cycle by inventory.py's JSON round-trip -- so USE could
    never load it. See BOT_README.md and inventory.py's
    InventoryEntry.to_json() docstring.

    Only records the 'use' event here on the send side; _update_belief()
    already records the actual "N ROUNDS NOW READY" reply, so this doesn't
    double-log the same real event under two different phases."""
    await bot.say(f'use {ammo_name}')
    await bot.drain_until(lambda b: b.is_main_prompt())


# ---------------------------------------------------------------------------
# Shared: teleport to the monster room, grab the Crystal Pendant
# ---------------------------------------------------------------------------

async def goto_monster_room(bot: Bot, *, get_pendant: bool = False) -> None:
    await bot.say(f'#{_MONSTER_ROOM}')
    await bot.drain_until(lambda b: b.is_main_prompt())
    _record('teleport', bot.label, f'teleported to room {_MONSTER_ROOM} (STONE ROOM)')

    if get_pendant:
        await bot.say('get crystal pendant')
        await bot.drain_until(lambda b: b.is_main_prompt())
        _record('item', bot.label, 'picked up the Crystal Pendant')

    bot.monster_present = False
    await bot.say('look')
    await bot.drain_until(lambda b: b.is_main_prompt())
    if bot.monster_present:
        _log(f'\n  [{bot.label}] *** MEDUSA confirmed in room {_MONSTER_ROOM} ***')
        _record('look', bot.label, 'MEDUSA confirmed in room')
    else:
        _log(f'\n  [{bot.label}] *** WARNING: MEDUSA not seen in room {_MONSTER_ROOM} -- already dead? ***')
        _record('look', bot.label, 'WARNING: monster not seen (already dead?)')


# ---------------------------------------------------------------------------
# Combat: leader keeps the fight open, bystanders join, everyone reacts
# ---------------------------------------------------------------------------

async def leader_loop(bot: Bot, fight_started: asyncio.Event, may_stop: asyncio.Event) -> None:
    """React round-by-round to the fight's own prompt until it ends or
    we're told to stop -- same pattern as bot_horse_journey.py's
    dummy_leader_loop (combat_seen guards against a stray room broadcast
    arriving before "Combat begins!" ever does)."""
    await bot.say('attack')
    combat_seen = False
    while True:
        msg = await bot._recv_one(timeout=3.0)
        if msg is None:
            return
        if bot.in_combat:
            combat_seen = True
            if not fight_started.is_set():
                fight_started.set()
        if bot.monster_dead:
            may_stop.set()
        if combat_seen and not bot.in_combat:
            return
        if bot.is_main_prompt():
            return
        if bot.last_prompt.rstrip().lower().endswith('command>'):
            if not bot.alive:
                return
            await bot.say('a')
        if may_stop.is_set() and not bot.in_combat:
            return


async def joiner_loop(bot: Bot, fight_started: asyncio.Event, may_stop: asyncio.Event) -> None:
    """Wait for the leader's fight to be real, join it, then keep re-issuing
    `attack` every round -- unlike the (original) leader, a bystander who
    joins an already-open fight gets a single swing and drops straight back
    to the main prompt each time (no persistent Command> menu of their own).

    But if the room's original leader dies or leaves first, whoever attacks
    next becomes the *new* leader and DOES get a Command> menu of their own
    (observed live: railbender ended up stuck there when botdummy fell
    before the others joined) -- so this loop also drives that menu with
    'a' each round, exactly like leader_loop, whenever it sees one."""
    await fight_started.wait()

    for _ in range(30):   # generous round budget
        if not bot.alive or bot.monster_dead or may_stop.is_set():
            return
        await bot.say('attack')
        if not await bot.drain_until(
            lambda b: b.is_main_prompt() or b.last_prompt.rstrip().lower().endswith('command>')
        ):
            _log(f'  [{bot.label}] gave up waiting for a response to attack')
            return
        while bot.last_prompt.rstrip().lower().endswith('command>'):
            if not bot.alive or bot.monster_dead:
                return
            await bot.say('a')
            if not await bot.drain_until(
                lambda b: b.is_main_prompt() or b.last_prompt.rstrip().lower().endswith('command>')
            ):
                _log(f'  [{bot.label}] gave up waiting for a response at the Command> menu')
                return
        if bot.monster_dead or not bot.alive:
            return


async def monster_encounter(host: str, port: int) -> None:
    _log(f'\n\n{"#" * WIDTH}\n#  MONSTER ENCOUNTER: ORDER + Crystal Pendant + Tactical Ambush\n{"#" * WIDTH}')

    dummy = Bot('botdummy', 'botdummy')
    lasso = Bot('botlasso', 'botlasso')
    rail  = Bot('railbender', 'railbender')

    for b in (dummy, lasso, rail):
        if not await b.connect(host, port):
            _log(f'  [{b.label}] could not connect -- aborting')
            return
        await b.say(f'connect {b.user} {_PASSWORD}')
        await b.drain_until(lambda x: x.is_main_prompt())

    await deploy_order(rail)

    for b in (dummy, lasso, rail):
        await ready_weapon(b)
    await load_ammo(lasso, '.357 ammo')   # botlasso: the ranged path

    await goto_monster_room(dummy, get_pendant=False)
    await goto_monster_room(lasso, get_pendant=False)
    await goto_monster_room(rail, get_pendant=True)   # railbender wears the pendant

    fight_started = asyncio.Event()
    may_stop = asyncio.Event()
    dummy_task = asyncio.create_task(leader_loop(dummy, fight_started, may_stop))
    lasso_task = asyncio.create_task(joiner_loop(lasso, fight_started, may_stop))
    rail_task  = asyncio.create_task(joiner_loop(rail, fight_started, may_stop))

    await asyncio.wait([lasso_task, rail_task], timeout=90)
    may_stop.set()
    try:
        await asyncio.wait_for(dummy_task, timeout=5)
    except asyncio.TimeoutError:
        _log('  [botdummy] leader loop did not wind down in time')

    _log(f'\n{"=" * WIDTH}\n  OUTCOME SUMMARY\n{"=" * WIDTH}')
    for b in (dummy, lasso, rail):
        _log(f'  [{b.label}] alive={b.alive} in_combat={b.in_combat}')
    _log(f'  monster_dead (any bot saw it): '
         f'{any(b.monster_dead for b in (dummy, lasso, rail))}')
    _log(f'  crystal pendant blocked: {rail.pendant_blocked}  countered: {rail.pendant_countered}')
    _log(f'  tactical ambush fired: {any(b.ambush_fired for b in (dummy, lasso, rail))}')
    _log(f'  ambush caught a player: {any(b.ambush_caught_self for b in (dummy, lasso, rail))}')
    _log(f'  ambush caught a servant: {rail.ambush_ally_caught}')
    _log(f'  ELITE servant immune: {rail.ambush_elite_immune}')
    _log(f'  a servant deserted: {rail.ambush_ally_deserted}')
    _log(f'  botlasso loaded .357 ammo: {lasso.ammo_loaded}')
    _log(f'  botlasso ran out of ammo mid-fight: {lasso.ammo_ran_out}')
    _log(f'  missile first strike triggered: {any(b.missile_first_strike for b in (dummy, lasso, rail))}')
    _record('outcome', 'system', 'encounter complete')

    for b in (dummy, lasso, rail):
        await b.close()
    _log('\n  Monster encounter complete.')


async def main(host: str, port: int) -> None:
    global _logfile
    _logfile = LOG_FILE.open('w', encoding='utf-8')
    _log(f'# bot_monster_encounter (reactive) session  {datetime.now().isoformat(timespec="seconds")}')
    _log(f'# {host}:{port}')

    await monster_encounter(host, port)

    _log(f'\n{"=" * WIDTH}\n  Session complete.\n{"=" * WIDTH}\n# log written to {LOG_FILE}')
    _logfile.close()
    EVENTS_FILE.write_text(json.dumps(_events, indent=2))
    print(f'Log saved to {LOG_FILE}')
    print(f'Events saved to {EVENTS_FILE}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TADA monster-encounter reactive bot demo')
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
