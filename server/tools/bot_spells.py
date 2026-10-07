#!/usr/bin/env python3
"""bot_spells.py -- end-to-end check over real sockets of the spells from
PR #73 (ELEVATOR UP/DOWN, TRANSPORT TO SHOPPE, DISPEL POISON, APPLE A DAY,
DRUID HEALTH, WIZARD'S GLOW -- commands/cast.py) and PR #74's
practice-raised cast % (player.spell_cast_chance, spellbook.py).

Two ways to run it:

  default      Self-contained, same as tools/bot_helpstaff.py: seeds two
               throwaway characters into a fresh temporary save directory,
               starts its own tools/run_throwaway_server.py on it (so it
               runs THIS checkout's code), runs the scenario, then shuts
               the server down. Never touches run/server or the real server.

  --from-live  The same, but the temporary save directory starts as a copy
               of the live server's saves (--live-dir, default the main
               checkout's run/server) -- real accounts, boards, guild
               state -- with the two bot characters seeded over the top of
               the copy. The live server and its files are only read.

A real `--live` run against the running server isn't offered: the bot
needs a character seeded with a full Spell Book, poison and disease, and
the only safe way to do that is to write the save file before the server
loads it -- not something to do to a server that's up.

Cast:
  botmage   Wizard, INT 20 (so every roll succeeds: b = max(3, 20-INT) = 3
            puts the roll at 1.01-4, under every spell's chance/10),
            poisoned and diseased, HP 10, STR 8, on level 3 room 91
            ("Wandering Path"). Spell Book: WHEATIES x2, DISPEL POISON x2,
            APPLE A DAY, DRUID HEALTH, WIZARD'S GLOW x2, ELEVATOR UP,
            ELEVATOR DOWN, TRANSPORT TO SHOPPE.
  botwatch  Fighter standing in the same room, to see botmage vanish.

Rooms: level 2 has no room 91, so ELEVATOR UP has to use the nearest-room
search (commands/cast.py's _landing_room) -- room 76, "Rough Tunnel" --
and level 3 has no room 76, so ELEVATOR DOWN lands in 75, "Side Of
Mountain". All three are monster-free and unflagged. The expected rooms
are recomputed from the level files at start-up, not hard-coded.

Checks:
  A  INV lists the Spell Book's pages with their cast % (PR #74)
  B  practice: WHEATIES succeeds and announces 72%, then the second copy
     casts and announces 74%; CAST's list shows 72% in between
  C  DISPEL POISON cures poison; the second copy, with nothing to cure,
     says "Why? You weren't poisoned!" and fizzles
  D  APPLE A DAY cures disease
  E  DRUID HEALTH: "A blue glow surrounds you!", hit points return
  F  WIZARD'S GLOW: the glow line; STATS shows 20/20 rounds; the second
     copy says "Spell already in effect!"
  G  ELEVATOR UP: "You have entered <level 2>!", lands in the nearest
     room; botwatch sees "botmage shimmers and fades away!"
  H  ELEVATOR DOWN: back on level 3, nearest room again
  I  TRANSPORT TO SHOPPE: straight into the Merchant Shoppe; the Wizard's
     i2 shows WHEATIES at "Cast    : 74%"; leaving shows level 3 room 1
  J  (after quit) the save has spell_cast_chance WHEATIES=74, DISPEL
     POISON at 92 (its fizzle didn't add practice), poison and disease
     cleared, glow saved, level 3 room 1
  K  logging back in: "Your Wizard's Glow spell has dissipated.", and
     STATS shows "Wizard Glow: Not cast"

Usage:
    .venv/bin/python3 tools/bot_spells.py [--port 34196] [--keep-dir]
    .venv/bin/python3 tools/bot_spells.py --from-live [--live-dir DIR]

Written 2026-10-06.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))
sys.path.insert(0, str(_SERVER_DIR / 'tools'))

THROWAWAY_PASSWORD = 'spell-bots'   # throwaway accounts in a throwaway dir
START_LEVEL, START_ROOM = 3, 91
DEFAULT_LIVE_DIR = Path('/home/ryan/Documents/c64/TADA/TADA/server/run/server')

# (spell number, copies) -- see shoppe/wizard.py's SPELLS.
SPELL_BOOK = [(2, 2), (16, 2), (17, 1), (18, 1), (19, 2), (5, 1), (12, 1), (14, 1)]

transcript: list[str] = []


def log(text: str = '') -> None:
    print(text)
    transcript.append(text)


# ---------------------------------------------------------------------------
# Expected rooms, from the real level files
# ---------------------------------------------------------------------------

def expected_rooms() -> dict:
    """Where ELEVATOR UP / DOWN should land, via the same _landing_room()
    the server uses, plus the names to look for in the room display."""
    import logging
    from types import SimpleNamespace
    from base_classes import Map
    from commands.cast import _landing_room
    from shoppe.elevator import level_name

    logging.disable(logging.CRITICAL)
    game_map = Map()
    for n in (2, 3):
        game_map.read_map(str(_SERVER_DIR / f'level_{n}.json'), level=n)
    logging.disable(logging.NOTSET)
    ctx = SimpleNamespace(server=SimpleNamespace(game_map=game_map))
    up = _landing_room(ctx, 2, START_ROOM)
    down = _landing_room(ctx, 3, up)
    return {
        'up': up, 'up_name': game_map.get_room(2, up).name, 'level2': level_name(2),
        'down': down, 'down_name': game_map.get_room(3, down).name, 'level3': level_name(3),
        'room1_name': game_map.get_room(3, 1).name,
    }


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def seed_accounts(save_dir: Path) -> None:
    """Write the two characters straight into save_dir, bypassing the
    creation wizard (same approach as tools/setup_bot_accounts.py)."""
    import net_common
    net_common.run_server_dir = str(save_dir)
    import spellbook
    from base_classes import Gender, PlayerClass, PlayerRace, PlayerStat
    from items import build_spell_from_raw
    from player import Player
    from shoppe.wizard import SPELLS
    from survival import apply_disease, apply_poison

    by_number = {sp['number']: sp for sp in SPELLS}
    (save_dir / 'net').mkdir(parents=True, exist_ok=True)
    for name, char_class in (('botmage', PlayerClass.WIZARD), ('botwatch', PlayerClass.FIGHTER)):
        player = Player(id=name, name=name, char_class=char_class, char_race=PlayerRace.HUMAN,
                        gender=Gender.MALE, map_level=START_LEVEL, map_room=START_ROOM)
        player.creation_done = True
        player.hit_points = 500
        if name == 'botmage':
            player.stats[PlayerStat.INT] = 20
            player.stats[PlayerStat.STR] = 8
            player.hit_points = 10
            player.wizard_glow = None
            player.spell_cast_chance = {}
            apply_poison(player)
            apply_disease(player)
            book = spellbook.ensure_spellbook(player)
            for number, copies in SPELL_BOOK:
                book.contents.add(build_spell_from_raw(by_number[number], id_number=number),
                                  quantity=copies)
        player.unsaved_changes = True
        if not player.save(force=True):
            raise RuntimeError(f'could not save {name}')
        (save_dir / 'net' / f'login-{name}.json').write_text(
            json.dumps({'password': net_common.hash_password(THROWAWAY_PASSWORD)}))


def saved(save_dir: Path, name: str) -> dict:
    return json.loads((save_dir / f'player-{name}.json').read_text())


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def start_server(save_dir: Path, port: int) -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(_SERVER_DIR / 'tools' / 'run_throwaway_server.py'),
         '--port', str(port), '--petscii-port', str(port + 1),
         '--dir', str(save_dir)],
        cwd=str(_SERVER_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError('throwaway server exited during startup')
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return proc
        except OSError:
            time.sleep(0.5)
    proc.terminate()
    raise RuntimeError(f'throwaway server never listened on {port}')


# ---------------------------------------------------------------------------
# One connection (tools/bot_helpstaff.py's Bot)
# ---------------------------------------------------------------------------

class Bot:
    def __init__(self, name: str, password: str):
        self.name = name
        self.password = password
        self.reader = self.writer = None
        self.last_prompt = ''
        self.prompts: list[str] = []    # every non-empty prompt received
        self.lines: list[str] = []      # every line received, in order

    async def connect(self, host: str, port: int) -> None:
        self.reader, self.writer = await asyncio.open_connection(host, port)
        init = await self.recv(timeout=5)
        await self._send({'server_id': init.get('server_id', 'test_server'),
                          'server_key': init.get('server_key', 'test_key')})
        # Terminal type, then the paging pre-login banner (PR #29).
        for _ in range(60):
            if self.last_prompt.rstrip().endswith('login>'):
                break
            if await self.recv(timeout=5) is None:
                raise RuntimeError(f'{self.name}: no login prompt (last {self.last_prompt!r})')
            low = self.last_prompt.lower()
            if 'terminal type' in low:              # plain text: no ANSI
                await self._send({'lines': ['P'], 'mode': 'login'})  # codes in the lines
            elif '-- more' in low or '-- end' in low:
                await self._send({'lines': [''], 'mode': 'login'})
        else:
            raise RuntimeError(f'{self.name}: no login prompt (last {self.last_prompt!r})')
        log(f'  [{self.name}] -> connect {self.name} ****')
        await self._send({'lines': [f'connect {self.name} {self.password}'], 'mode': 'game'})
        for _ in range(150):
            msg = await self.recv(timeout=6)
            if msg is None:
                raise RuntimeError(f'{self.name}: login stalled at {self.last_prompt!r}')
            if self.at_main():
                return
            if msg.get('prompt') and not self.at_marker():
                await self.say('')
        raise RuntimeError(f'{self.name}: never reached the main prompt')

    async def _send(self, obj: dict) -> None:
        self.writer.write(json.dumps(obj).encode() + b'\n')
        await self.writer.drain()

    async def say(self, line: str) -> None:
        log(f'  [{self.name}] -> {line!r}')
        await self._send({'lines': [line], 'mode': 'game'})

    async def recv(self, timeout: float) -> dict | None:
        try:
            raw = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        if not raw:
            return None
        msg = json.loads(raw)
        lines = msg.get('lines', [])
        if isinstance(lines, str):
            lines = [lines]
        for line in lines:
            if line:
                log(f'  [{self.name}] {line}')
                self.lines.append(line)
        self.last_prompt = msg.get('prompt', '') or ''
        if self.last_prompt:
            log(f'  [{self.name}] [{self.last_prompt}]')
            self.prompts.append(self.last_prompt)
        return msg

    def at_marker(self) -> bool:
        """A bare 'main'/'login' prompt announces the input mode -- never answer it."""
        return self.last_prompt.strip() in ('main', 'login')

    def at_main(self) -> bool:
        return self.last_prompt.rstrip().endswith('main>')

    async def until_main(self, *, answer=None, max_msgs: int = 200) -> bool:
        for _ in range(max_msgs):
            if await self.recv(timeout=6) is None:
                return False
            if self.at_main():
                return True
            if self.last_prompt and not self.at_marker():
                low = self.last_prompt.lower()
                reply = answer(self) if answer else None
                if reply is None and ('-- more' in low or '-- end' in low):
                    reply = ''
                if reply is not None:
                    await self.say(reply)
        return False

    async def settle(self, quiet: float = 1.5) -> list[str]:
        start = len(self.lines)
        while await self.recv(timeout=quiet) is not None:
            pass
        return self.lines[start:]

    async def run(self, line: str, *, answer=None) -> list[str]:
        """Send a command, read to the next main prompt, return its lines."""
        await self.settle(0.3)
        start = len(self.lines)
        await self.say(line)
        await self.until_main(answer=answer)
        return self.lines[start:]

    async def quit(self) -> None:
        await self.say('quit')
        await self.until_main(answer=lambda b: 'Y' if 'leave spur' in b.last_prompt.lower() else None,
                              max_msgs=30)
        self.writer.close()


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

failures: list[str] = []


def check(label: str, ok: bool, detail: str = '') -> None:
    log(f'{"PASS" if ok else "FAIL"}  {label}' + (f'\n      {detail}' if detail else ''))
    if not ok:
        failures.append(label)


def joined(lines) -> str:
    """The server wraps text to the terminal width: search lines as one string."""
    return ' '.join(' '.join(lines).split())


def has(lines, text: str) -> bool:
    return ' '.join(text.split()) in joined(lines)


def bare_prompt(bot: Bot) -> str:
    """The prompt without its "[HH:MM] " timestamp, lower-cased."""
    return re.sub(r'^\[\d\d:\d\d\]\s*', '', bot.last_prompt).strip().lower()


def spell_number(lines, name: str) -> str | None:
    """The row number CAST's "Known Spells" table gives *name* -- a long
    name wraps onto a continuation row ("TRANSPORT TO" / "SHOPPE"), so
    rows with an empty # cell are joined onto the one above."""
    rows: list[list[str]] = []
    for line in lines:
        parts = re.split(r'[|│║┃]', line)
        if len(parts) < 4:
            continue
        cells = [c.strip() for c in parts[1:-1]]
        if cells[0].isdigit():
            rows.append(cells[:2])
        elif not cells[0] and rows and cells[1]:
            rows[-1][1] = f'{rows[-1][1]} {cells[1]}'
    return next((number for number, label in rows if label == name), None)


