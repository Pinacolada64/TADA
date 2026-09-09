#!/usr/bin/env python3
"""bot_epic_battle.py — a full, reactive, multi-phase live demo built to
exercise as much of the combat surface as one run can reach: the Death
Amulet gamble (Amulet-of-Life-halved), STORM weapon acceptance + auto-
assert + ammo, the Crystal Pendant petrify counter, tactical ambush,
LASSO + MOUNT + CHARGE + the unseat check, PC spellcasting (CAST) against
a live monster, monster spellcasting (endurance/destroy) cast back, a
double-attack boss, and a final kill on a no_article-flagged monster
(RONNEY) -- validating the monster-name article fix landed this session.

Two throwaway characters (tools/setup_epic_battle_account.py):
  sylvanwynd  (Druid/Elf) -- the hero. Carries the Death Amulet + Amulet
              of Life, the STORM BOW + arrows, 2 monster-damage spells,
              and 2 purchased servant allies (one ELITE, one slot left
              open for the horse).
  thornshield (Fighter)   -- exists purely to hold a fight open as
              *leader* so sylvanwynd can act as a *bystander* whenever a
              phase needs LASSO or CAST -- both are top-level commands
              only reachable from the ordinary main-prompt loop
              (combat.engine.CombatSession.join()), never from a fight
              leader's own [A]ttack/[F]lee/[R]eady/e[X]it Command> menu
              (_run_loop() reads that menu char-by-char with no dispatch
              back to the general command processor at all). Conversely,
              the Crystal Pendant / tactical ambush checks and the CHARGE
              menu option only ever fire for the *leader* -- so sylvanwynd
              leads the MEDUSA and GUARDIAN fights herself, and hands the
              RONNEY fight's leadership to thornshield so she's free to
              CAST.

Targets tools/run_throwaway_server.py's isolated instance (default
127.0.0.1:34190) -- never the real run/server save directory.

Usage:
    .venv/bin/python tools/run_throwaway_server.py &
    .venv/bin/python tools/setup_epic_battle_account.py
    .venv/bin/python tools/bot_epic_battle.py [--host HOST] [--port PORT]

Writes a human-readable transcript to bot_epic_battle_<timestamp>.log and
a structured JSON event timeline (for the artifact viewer) to
bot_epic_battle_<timestamp>.events.json.
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
PORT  = 34190
WIDTH = 78
_STAMP = datetime.now().strftime("%Y-%m-%d_%H%M%S")
LOG_FILE    = Path(__file__).resolve().parent.parent / f'bot_epic_battle_{_STAMP}.log'
EVENTS_FILE = Path(__file__).resolve().parent.parent / f'bot_epic_battle_{_STAMP}.events.json'

_PASSWORD = 'puppy123'

# Room numbers confirmed live from level_1.json / level_5.json (see
# tools/BOT_README.md's method: room dicts carry their real game 'number'
# field, which does NOT equal their position in the JSON list).
_MEDUSA_ROOM   = (1, 125)   # STONE ROOM -- MEDUSA (#19, petrify) + Crystal Pendant on the floor
_GUARDIAN_ROOM = (5, 116)   # Rocky Ravine -- GUARDIAN (#103: caster, tough, petrify, re_animates, fire_attack)
_RONNEY_ROOM   = (5, 262)   # Kings Chamber -- RONNEY (#93: caster, double_attacks, tough, petrify,
                            #                  fire_attack, no_article, no_flee)
_HORSE_ROOMS   = (30, 52, 68)  # level 1, simple_server.py's _WILD_HORSE_ROOMS

_logfile = None
_events: list[dict] = []
_t0 = time.monotonic()


def _log(text: str = '') -> None:
    print(text)
    if _logfile is not None:
        _logfile.write(text + '\n')
        _logfile.flush()


def _record(phase: str, actor: str, text: str, tag: str | None = None) -> None:
    """Append one entry to the structured timeline the artifact renders.
    tag is an optional short mechanic label (e.g. 'ammo', 'storm', 'mount')
    the artifact uses to color/badge that line -- purely presentational,
    never used to drive bot logic."""
    entry = {
        't': round(time.monotonic() - _t0, 2),
        'phase': phase,
        'actor': actor,
        'text': text,
    }
    if tag:
        entry['tag'] = tag
    _events.append(entry)


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
    """One connection, driven by a perceive -> update-belief -> decide loop
    (same style as tools/bot_horse_journey.py / tools/bot_monster_encounter.py)."""

    def __init__(self, label: str, user: str):
        self.label = label
        self.user = user
        self.reader = None
        self.writer = None

        self.alive = True
        self.in_combat = False
        self.is_attacker = False
        self.monster_present = False
        self.monster_dead = False
        self.last_prompt = ''
        self.last_lines_text = ''
        self.done = False

        self.mount_captured = False
        self.name_warning_seen = False
        self.mounted = False
        self.charge_eligible = False

        # Bumped by _update_belief() whenever a message matches a known
        # LASSO/CAST outcome -- used instead of a bare is_main_prompt()
        # stop condition, since two bots sharing a room means unrelated
        # broadcasts (the other bot's own swing) can land a 'main>' prompt
        # on this connection before this bot's own command's real reply
        # does. Counting (not booleaning) lets a caller snapshot the count
        # before sending, then wait for it to increase -- proof THIS
        # command got a matching reply, not a stale/unrelated one.
        self.lasso_outcome_count = 0
        self.arrival_count = 0
        self.cast_prompt_count = 0

    def _bump(self, attr: str) -> None:
        setattr(self, attr, getattr(self, attr) + 1)

    async def connect(self, host: str, port: int) -> bool:
        _log(f'\n{"=" * WIDTH}\n  [{self.label}] connecting as {self.user!r} to {host}:{port}\n{"=" * WIDTH}')
        _record('connect', self.label, f'connecting as {self.user!r}')
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
            _log(f'  [{self.label}] (timed out waiting {timeout}s for a message)')
            return None
        if not raw:
            self.done = True
            _log(f'  [{self.label}] (connection closed by server)')
            return None
        msg = json.loads(raw.strip())
        _wrap_recv(self.label, msg)
        self.last_prompt = msg.get('prompt', '') or ''
        self.last_lines_text = _text_of(msg)
        self._update_belief(self.last_lines_text)

        # Auto-decline a shadow-ally recruit offer (encounters/monster.py's
        # try_shadow_ally(), ~50% chance right after ANY kill, PC or bystander,
        # leader or not). It's a synchronous ctx.prompt() fired from inside
        # _monster_dies() -- i.e. mid-round, before the fight-ending message
        # even finishes propagating -- so a caller's own "combat's over,
        # stop watching this bot" check can return before ever seeing this
        # prompt, leaving it permanently unanswered and desyncing every
        # subsequent command on this connection (this module's docstring:
        # the WILD HORSE phase race that motivated this fix). Answered here,
        # centrally, so every caller benefits transparently.
        if 'let them join' in self.last_prompt.lower():
            _log(f'  [{self.label}] (auto-declining shadow-ally recruit offer)')
            await self._send({'lines': ['N'], 'mode': 'game'})

        # LASSO's "Name your horse" and CAST's "Cast which spell number"
        # both arrive via ctx.prompt() -- i.e. in THIS message's prompt
        # field, never in its lines -- so say_and_await()'s callers need
        # the bump to fire off the prompt, not the lines text (which is
        # all _update_belief() above ever sees). Missing this originally
        # meant say_and_await('lasso', ...) never recognized the name
        # prompt at all and just kept consuming the OTHER bot's ongoing
        # fight broadcasts (the capture doesn't end the fight until the
        # name is actually given) until its message budget ran out,
        # overwriting last_prompt along the way and losing the prompt
        # entirely -- leaving it permanently unanswered.
        #
        # CAST's own long instructional text ("Cast which spell number?
        # (?=list, Q to leave)") later moved out of prompt_text into
        # preamble_lines (commands/cast.py, the alpha-tester too-long-
        # prompt-lines fix) -- so it now arrives in THIS message's lines,
        # not its prompt field, while prompt_text itself shrank to just
        # 'Spell #'. Check both fields so this still matches regardless
        # of which one carries it.
        low_prompt = self.last_prompt.lower()
        low_lines  = self.last_lines_text.lower()
        if 'name your horse' in low_prompt:
            self.name_warning_seen = True
            self._bump('lasso_outcome_count')
        if 'cast which spell number' in low_prompt or 'cast which spell number' in low_lines:
            self._bump('cast_prompt_count')

        return msg

    async def say(self, line: str) -> None:
        _wrap_send(self.label, line)
        await self._send({'lines': [line], 'mode': 'game'})

    def is_main_prompt(self) -> bool:
        return self.last_prompt.rstrip().endswith('main>')

    async def close(self) -> None:
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    def _update_belief(self, text: str) -> None:
        low = text.lower()

        # "You appear in a flash of light." -- the traveler's own arrival
        # confirmation (commands/teleport.py). A stray same-tick broadcast
        # (e.g. "The MEDUSA turns to stone as it dies!" from this bot's own
        # kill a message earlier) can land its own 'main>'-ending prompt on
        # this connection BEFORE the real teleport reply does -- a bare
        # is_main_prompt() stop condition would then wrongly declare the
        # teleport done while the bot is still standing in the old room.
        if 'you appear in a flash of light' in low:
            self._bump('arrival_count')

        if 'has been slain by' in low and self.user.lower() in low:
            self.alive = False
            self.in_combat = False
            _record('death', self.label, text.strip(), tag='death')
        if 'the blast was fatal' in low:
            self.alive = False
            _record('death', self.label, text.strip(), tag='death')
        if 'combat begins!' in low:
            self.in_combat = True
            _record('combat', self.label, 'Combat begins!', tag='combat')
        if "you're not in a fight" in low or "you're not fighting anything" in low:
            self.is_attacker = False
            self.in_combat = False
        if 'joins ' in low and 'in fighting' in low:
            self.is_attacker = True
        if any(p in low for p in ('you miss', 'you strike', 'misses', 'strikes')):
            self.is_attacker = True
        if 'there is' in low:
            self.monster_present = True
        if ('have slain' in low or 'slays' in low or 'is slain!' in low
                or 'turns to stone as it dies' in low):
            self.monster_dead = True
            self.in_combat = False
            _record('combat', self.label, 'monster defeated', tag='kill')

        # --- Death Amulet gamble (Amulet of Life halves it) ---
        if 'possibility of instant death' in low or 'deadly power stirs' in low:
            _record('gamble', self.label, text.strip(), tag='death-amulet')
        if 'you live!' in low:
            _record('gamble', self.label, text.strip(), tag='death-amulet')

        # --- STORM weapon ---
        if 'accept thee as' in low or 'my servant' in low:
            _record('storm', self.label, text.strip(), tag='storm')
        if 'asserts its will' in low:
            _record('storm', self.label, text.strip(), tag='storm')
        if 'screams in glee' in low:
            _record('storm', self.label, text.strip(), tag='storm')
        if 'howls in rage' in low or 'howls in jealous rage' in low or 'you are not mine' in low:
            _record('storm', self.label, text.strip(), tag='storm-reject')

        # --- Ammo ---
        if 'rounds now ready' in low or 'now ready' in low:
            _record('ammo', self.label, text.strip(), tag='ammo')
        if 'try use to load ammunition' in low or 'no rounds ready' in low:
            _record('ammo', self.label, text.strip(), tag='ammo')
        if 'missile: first strike' in low:
            _record('combat', self.label, text.strip(), tag='ammo')

        # --- Crystal Pendant / tactical ambush ---
        if 'preventing turn to stone by' in low:
            _record('pendant', self.label, text.strip(), tag='petrify')
        if 'happens to see you are' in low:
            _record('pendant', self.label, text.strip(), tag='petrify')
        if any(s in low for s in ('to the front!', 'on the flank!', 'to the rear!')):
            _record('ambush', self.label, text.strip(), tag='ambush')
        if 'caught off guard' in low or 'too clever to be caught off guard' in low:
            _record('ambush', self.label, text.strip(), tag='ambush')

        # --- LASSO outcome (bumped, not just booleaned -- see __init__'s
        # docstring on why a stray-broadcast race needs a counter here).
        # 'name your horse' is checked against the PROMPT field instead,
        # in _recv_one() right after this call -- it arrives via
        # ctx.prompt(), never in a message's lines, so it can never match
        # here (see _recv_one()'s comment for the desync this caused live).
        if any(p in low for p in (
            'you practice with the lasso', 'only 3 allies allowed',
            'only 1 mount per customer', "you're not in a fight", "you're not fighting anything",
        )):
            self._bump('lasso_outcome_count')

        # --- CAST outcome (same counter reasoning). 'cast which spell
        # number' is also a ctx.prompt() -- checked in _recv_one() too. ---
        if any(p in low for p in (
            'you have no spells', "you'll need to be in combat first",
        )):
            self._bump('cast_prompt_count')

        # --- Mount / charge ---
        if 'you capture the horse' in low:
            _record('mount', self.label, text.strip(), tag='mount')
        if 'joins your party as a mount' in low:
            self.mount_captured = True
            _record('mount', self.label, text.strip(), tag='mount')
        if 'you climb onto' in low:
            self.mounted = True
            _record('mount', self.label, text.strip(), tag='mount')
        if 'you dismount' in low:
            self.mounted = False
            _record('mount', self.label, text.strip(), tag='mount')
        if 'get first strike' in low or "didn't get first strike" in low:
            self.charge_eligible = 'manage to get first strike' in low
            _record('charge', self.label, text.strip(), tag='charge')
        if 'retain your mount' in low or 'knocks you from your mount' in low:
            _record('charge', self.label, text.strip(), tag='charge')

        # --- LURK (commands/lurk.py -- fire over your allies' shoulders) ---
        if 'fire over' in low and 'ally' in low:
            _record('lurk', self.label, text.strip(), tag='lurk')
        if 'lurk behind your allies' in low:
            _record('lurk', self.label, text.strip(), tag='lurk')
        if 'attacks you, but strikes' in low and 'instead' in low:
            _record('lurk', self.label, text.strip(), tag='lurk')

        # --- Spellcasting (PC and monster) ---
        if 'spell successful' in low or 'spell backfired' in low:
            _record('spell', self.label, text.strip(), tag='spell-pc')
        if 'casts an endurance spell' in low or 'casts a destroyer spell' in low:
            _record('spell', self.label, text.strip(), tag='spell-monster')
        if 'casts turn to stone on you' in low:
            _record('spell', self.label, text.strip(), tag='spell-monster')

        # --- Flavor: critical hits, double attacks, scare, statue, gold ---
        if 'critical hit' in low:
            _record('exchange', self.label, text.strip(), tag='critical')
        if 'double attack' in low:
            _record('exchange', self.label, text.strip(), tag='double-attack')
        if 'scares' in low and 'away' in low:
            _record('exchange', self.label, text.strip(), tag='scare')
        if 'gold pieces on' in low:
            _record('loot', self.label, text.strip(), tag='loot')
        if 'turns to stone as it dies' in low:
            _record('exchange', self.label, text.strip(), tag='statue')

        # Compact round-by-round exchange narration.
        if any(p in low for p in ('strikes ', 'misses ', 'strike ', 'miss ', 'hits you for', 'hits ')):
            if not any(p in low for p in ('critical', 'double attack')):
                _record('exchange', self.label, text.strip())

    async def drain_until(self, stop: callable, *, max_msgs: int = 400, timeout: float = 5.0) -> bool:
        for _ in range(max_msgs):
            msg = await self._recv_one(timeout=timeout)
            if msg is None:
                return False
            if stop(self):
                return True
        return False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def say_and_await(bot: Bot, command: str, counter_attr: str, *, timeout: float = 8.0) -> bool:
    """Send *command* and wait until *counter_attr* (e.g. 'lasso_outcome_count')
    increments -- proof a message matching that specific outcome actually
    arrived, immune to an unrelated same-tick broadcast (from the other bot's
    own fight) landing a 'main>' prompt on this connection first. Returns
    False on timeout."""
    before = getattr(bot, counter_attr)
    await bot.say(command)
    for _ in range(40):
        msg = await bot._recv_one(timeout=timeout)
        if msg is None:
            return False
        if getattr(bot, counter_attr) > before:
            return True
    return False


async def goto(bot: Bot, level: int, room: int, label: str) -> None:
    ok = await say_and_await(bot, f'#{level} {room}', 'arrival_count')
    if not ok:
        _log(f'  [{bot.label}] *** teleport to level {level} room {room} never confirmed ***')
    else:
        # commands/teleport.py sends "You appear in a flash of light." (what
        # bumped arrival_count above) THEN separately calls _show_room(ctx),
        # which is its own distinct wire message -- leaving it unread here
        # desyncs every reply after this by exactly one message (each
        # subsequent command would read the PREVIOUS command's leftover
        # reply instead of its own -- exactly the bug that made 'attack'
        # read back as a stale room description in an earlier run).
        await bot.drain_until(lambda b: b.is_main_prompt())
    _record('teleport', bot.label, f'teleported to level {level} room {room} ({label})', tag='travel')


async def look_confirm(bot: Bot) -> bool:
    bot.monster_present = False
    await bot.say('look')
    await bot.drain_until(lambda b: b.is_main_prompt())
    return bot.monster_present


async def deploy_order(bot: Bot) -> None:
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE: ORDER -- tactical deployment ({bot.label})\n{"#" * WIDTH}')
    await bot.say('order')
    await bot.drain_until(lambda b: 'change this' in b.last_prompt.lower())
    await bot.say('Y')
    for _ in range(2):   # 2 servants -> 2 slots filled, Rear Guard stays empty
        got = await bot.drain_until(
            lambda b: 'new point man' in b.last_prompt.lower()
            or 'new flank guard' in b.last_prompt.lower()
            or 'new rear guard' in b.last_prompt.lower()
            or b.is_main_prompt()
        )
        if not got or bot.is_main_prompt():
            break
        await bot.say('1')
    await bot.drain_until(lambda b: b.is_main_prompt())
    _record('order', bot.label, 'servants deployed: Point/Flank', tag='ambush')


async def ready_weapon(bot: Bot, name: str) -> None:
    await bot.say(f'ready {name}')
    await bot.drain_until(lambda b: b.is_main_prompt())


async def load_ammo(bot: Bot, item_name: str) -> None:
    await bot.say(f'use {item_name}')
    await bot.drain_until(lambda b: b.is_main_prompt())


# ---------------------------------------------------------------------------
# Fight loops
# ---------------------------------------------------------------------------

async def leader_fight(bot: Bot, *, mount_charge: bool = False, max_rounds: int = 40,
                        started: asyncio.Event | None = None,
                        may_stop: asyncio.Event | None = None,
                        lurk_round: int | None = None) -> None:
    """Drive a fight as the LEADER: start it with 'attack', then answer the
    Command> menu every round until the monster or the leader dies.
    mount_charge=True picks 'c' (CHARGE) whenever the game says charge is
    available this round, else 'a' (plain attack). lurk_round, if given,
    picks 'l' (LURK -- commands/lurk.py, requires a living ally) on that
    one round number instead, then resumes normal attacks. Sets *started*
    the instant "Combat begins!" is actually seen -- callers use this to
    hold a second bot off attacking in the same room until this one has
    genuinely become the fight's leader (racing two 'attack's in the same
    room lets the second one open its OWN session and become a second
    leader, permanently stuck in its own Command> menu -- see this
    module's docstring)."""
    await bot.say('attack')
    combat_seen = False
    round_no = 0
    for _ in range(max_rounds * 3):
        msg = await bot._recv_one(timeout=5.0)
        if msg is None:
            return
        if bot.in_combat:
            combat_seen = True
            if started is not None and not started.is_set():
                started.set()
        if bot.monster_dead and may_stop is not None:
            may_stop.set()
        # Deliberately NOT "combat_seen and not bot.in_combat: return" here --
        # a kill can still have trailing messages in flight (loot, the ~50%
        # shadow-ally recruit offer) after in_combat already clears. Only a
        # genuine "[HH:MM] main> " prompt (is_main_prompt(); mid-fight/mid-
        # reply prompts are the bare "main" tag, which doesn't match) means
        # every message belonging to this fight has actually been drained --
        # returning early here left the connection mid-conversation for the
        # NEXT command to stumble into (observed live: an admin teleport
        # typed right after a kill got silently swallowed as the answer to
        # a still-pending "Let them join?" prompt instead of running as a
        # command at all).
        if bot.is_main_prompt():
            return
        if not bot.alive:
            return
        if bot.last_prompt.rstrip().lower().endswith('command>'):
            round_no += 1
            if lurk_round is not None and round_no == lurk_round:
                choice = 'l'
            elif mount_charge and bot.charge_eligible:
                choice = 'c'
            else:
                choice = 'a'
            await bot.say(choice)


