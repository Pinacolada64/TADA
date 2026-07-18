#!/usr/bin/env python3
"""bot_horse_journey.py — Reactive live demo of the wild-horse mount pipeline
against a real running TADA server.

Unlike a scripted transcript (send line, sleep, assume the reply matches
what you expected), each Bot here runs a perceive -> update-belief -> decide
loop: it reads one message at a time, updates a small belief-state by
pattern-matching the message's *actual* content (the real strings the
server sends -- "has been slain by", "joins your party as a mount!", "not
enough gold", etc.), and only then decides its next move. A coarse `phase`
per bot keeps the run heading toward the intended story (find horse -> fight
-> captured -> travel to level 5 -> Jake's Stable -> equip -> train), but
everything inside a phase -- how many rounds to swing, whether a purchase
needs retrying, whether the horse's name needs a second attempt -- is driven
by what the server actually said, not by a fixed line count.

Why this exists / what studying it is worth your time for
-----------------------------------------------------------
This started as a plain scripted bot (send command, sleep a fixed delay,
grab whatever's queued, assume it answered what you just sent) and that
approach silently desynchronized from reality the moment two connections
shared a room, or the server's own RNG did something the script didn't
predict. Rewriting it as this perceive/update-belief/decide loop caught a
chain of real bugs, in roughly the order found:

  1. `'attack' in '[a]ttack'` is False -- the server's bracketed hotkey
     styling ("[A]ttack", "[F]lee") breaks naive substring checks. Fixed by
     matching on "exit this menu" (an unbracketed, unique phrase) instead.
  2. The real wire value for the main prompt is NOT the bare 'main> ' -- the
     server bakes a "[HH:MM] " timestamp directly into the prompt string
     (e.g. '[17:32] main> '). Every `== 'main> '` exact-equality check
     silently never matched. Found by connecting a raw diagnostic client
     and printing repr(msg['prompt']). Fixed with is_main_prompt(), an
     endswith() check.
  3. drain_until() couldn't tell "the condition I was waiting for actually
     happened" from "I gave up because the stream went quiet." It now
     returns a bool, and callers check it before acting on the assumption
     that what they were waiting for really arrived.
  4. A prompt's text lives in msg['prompt'], not msg['lines'] -- a check
     against the wrong field (_text_of(msg) instead of bot.last_prompt)
     silently never fired for the "Name your horse" prompt.
  5. Two REAL production bugs, invisible to the entire existing unit-test
     suite because every test fakes player.party as a bare list and builds
     Player objects with class/gender already set as constructor kwargs:
       - party.Party has no .append() (only .add_member()/.add()) --
         combat/engine.py's mount-capture code called .append() directly,
         so every real capture (LASSO and the passive Druid/Ranger tame)
         raised AttributeError against a real Player, silently, every time.
       - Player._load() never restored char_class/char_race/gender from the
         saved JSON on login -- commands/connect.py logs a player back in
         via `Player(name=char_name, id=username)` with no class/race/
         gender kwargs, so every reconnect silently reset them to defaults
         (char_class=None, gender=Gender.MALE), independent of this
         session's feature work.
  Both (5)s are fixed in combat/engine.py and player.py, with regression
  tests in tests/test_horse_mount_pipeline.py's fakes (now real Party
  objects) and tests/test_player_login_restores_class.py.

Setup
-----
Run tools/setup_bot_accounts.py first (creates botdummy/botlasso/botdruid).
Point this at a server instance you don't mind mutating -- it teleports
around as an admin, fights a real monster, spends real gold, and captures
a real mount. Safest to run against a disposable second instance:

    .venv/bin/python simple_server.py --port 34090 --petscii-port 34091 &

Usage
-----
    .venv/bin/python tools/bot_horse_journey.py [--host HOST] [--port PORT] [--horse-room N]

--horse-room skips the room-search phase if you already know where the
wild horse landed this session (simple_server.py logs
"Wild horse this session: room N" at startup).
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
LOG_FILE = Path(__file__).resolve().parent.parent / f'bot_horse_journey_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.log'

_PASSWORD = load_password()   # tools/.bot_credentials.json (gitignored)
_ELEVATOR_COMBO = '11-22-33'
_HORSE_ROOMS = (30, 52, 68)   # simple_server.py's _WILD_HORSE_ROOMS

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
        self.is_attacker = False
        self.monster_present = False
        self.mount_captured = False
        self.name_warning_seen = False
        self.gold_short = False
        self.saddle_equipped = False
        self.armor_equipped = False
        self.trained = False
        self.last_prompt = ''
        self.done = False

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
        """True if we're back at the normal game-loop prompt.

        The real wire value is NOT the bare 'main> ' -- the server bakes a
        "[HH:MM] " timestamp directly into the prompt string, e.g.
        '[17:32] main> '. An exact-equality check against 'main> ' silently
        never matches; discovered by connecting a raw diagnostic client and
        printing repr(msg['prompt']).
        """
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
        if 'joins your party as a mount!' in low:
            self.mount_captured = True
            self.in_combat = False
        if "you're not in a fight" in low or "you're not fighting anything" in low:
            self.is_attacker = False
            self.in_combat = False
        if 'joins ' in low and 'in fighting the' in low:
            self.is_attacker = True   # seen by bystanders watching someone ELSE join
        if 'you miss the' in low or 'you strike the' in low or 'you strike over' in low or 'you miss over' in low:
            # The joiner's OWN join-broadcast ("X joins Y in fighting...") is sent to
            # everyone else in the room (exclude_self=True) -- the joiner itself never
            # sees that line. Its own swing result is what actually confirms it's an
            # attacker now.
            self.is_attacker = True
        if 'there is' in low and 'horse' in low:
            self.monster_present = True
        if 'name must be 4-12 characters' in low or 'not allowed in name' in low:
            self.name_warning_seen = True
        if 'you do not have enough gold' in low:
            # Caller (jakes_journey) resets this to False before each purchase
            # attempt -- auto-clearing it here on every unrelated message would
            # wipe it out before the caller ever gets to check it.
            self.gold_short = True
        if 'saddled' in low or 'you put the saddle on the horse' in low:
            self.saddle_equipped = True
        if 'armored' in low or 'you put the horse armor on the horse' in low:
            self.armor_equipped = True
        if 'prances proudly' in low:
            self.trained = True
        if 'thy mount already is trained' in low:
            self.trained = True

    # -- driving a prompt loop until a real exit condition --------------

    async def drain_until(self, stop: callable, *, max_msgs: int = 300, timeout: float = 4.0) -> bool:
        """Receive at least one new message, then keep going until `stop(self)`
        is true. Returns True if `stop` actually fired, False if we gave up
        (quiet stream / timeout / connection closed / max_msgs exhausted).

        That return value matters: a timeout is NOT the same thing as the
        condition being satisfied, and treating them the same is exactly the
        kind of "acted on a guess instead of what really happened" bug this
        whole rewrite exists to avoid -- callers must check it before acting
        on the assumption that what they were waiting for actually arrived.

        The stop-check must come AFTER a receive, not before: belief-state
        fields like last_prompt persist across calls, so checking first would
        let a stale value from an *earlier* exchange satisfy the condition
        before we've read the real reply to whatever we just sent.
        """
        for _ in range(max_msgs):
            msg = await self._recv_one(timeout=timeout)
            if msg is None:
                return False
            if stop(self):
                return True
        return False


async def find_horse_room(bot: Bot) -> int:
    for room in _HORSE_ROOMS:
        await bot.say(f'#{room}')
        await bot.drain_until(lambda b: b.is_main_prompt())
        bot.monster_present = False
        await bot.say('look')
        await bot.drain_until(lambda b: b.is_main_prompt())
        if bot.monster_present:
            _log(f'\n  [{bot.label}] *** wild horse found in room {room} ***')
            return room
    raise RuntimeError('wild horse not found in any candidate room')


# ---------------------------------------------------------------------------
# Journey 1: non-Druid/Ranger LASSO capture (two bots, real synchronization)
# ---------------------------------------------------------------------------

async def dummy_leader_loop(bot: Bot, fight_started: asyncio.Event, may_stop: asyncio.Event) -> None:
    """React round-by-round to the fight's own prompt until it ends or we're told to stop.

    Room broadcasts (another player arriving, etc.) can land before "Combat
    begins!" ever does, so bot.in_combat being False does NOT by itself mean
    the fight is over -- only that it hasn't been observed to start *yet*.
    We only treat "not in_combat" as an end-of-fight signal once we've
    actually seen it start (combat_seen).
    """
    await bot.say('attack')
    combat_seen = False
    while True:
        msg = await bot._recv_one(timeout=2.0)
        if msg is None:
            return
        if bot.in_combat:
            combat_seen = True
            if not fight_started.is_set():
                fight_started.set()
        if combat_seen and not bot.in_combat:
            return   # the fight genuinely ended (captured, monster died, we died)
        if bot.is_main_prompt():
            return
        if 'exit this menu' in bot.last_prompt.lower():
            if not bot.alive:
                return
            await bot.say('a')
        if may_stop.is_set() and not bot.in_combat:
            return


async def lasso_capture_loop(bot: Bot, fight_started: asyncio.Event) -> bool:
    """Join the fight once it's real (not guessed via sleep), then react to
    whatever the name prompt actually says instead of assuming it worked."""
    await fight_started.wait()

    await bot.say('attack')
    if not await bot.drain_until(lambda b: b.is_main_prompt()):
        _log(f'  [{bot.label}] gave up waiting to rejoin the fight')
        return False
    if not bot.is_attacker:
        _log(f'  [{bot.label}] did not register as an attacker (fight may have already ended) -- aborting lasso')
        return False

    def _at_name_prompt(b: Bot) -> bool:
        return 'name your horse' in b.last_prompt.lower() or b.mount_captured or b.is_main_prompt()

    await bot.say('lasso')
    if not await bot.drain_until(_at_name_prompt):
        _log(f'  [{bot.label}] gave up waiting for a response to lasso')
        return False
    if bot.is_main_prompt() and 'name your horse' not in bot.last_prompt.lower() and not bot.mount_captured:
        _log(f'  [{bot.label}] lasso never opened a name prompt (fight likely ended first)')
        return False

    # Deliberately answer with an invalid (too-short) name first, and wait for
    # the *actual* reprompt (the "Name your horse" prompt reappearing) before
    # sending the real name -- not a fixed single read, which could leave the
    # true reprompt message sitting unread in the buffer for the next step to
    # accidentally swallow.
    bot.name_warning_seen = False
    await bot.say('AB')
    if not await bot.drain_until(_at_name_prompt):
        _log(f'  [{bot.label}] gave up waiting for the name reprompt')
        return False
    if not bot.name_warning_seen:
        _log(f'  [{bot.label}] expected a reprompt for the short name but did not see one')

    await bot.say('STARDUST')
    got_it = await bot.drain_until(lambda b: b.mount_captured or b.is_main_prompt())
    return got_it and bot.mount_captured


async def journey_lasso(host: str, port: int, horse_room: int | None) -> None:
    _log(f'\n\n{"#" * WIDTH}\n#  JOURNEY 1: non-Druid/Ranger LASSO capture (reactive)\n{"#" * WIDTH}')

    dummy = Bot('botdummy', 'botdummy')
    lasso = Bot('botlasso', 'botlasso')
    if not await dummy.connect(host, port) or not await lasso.connect(host, port):
        return
    await dummy.say(f'connect {dummy.user} {_PASSWORD}')
    await dummy.drain_until(lambda b: b.is_main_prompt())
    await lasso.say(f'connect {lasso.user} {_PASSWORD}')
    await lasso.drain_until(lambda b: b.is_main_prompt())

    room = horse_room or await find_horse_room(dummy)
    if horse_room:
        await dummy.say(f'#{room}')
        await dummy.drain_until(lambda b: b.is_main_prompt())
    await lasso.say(f'#{room}')
    await lasso.drain_until(lambda b: b.is_main_prompt())

    fight_started = asyncio.Event()
    may_stop = asyncio.Event()
    dummy_task = asyncio.create_task(dummy_leader_loop(dummy, fight_started, may_stop))

    captured = await lasso_capture_loop(lasso, fight_started)
    may_stop.set()
    try:
        await asyncio.wait_for(dummy_task, timeout=5)
    except asyncio.TimeoutError:
        _log(f'  [botdummy] leader loop did not wind down in time')

    _log(f'\n  [botlasso] *** capture {"SUCCEEDED" if captured else "FAILED"} ***')

    if captured:
        await jakes_journey(lasso)

    await dummy.close()
    await lasso.close()
    _log('\n  Journey 1 complete.')


# ---------------------------------------------------------------------------
# Journey 2: Druid/Ranger passive tame (single bot, reactive round loop)
# ---------------------------------------------------------------------------

async def druid_passive_tame(bot: Bot) -> bool:
    await bot.say('attack')
    for _ in range(400):   # 15%/round -- give it a generous budget
        msg = await bot._recv_one(timeout=3.0)
        if msg is None or bot.done:
            return bot.mount_captured
        if bot.mount_captured:
            return True
        if not bot.alive:
            _log(f'  [{bot.label}] died before the passive tame ever fired')
            return False
        if bot.is_main_prompt() and not bot.in_combat:
            return bot.mount_captured
        if 'name your horse' in bot.last_prompt.lower():
            # The prompt text lives in msg['prompt'], not msg['lines'] --
            # checking a lines-only helper here never matched, so this
            # branch silently never fired and the loop just timed out
            # waiting on a prompt it never recognized as the name prompt.
            await bot.say('MOONBEAM')
        elif 'exit this menu' in bot.last_prompt.lower():
            await bot.say('a')
    return bot.mount_captured


async def journey_druid(host: str, port: int, horse_room: int | None) -> None:
    _log(f'\n\n{"#" * WIDTH}\n#  JOURNEY 2: Druid/Ranger passive tame (reactive)\n{"#" * WIDTH}')

    druid = Bot('botdruid', 'botdruid')
    if not await druid.connect(host, port):
        return
    await druid.say(f'connect {druid.user} {_PASSWORD}')
    await druid.drain_until(lambda b: b.is_main_prompt())

    room = horse_room or await find_horse_room(druid)
    if horse_room:
        await druid.say(f'#{room}')
        await druid.drain_until(lambda b: b.is_main_prompt())

    tamed = await druid_passive_tame(druid)
    _log(f'\n  [botdruid] *** passive tame {"SUCCEEDED" if tamed else "did not occur"} ***')

    if tamed:
        await jakes_journey(druid)

    await druid.close()
    _log('\n  Journey 2 complete.')


# ---------------------------------------------------------------------------
# Shared tail: elevator to level 5, Jake's Stable buy/equip/train
# ---------------------------------------------------------------------------

async def jakes_journey(bot: Bot) -> None:
    await bot.say('#1')
    await bot.drain_until(lambda b: b.is_main_prompt())
    await bot.say('d')
    await bot.drain_until(lambda b: 'shoppe' in b.last_prompt.lower())
    await bot.say('E')
    await bot.drain_until(lambda b: 'combination' in b.last_prompt.lower())
    await bot.say(_ELEVATOR_COMBO)
    await bot.drain_until(lambda b: 'level' in b.last_prompt.lower())
    await bot.say('5')
    await bot.drain_until(lambda b: 'level' in b.last_prompt.lower())
    await bot.say('L')
    await bot.drain_until(lambda b: 'shoppe' in b.last_prompt.lower())
    await bot.say('x')
    await bot.drain_until(lambda b: b.is_main_prompt())

    await bot.say('#157')
    await bot.drain_until(lambda b: b.is_main_prompt())
    await bot.say('e')
    await bot.drain_until(lambda b: 'jake' in b.last_prompt.lower())

    # Buy Saddle, reacting to a real "not enough gold" instead of assuming success.
    bot.gold_short = False
    await bot.say('3')
    await bot.drain_until(lambda b: 'gold?' in b.last_prompt.lower() or 'jake' in b.last_prompt.lower())
    if 'jake' not in bot.last_prompt.lower():
        await bot.say('Y')
        await bot.drain_until(lambda b: 'jake' in b.last_prompt.lower())
    if bot.gold_short:
        _log(f'  [{bot.label}] *** could not afford the Saddle -- stopping Jake\'s sequence ***')
        return

    bot.gold_short = False
    await bot.say('4')
    await bot.drain_until(lambda b: 'gold?' in b.last_prompt.lower() or 'jake' in b.last_prompt.lower())
    if 'jake' not in bot.last_prompt.lower():
        await bot.say('Y')
        await bot.drain_until(lambda b: 'jake' in b.last_prompt.lower())
    if bot.gold_short:
        _log(f'  [{bot.label}] *** could not afford the Horse Armor -- stopping Jake\'s sequence ***')
        return

    await bot.say('')   # leave the stable
    await bot.drain_until(lambda b: b.is_main_prompt())

    for _ in range(2):   # equip Saddle, then Horse Armor
        await bot.say('use')
        await bot.drain_until(lambda b: 'use which item' in b.last_prompt.lower() or b.is_main_prompt())
        if 'use which item' in bot.last_prompt.lower():
            await bot.say('1')
            await bot.drain_until(lambda b: b.is_main_prompt())
        if bot.saddle_equipped and bot.armor_equipped:
            break

    await bot.say('e')
    await bot.drain_until(lambda b: 'jake' in b.last_prompt.lower())
    await bot.say('6')
    await bot.drain_until(lambda b: 'gold?' in b.last_prompt.lower() or 'jake' in b.last_prompt.lower())
    if 'jake' not in bot.last_prompt.lower():
        await bot.say('Y')
        await bot.drain_until(lambda b: 'jake' in b.last_prompt.lower())

    _log(f'  [{bot.label}] *** training {"SUCCEEDED" if bot.trained else "did not complete"} ***')


async def main(host: str, port: int, horse_room: int | None) -> None:
    global _logfile
    _logfile = LOG_FILE.open('w', encoding='utf-8')
    _log(f'# bot_horse_journey (reactive) session  {datetime.now().isoformat(timespec="seconds")}')
    _log(f'# {host}:{port}')

    await journey_lasso(host, port, horse_room)
    await journey_druid(host, port, horse_room)

    _log(f'\n{"=" * WIDTH}\n  All journeys complete.\n{"=" * WIDTH}\n# log written to {LOG_FILE}')
    _logfile.close()
    print(f'Log saved to {LOG_FILE}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TADA horse-journey reactive bot demo')
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--horse-room', type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port, args.horse_room))