async def cast(bot: Bot, name: str, *, answer=None) -> list[str]:
    """CAST, pick *name* at the "Spell #" prompt (msg['prompt'] -- see
    CLAUDE.md's bot notes), and answer any later prompts with *answer*."""
    mark = len(bot.lines)

    def _answer(b):
        if bare_prompt(b).startswith('spell #'):
            number = spell_number(b.lines[mark:], name)
            return number if number else 'Q'
        return answer(b) if answer else None

    return await bot.run('cast', answer=_answer)


def shoppe_walk():
    """Inside the Shoppe: W)izard, Y to learning, i2 (WHEATIES info), then
    Q out of the Wizard and Q out of the Shoppe."""
    state = {'shoppe': 0, 'learn': 0}

    def _answer(b):
        p = bare_prompt(b)
        if p.startswith('shoppe'):
            state['shoppe'] += 1
            return 'W' if state['shoppe'] == 1 else 'Q'
        if p.startswith('y/n'):
            return 'Y'
        if p.startswith('learn which spell'):
            state['learn'] += 1
            return 'i2' if state['learn'] == 1 else 'Q'
        return None
    return _answer


async def scenario(host: str, port: int, mage: Bot, watch: Bot, rooms: dict) -> None:
    for b in (watch, mage):
        log(f'\n== {b.name} logs in')
        await b.connect(host, port)
    for b in (watch, mage):
        await b.settle(0.5)

    log('\n== A: INV lists the Spell Book pages with their cast %')
    said = await mage.run('inv')
    check('A Spell Book pages show cast %',
          has(said, 'WHEATIES x2 (cast: 70%)') and has(said, "WIZARD'S GLOW x2 (cast: 90%)"),
          joined(said))

    log('\n== B: practice raises WHEATIES')
    said = await cast(mage, 'WHEATIES')
    check('B1 first WHEATIES succeeds and improves to 72%',
          has(said, 'Spell successful!') and has(said, 'improves: 72% to cast'), joined(said))
    said = await cast(mage, 'WHEATIES')
    check('B2 CAST list showed the second copy at 72%', has(said, '72%'), joined(said))
    check('B3 second WHEATIES improves to 74%', has(said, 'improves: 74% to cast'), joined(said))

    log('\n== C: DISPEL POISON')
    said = await cast(mage, 'DISPEL POISON')
    check('C1 DISPEL POISON cures poison', has(said, 'Poison.. gone!'), joined(said))
    said = await cast(mage, 'DISPEL POISON')
    check("C2 second copy: \"Why? You weren't poisoned!\" and fizzles",
          has(said, "Why? You weren't poisoned!") and has(said, 'Your spell fizzles...'),
          joined(said))

    log('\n== D: APPLE A DAY')
    said = await cast(mage, 'APPLE A DAY')
    check('D APPLE A DAY cures disease', has(said, 'You feel much better!'), joined(said))

    log('\n== E: DRUID HEALTH')
    said = await cast(mage, 'DRUID HEALTH')
    check('E DRUID HEALTH restores hit points',
          has(said, 'A blue glow surrounds you!') and has(said, 'Hit points return'), joined(said))

    log("\n== F: WIZARD'S GLOW")
    said = await cast(mage, "WIZARD'S GLOW")
    check('F1 the glow surrounds the caster', has(said, 'A shimmering glow surrounds you!'),
          joined(said))
    said = await mage.run('stats')
    check('F2 STATS shows 20/20 rounds', has(said, 'Wizard Glow: 20/20 rounds left'),
          joined(said))
    said = await cast(mage, "WIZARD'S GLOW")
    check('F3 second copy: "Spell already in effect!"', has(said, 'Spell already in effect!'),
          joined(said))

    log('\n== G: ELEVATOR UP')
    await watch.settle(0.3)
    watch_mark = len(watch.lines)
    said = await cast(mage, 'ELEVATOR UP')
    check(f"G1 lands on level 2 in nearest room {rooms['up']} ({rooms['up_name']})",
          has(said, 'Spell successful!') and has(said, f"You have entered {rooms['level2']}!")
          and has(said, rooms['up_name']), joined(said))
    await watch.settle(1.0)
    check('G2 botwatch sees botmage vanish',
          has(watch.lines[watch_mark:], 'botmage shimmers and fades away!'),
          joined(watch.lines[watch_mark:]))

    log('\n== H: ELEVATOR DOWN')
    said = await cast(mage, 'ELEVATOR DOWN')
    check(f"H back on level 3 in nearest room {rooms['down']} ({rooms['down_name']})",
          has(said, f"You have entered {rooms['level3']}!") and has(said, rooms['down_name']),
          joined(said))

    log('\n== I: TRANSPORT TO SHOPPE')
    said = await cast(mage, 'TRANSPORT TO SHOPPE', answer=shoppe_walk())
    check('I1 straight into the Merchant Shoppe',
          has(said, "merchant's annex") or has(said, 'Merchant Shoppe:'), joined(said))
    check("I2 Wizard's i2 shows WHEATIES at the practised 74%", has(said, 'Cast : 74%'),
          joined(said))
    check(f"I3 leaving the Shoppe shows level 3 room 1 ({rooms['room1_name']})",
          has(said[-15:], rooms['room1_name']), joined(said[-15:]))

    log('\n== botmage and botwatch quit')
    await mage.quit()
    await watch.quit()