async def bystander_action(bot: Bot, command: str, *,
                            stop: callable | None = None) -> None:
    """One bystander action from the main prompt (e.g. 'attack', 'lasso',
    'cast'). Reactive: waits for whatever actually comes back rather than
    a fixed number of messages.

    Defensive: a bystander's 'attack' sent the instant another player's
    kill lands can race the room's "monster's dead" state and open a
    brand-new fight against a freshly-restocked copy of the same monster,
    with THIS bot as its (unwanted) leader (see this module's docstring).
    e[X]it only skips one round's menu without leaving the fight
    (engine.py: "no attack, no flee attempt -- just skip the turn"), so
    the actual recovery is to just finish this small extra fight with
    plain attacks, same as leader_fight()."""
    await bot.say(command)
    default_stop = lambda b: b.is_main_prompt()
    ok = await bot.drain_until(stop or default_stop, timeout=6.0)
    if not ok and bot.last_prompt.rstrip().lower().endswith('command>'):
        _log(f'  [{bot.label}] *** unexpectedly leading a fight -- finishing it off ***')
        for _ in range(30):
            if not bot.last_prompt.rstrip().lower().endswith('command>'):
                break
            await bot.say('a')
            if not await bot.drain_until(
                lambda b: b.is_main_prompt() or b.last_prompt.rstrip().lower().endswith('command>'),
                timeout=5.0,
            ):
                break


async def bystander_loop(bot: Bot, rounds: int, *, may_stop: asyncio.Event | None = None) -> None:
    """Keep attacking as a bystander every round for up to *rounds* swings,
    stopping early if the monster dies, the bot dies, or may_stop fires."""
    for _ in range(rounds):
        if bot.monster_dead or not bot.alive or (may_stop is not None and may_stop.is_set()):
            return
        await bystander_action(bot, 'attack')


# ---------------------------------------------------------------------------
# Phase 0: Death Amulet gamble, then STORM BOW, ammo, spellbook is pre-seeded
# ---------------------------------------------------------------------------

async def phase_death_amulet(hero: Bot) -> bool:
    """Returns False if the gamble killed her (caller should abort the run)."""
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 0: The Death Amulet gamble (Amulet of Life carried)\n{"#" * WIDTH}')
    await hero.say('ready death amulet')
    await hero.drain_until(lambda b: 'still want to' in b.last_prompt.lower())
    await hero.say('Y')
    await hero.drain_until(lambda b: b.is_main_prompt() or not b.alive)
    if not hero.alive:
        _log('\n  *** sylvanwynd perished readying the Death Amulet -- rerun the script. ***')
        return False
    _log('\n  *** sylvanwynd survives the Death Amulet! ***')
    return True