async def relogin(host: str, port: int) -> None:
    log('\n== K: botmage logs back in')
    mage = Bot('botmage', THROWAWAY_PASSWORD)
    await mage.connect(host, port)
    said = await mage.settle(1.0)
    check("K1 login says the Wizard's Glow has dissipated",
          has(mage.lines, "Your Wizard's Glow spell has dissipated."), joined(mage.lines[-20:]))
    said = await mage.run('stats')
    check('K2 STATS shows "Wizard Glow: Not cast"', has(said, 'Wizard Glow: Not cast'),
          joined(said))
    await mage.quit()


def check_save(save_dir: Path) -> None:
    log('\n== J: botmage\'s save')
    data = saved(save_dir, 'botmage')
    chances = data.get('spell_cast_chance') or {}
    check('J1 WHEATIES remembered at 74%', chances.get('2') == 74, repr(chances))
    check('J2 DISPEL POISON at 92% (its fizzle added no practice)', chances.get('16') == 92,
          repr(chances))
    check('J3 poison and disease cleared',
          not data.get('poisoned') and not data.get('diseased'),
          f"poisoned={data.get('poisoned')} diseased={data.get('diseased')}")
    check('J4 glow saved until next login', data.get('wizard_glow') == 20,
          repr(data.get('wizard_glow')))
    check('J5 saved on level 3 room 1', (data.get('map_level'), data.get('map_room')) == (3, 1),
          f"level={data.get('map_level')} room={data.get('map_room')}")