async def phase_storm_bow(hero: Bot) -> None:
    """Buy the STORM BOW live from the Armory (shoppe/armory.py) rather
    than pre-seeding it -- see setup_epic_battle_account.py's _seed_gear()
    docstring: carrying it alongside the Death Amulet, in either order,
    triggers ready.py's STORM jealousy/rejection mechanic and destroys it
    before the run ever gets to use it. Bought fresh here, nothing else
    is competing for the readied slot when she READYs it afterward."""
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 0b: Armory -- buy the STORM BOW, ready it, load arrows\n{"#" * WIDTH}')
    await hero.say('down')
    await hero.drain_until(lambda b: 'shoppe' in b.last_prompt.lower())
    await hero.say('A')
    await hero.drain_until(lambda b: 'protection or' in b.last_prompt.lower())
    await hero.say('W')
    await hero.drain_until(lambda b: 'buy or' in b.last_prompt.lower())
    await hero.say('B')
    await hero.drain_until(lambda b: 'your choice' in b.last_prompt.lower())
    await hero.say('34')   # weapons.json #34 -- STORM BOW
    await hero.drain_until(lambda b: 'try it out' in b.last_prompt.lower())
    await hero.say('N')
    await hero.drain_until(lambda b: 'buy it' in b.last_prompt.lower())
    await hero.say('Y')
    await hero.drain_until(lambda b: 'your choice' in b.last_prompt.lower())
    _record('item', hero.label, 'bought a STORM BOW from the Armory', tag='storm')
    await hero.say('Q')
    await hero.drain_until(lambda b: 'buy or' in b.last_prompt.lower())
    await hero.say('Q')
    await hero.drain_until(lambda b: 'shoppe' in b.last_prompt.lower())
    await hero.say('X')
    await hero.drain_until(lambda b: b.is_main_prompt())

    await ready_weapon(hero, 'storm bow')
    await load_ammo(hero, 'arrows')


# ---------------------------------------------------------------------------
# Phase 1: MEDUSA -- pendant, tactical ambush, STORM assert, ammo, leader CHARGE n/a
# ---------------------------------------------------------------------------

async def phase_medusa(hero: Bot) -> None:
    """Hero solos this one -- thornshield staying elsewhere avoids the race
    where its bystander 'attack' lands the instant after hero's kill and
    opens a second, unwanted fresh fight against the same room/monster
    number (see this module's docstring: _monster_in_room() has no
    "already dead" gate, only per-player dead_monsters, so a second
    attacker always gets a fresh full-HP copy). Not needed here anyway --
    pendant/ambush/STORM/ammo are all leader-only mechanics hero gets
    fighting alone."""
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 1: MEDUSA -- Crystal Pendant + tactical ambush + STORM BOW\n{"#" * WIDTH}')
    level, room = _MEDUSA_ROOM
    await goto(hero, level, room, 'STONE ROOM')
    await hero.say('get crystal pendant')
    await hero.drain_until(lambda b: b.is_main_prompt())
    _record('item', hero.label, 'picked up the Crystal Pendant', tag='petrify')
    await look_confirm(hero)

    # No lurk_round here -- MEDUSA has only ~8-18 HP and the STORM BOW's
    # "asserts its will" auto-attack (30%/round) bypasses the Command> menu
    # entirely when it fires, so this fight routinely ends in round 1
    # before any menu (LURK's only leader-mode entry point) ever appears.
    # LURK is demonstrated in the RONNEY fight instead (phase_ronney),
    # where hero fights as a BYSTANDER and can just type 'lurk' from the
    # main prompt (commands/lurk.py) -- and RONNEY reliably survives many
    # rounds, unlike MEDUSA/GUARDIAN.
    await leader_fight(hero, max_rounds=40)
    _log(f'\n  *** MEDUSA phase complete: hero_alive={hero.alive} monster_dead={hero.monster_dead} ***')