async def run_all(port: int, save_dir: Path, rooms: dict) -> None:
    mage  = Bot('botmage', THROWAWAY_PASSWORD)
    watch = Bot('botwatch', THROWAWAY_PASSWORD)
    await scenario('127.0.0.1', port, mage, watch, rooms)
    await asyncio.sleep(1.0)            # let the quit saves land
    check_save(save_dir)
    await relogin('127.0.0.1', port)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--port', type=int, default=34196)
    parser.add_argument('--from-live', action='store_true',
                        help='start the throwaway save dir as a copy of the live saves')
    parser.add_argument('--live-dir', type=Path, default=DEFAULT_LIVE_DIR)
    parser.add_argument('--keep-dir', action='store_true', help='keep the temporary save dir')
    args = parser.parse_args()

    rooms = expected_rooms()
    log(f"Expected: L3 {START_ROOM} -> L2 {rooms['up']} ({rooms['up_name']}) "
        f"-> L3 {rooms['down']} ({rooms['down_name']})")

    tmp = Path(tempfile.mkdtemp(prefix='bot_spells_'))
    save_dir = tmp / 'server'
    if args.from_live:
        log(f'Copying live saves from {args.live_dir}')
        shutil.copytree(args.live_dir, save_dir)
    else:
        save_dir.mkdir(parents=True)
    seed_accounts(save_dir)

    proc = start_server(save_dir, args.port)
    try:
        asyncio.run(run_all(args.port, save_dir, rooms))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        if args.keep_dir:
            log(f'Save dir kept: {save_dir}')
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    log_path = _SERVER_DIR / 'tools' / 'bot_spells.log'
    log(f"\n{'ALL PASS' if not failures else f'{len(failures)} FAILED: ' + ', '.join(failures)}")
    log_path.write_text('\n'.join(transcript) + '\n')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