# ---------------------------------------------------------------------------
# Phase 2: WILD HORSE -- LASSO (bystander) + MOUNT
# ---------------------------------------------------------------------------

async def find_horse_room(bot: Bot) -> int | None:
    for room in _HORSE_ROOMS:
        await goto(bot, 1, room, 'wild horse candidate')
        if await look_confirm(bot):
            _log(f'\n  *** wild horse found in room {room} ***')
            return room
    return None


async def phase_wild_horse(hero: Bot, anchor: Bot) -> None:
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 2: WILD HORSE -- LASSO + MOUNT\n{"#" * WIDTH}')
    room = await find_horse_room(anchor)
    if room is None:
        _log('\n  *** WARNING: wild horse not found in any candidate room -- skipping mount phases ***')
        return
    await goto(hero, 1, room, 'wild horse room')

    started = asyncio.Event()
    fight_task = asyncio.create_task(leader_fight(anchor, max_rounds=30, started=started))
    await started.wait()

    await bystander_action(hero, 'attack')
    if not hero.is_attacker:
        _log('  [sylvanwynd] did not register as an attacker -- aborting lasso')
        await asyncio.wait_for(fight_task, timeout=30)
        return

    await say_and_await(hero, 'lasso', 'lasso_outcome_count')
    if 'name your horse' in hero.last_prompt.lower():
        # Deliberately answer with a too-short name first to exercise the
        # reprompt path, then send the real name once it reprompts.
        hero.name_warning_seen = False
        await say_and_await(hero, 'AB', 'lasso_outcome_count')
        await hero.say('STARDUST')
        await hero.drain_until(lambda b: b.mount_captured or b.is_main_prompt())

    await asyncio.wait_for(fight_task, timeout=30)
    _log(f'\n  *** LASSO {"SUCCEEDED" if hero.mount_captured else "FAILED"} ***')

    if hero.mount_captured:
        await hero.say('mount')
        await hero.drain_until(lambda b: b.is_main_prompt())


# ---------------------------------------------------------------------------
# Phase 3: GUARDIAN -- mounted CHARGE, monster spellcasting, re_animates/fire
# ---------------------------------------------------------------------------

async def phase_guardian(hero: Bot) -> None:
    """Hero solos this one too, same race-avoidance reasoning as
    phase_medusa -- CHARGE is a leader-only menu option anyway."""
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 3: GUARDIAN -- mounted CHARGE + monster spellcasting\n{"#" * WIDTH}')
    level, room = _GUARDIAN_ROOM
    await goto(hero, level, room, 'Rocky Ravine')
    await look_confirm(hero)

    await leader_fight(hero, mount_charge=True, max_rounds=40)
    _log(f'\n  *** GUARDIAN phase complete: hero_alive={hero.alive} monster_dead={hero.monster_dead} '
         f'mounted={hero.mounted} ***')

    # GUARDIAN is flagged re_animates -- combat/engine.py's _record_kill()
    # deliberately never adds a re_animates monster to player.dead_monsters
    # (SPUR precedent: "The body twitches strangely!" -- it's eligible for a
    # full re-encounter, not permanently dead). That means
    # commands/teleport.py's tough-monster block (_room_monster()) still
    # sees GUARDIAN as "present" forever and refuses a '#' teleport straight
    # out of this room ("The GUARDIAN casts a 'Freeze Adventurer' spell!"),
    # even though it's freshly slain. A normal walk isn't gated by that
    # check, so leave on foot first, then admin-teleport from there.
    await hero.say('north')
    await hero.drain_until(lambda b: b.is_main_prompt())


# ---------------------------------------------------------------------------
# Phase 4: RONNEY -- final boss. thornshield leads, sylvanwynd CASTs + finishes.
# ---------------------------------------------------------------------------

async def phase_ronney(hero: Bot, anchor: Bot) -> None:
    _log(f'\n\n{"#" * WIDTH}\n#  PHASE 4: RONNEY -- the final boss (no_flee, no_article)\n{"#" * WIDTH}')
    level, room = _RONNEY_ROOM
    await goto(hero, level, room, 'Kings Chamber')
    await goto(anchor, level, room, 'Kings Chamber')
    await look_confirm(anchor)

    started = asyncio.Event()
    may_stop = asyncio.Event()
    fight_task = asyncio.create_task(leader_fight(anchor, max_rounds=50, started=started, may_stop=may_stop))
    await started.wait()

    # Bot.monster_dead/is_attacker are set once from belief-tracking and
    # never auto-reset between fights (see Bot.__init__) -- by phase 4,
    # hero.monster_dead is already True from GUARDIAN's kill in phase 3,
    # which silently skipped both CAST and LURK below every time until
    # this reset was added (their gate is "and not hero.monster_dead").
    hero.monster_dead = False
    hero.is_attacker = False

    await bystander_action(hero, 'attack')
    if hero.is_attacker and not hero.monster_dead:
        await say_and_await(hero, 'cast', 'cast_prompt_count')
        if ('cast which spell number' in hero.last_prompt.lower()
                or 'cast which spell number' in hero.last_lines_text.lower()):
            await bystander_action(hero, '1')   # SLAUGHTER: M-type, 90% cast chance

    # LURK -- fire over BATMAN/ARTHUR DENT's shoulders and force RONNEY's
    # counter-attack onto one of them instead of the hero (commands/lurk.py
    # is a top-level command, same as 'attack', so this works fine as a
    # bystander -- unlike CHARGE/the Command> menu's [L]urk option, which
    # only exists for a fight's LEADER). RONNEY reliably survives many
    # rounds (tough, double_attacks), unlike MEDUSA/GUARDIAN.
    if not hero.monster_dead and not may_stop.is_set():
        await bystander_action(hero, 'lurk')

    await bystander_loop(hero, 30, may_stop=may_stop)
    await asyncio.wait_for(fight_task, timeout=120)
    _log(f'\n  *** RONNEY phase complete: hero_alive={hero.alive} anchor_alive={anchor.alive} '
         f'monster_dead={hero.monster_dead or anchor.monster_dead} ***')


async def run_phase(label: str, coro, *, timeout: float = 90.0):
    """Run one phase coroutine under a hard wall-clock timeout so a stray
    hang (observed live: an occasional multi-minute stall with both bot
    and server sitting idle in epoll_wait, never reproduced against a
    bare single-connection probe -- some asyncio scheduling edge case
    between the two concurrent bot tasks, not a game-logic bug) can never
    block the whole run. Logs and moves on to the next phase instead of
    hanging forever; the resulting transcript just has a gap where that
    phase's mechanics didn't get exercised."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        _log(f'\n  *** PHASE {label} TIMED OUT after {timeout}s -- skipping to the next phase ***')
        _record('outcome', 'system', f'{label} timed out, skipped', tag='error')
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def epic_battle(host: str, port: int) -> None:
    _log(f'\n\n{"#" * WIDTH}\n#  EPIC BATTLE: sylvanwynd & thornshield\n{"#" * WIDTH}')

    hero   = Bot('sylvanwynd',  'sylvanwynd')
    anchor = Bot('thornshield', 'thornshield')

    for b in (hero, anchor):
        if not await b.connect(host, port):
            _log(f'  [{b.label}] could not connect -- aborting')
            return
        await b.say(f'connect {b.user} {_PASSWORD}')
        await b.drain_until(lambda x: x.is_main_prompt())

    await run_phase('ready-crossbow', ready_weapon(anchor, 'crossbow'), timeout=30)
    await run_phase('load-bolts', load_ammo(anchor, 'bolts'), timeout=30)

    survived = await run_phase('death-amulet', phase_death_amulet(hero), timeout=30)
    if not survived:
        for b in (hero, anchor):
            await b.close()
        return

    await run_phase('storm-bow', phase_storm_bow(hero), timeout=60)
    await run_phase('order', deploy_order(hero), timeout=30)

    await run_phase('medusa', phase_medusa(hero), timeout=90)
    await run_phase('wild-horse', phase_wild_horse(hero, anchor), timeout=90)
    await run_phase('guardian', phase_guardian(hero), timeout=90)
    await run_phase('ronney', phase_ronney(hero, anchor), timeout=150)

    _log(f'\n\n{"#" * WIDTH}\n#  EPILOGUE\n{"#" * WIDTH}')
    if hero.mounted:
        await hero.say('dismount')
        await hero.drain_until(lambda b: b.is_main_prompt())
    await hero.say('stats')
    await hero.drain_until(lambda b: b.is_main_prompt())

    _log(f'\n{"=" * WIDTH}\n  OUTCOME SUMMARY\n{"=" * WIDTH}')
    _log(f'  sylvanwynd  alive={hero.alive}')
    _log(f'  thornshield alive={anchor.alive}')
    _record('outcome', 'system', 'epic battle complete')

    for b in (hero, anchor):
        await b.close()
    _log('\n  Epic battle complete.')


async def main(host: str, port: int) -> None:
    global _logfile
    _logfile = LOG_FILE.open('w', encoding='utf-8')
    _log(f'# bot_epic_battle session  {datetime.now().isoformat(timespec="seconds")}')
    _log(f'# {host}:{port}')

    await epic_battle(host, port)

    _log(f'\n{"=" * WIDTH}\n  Session complete.\n{"=" * WIDTH}\n# log written to {LOG_FILE}')
    _logfile.close()
    EVENTS_FILE.write_text(json.dumps(_events, indent=2))
    print(f'Log saved to {LOG_FILE}')
    print(f'Events saved to {EVENTS_FILE}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TADA epic-battle reactive bot demo')
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
