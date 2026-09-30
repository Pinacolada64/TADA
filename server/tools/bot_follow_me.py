#!/usr/bin/env python3
"""bot_follow_me.py -- live end-to-end check of FOLLOW ME / STAY
(guild_follow.py, commands/follow.py, commands/stay.py) and the room
notices around a move (room_notices.py, simple_server.py's _move()).

Self-contained: seeds five throwaway characters into a fresh temporary
save directory, starts its own tools/run_throwaway_server.py on it, runs
the scenario over real sockets, then shuts the server down. Never touches
run/server or the real dev server on 34083.

Cast (level 1, all starting in room 41, "UNDERGROUND FOREST"):
  botleader  Claw guild -- says FOLLOW ME, walks, says STAY
  botfollow  Claw, Guild Follow on, online -- the live follower
  botcarried Claw, Guild Follow on, never logs in until the end -- the
             offline follower, carried along and dropped off by STAY
  botrival   Fist, Guild Follow on -- another guild: "stares at you"; then
             waits in room 42 to watch the leader arrive
  botwatch   Civilian -- stays in room 41 to watch the leader leave

Route 41 -east-> 42 -south-> 54 (STAY here) -north-> 42 alone. Chosen from
level_1.json for being neutral (STAY isn't blocked), monster-free, and not
desert/labyrinth terrain (encounters/desert.py). Room 30 would have made
a nicer-named route but is one of the wild horse's three rooms.

Checks:
  A  FOLLOW ME: the rival and the civilian stare, both Claw members agree
     (the live one after a "Take botfollow? [Y]/n" prompt, answered in
     msg['prompt'] -- see CLAUDE.md's bot notes), the live follower is told
     it's falling in behind
  B  first move, as one group: the leader reads "You leave east, with
     botfollow and botcarried following.", the room left hears "botleader
     leaves east, with ...", the room reached "botleader arrives from the
     west, with ...", and the follower gets only "You follow botleader
     east." -- then sees the new room with the leader already in it
  C  second move: the group moves again (same lines, south)
  D  STAY: both followers stay; the live one is told to stay
  E  the leader moves on alone: plain "botleader moves north." /
     "botleader enters from the south.", and no "You follow" for the
     follower
  F  the live follower's save puts it in room 54 (where it was left)
  G  the offline follower's save was rewritten to room 54 with
     followed_leader_name, it hears "You followed botleader to your
     current location." at login, and that one-shot name is cleared after

(The group lines replaced separate notices on 2026-09-30: before, bystanders
heard only about the leader, and the follower saw the leader "enter" after
it had already arrived.)

Usage:
    .venv/bin/python tools/bot_follow_me.py [--port 34192] [--keep-dir]

Written 2026-09-30.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))

PASSWORD = 'followme-bots'     # throwaway accounts in a throwaway dir
START, MIDDLE, STAY_ROOM = 41, 42, 54
FIRST_DIR, SECOND_DIR, BACK_DIR = 'east', 'south', 'north'

transcript: list[str] = []


def log(text: str = '') -> None:
    print(text)
    transcript.append(text)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def seed_accounts(save_dir: Path) -> None:
    """Write the five characters straight into save_dir, bypassing the
    creation wizard (same approach as tools/setup_bot_accounts.py)."""
    import net_common
    net_common.run_server_dir = str(save_dir)
    from base_classes import Gender, Guild, PlayerClass
    from flags import PlayerFlags
    from player import Player

    cast = [
        ('botleader',  Guild.CLAW,     False),
        ('botfollow',  Guild.CLAW,     True),
        ('botcarried', Guild.CLAW,     True),
        ('botrival',   Guild.FIST,     True),
        ('botwatch',   Guild.CIVILIAN, False),
    ]
    (save_dir / 'net').mkdir(parents=True, exist_ok=True)
    for name, guild, follow in cast:
        player = Player(id=name, name=name, char_class=PlayerClass.FIGHTER,
                        gender=Gender.MALE, map_level=1, map_room=START,
                        guild=guild)
        player.creation_done = True
        player.hit_points = 500          # survive any stray encounter
        if follow:
            player.set_flag(PlayerFlags.GUILD_FOLLOW_MODE)
        player.unsaved_changes = True
        if not player.save(force=True):
            raise RuntimeError(f'could not save {name}')
        (save_dir / 'net' / f'login-{name}.json').write_text(
            json.dumps({'password': net_common.hash_password(PASSWORD)}))


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
# One connection
# ---------------------------------------------------------------------------

class Bot:
    def __init__(self, name: str):
        self.name = name
        self.reader = self.writer = None
        self.last_prompt = ''
        self.lines: list[str] = []      # every line received, in order
        self.closed = False

    async def connect(self, port: int) -> None:
        self.reader, self.writer = await asyncio.open_connection('127.0.0.1', port)
        init = await self.recv(timeout=5)
        await self._send({'server_id': init.get('server_id', 'test_server'),
                          'server_key': init.get('server_key', 'test_key')})
        # Terminal type, then the pre-login banner -- which pages ("-- More
        # [1/2] ... -->", then "-- End [2/2] ... -->", PR #29), so answer
        # those with a bare RETURN.
        for _ in range(60):
            if self.last_prompt.rstrip().endswith('login>'):
                break
            if await self.recv(timeout=5) is None:
                raise RuntimeError(f'{self.name}: no login prompt (last {self.last_prompt!r})')
            low = self.last_prompt.lower()
            if 'terminal type' in low:              # plain text: no ANSI
                await self._send({'lines': ['P'], 'mode': 'login'})  # codes in the lines
            elif '-- more' in low or '-- end' in low:   # last page is "-- End [2/2]"
                await self._send({'lines': [''], 'mode': 'login'})
        else:
            raise RuntimeError(f'{self.name}: no login prompt (last {self.last_prompt!r})')
        await self.say(f'connect {self.name} {PASSWORD}')
        # The login banner/welcome can page; answer anything that isn't
        # the main prompt with a bare RETURN until we get there.
        for _ in range(40):
            msg = await self.recv(timeout=5)
            if msg is None:
                raise RuntimeError(f'{self.name}: login stalled at {self.last_prompt!r}')
            if self.at_main():
                return
            if msg.get('prompt'):
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
            self.closed = True
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
        return msg

    def at_main(self) -> bool:
        # The main prompt carries a "[HH:MM] " timestamp (bot_horse_journey.py).
        return self.last_prompt.rstrip().endswith('main>')

    async def until_main(self, *, answer=None, max_msgs: int = 200) -> bool:
        """Read until the main prompt; `answer(bot)` may return a reply for
        any other prompt on the way (None = keep reading)."""
        for _ in range(max_msgs):
            if await self.recv(timeout=6) is None:
                return False
            if self.at_main():
                return True
            if answer and self.last_prompt:
                reply = answer(self)
                if reply is not None:
                    await self.say(reply)
        return False

    async def settle(self, quiet: float = 1.5) -> list[str]:
        """Collect whatever arrives until the connection goes quiet; returns
        just the new lines."""
        start = len(self.lines)
        while await self.recv(timeout=quiet) is not None:
            pass
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
    """The server wraps text to the terminal width (about 40 columns here),
    so a message can span several lines: search them as one string."""
    return ' '.join(' '.join(lines).split())


def has(lines, text: str) -> bool:
    return text in joined(lines)


def index_of(lines, text: str) -> int:
    """Position of `text` in the joined lines (-1 if absent) -- comparable
    between two calls on the same lines, for checking order."""
    return joined(lines).find(text)


async def move(bot: Bot, direction: str, others: list[Bot]) -> dict[str, list[str]]:
    """Move `bot`, then gather what everyone else saw."""
    for o in others:
        await o.settle(0.3)                 # drop anything older
    marks = {o.name: len(o.lines) for o in others}
    await bot.say(direction)
    await bot.until_main()
    seen = {}
    for o in others:
        await o.settle()
        seen[o.name] = o.lines[marks[o.name]:]
    return seen


async def scenario(port: int, save_dir: Path) -> None:
    watch, rival, follow, leader = (Bot(n) for n in ('botwatch', 'botrival', 'botfollow', 'botleader'))
    everyone = [watch, rival, follow, leader]
    for b in everyone:
        log(f'\n== {b.name} logs in')
        await b.connect(port)
    for b in everyone:
        await b.settle(0.5)

    # A -- FOLLOW ME
    log('\n== A: botleader says FOLLOW ME')
    mark = len(leader.lines)
    await leader.say('follow me')
    # The prompt carries a "[HH:MM] " timestamp, so look for "take " inside it.
    await leader.until_main(answer=lambda b: 'Y' if 'take ' in b.last_prompt.lower() else None)
    said = leader.lines[mark:]
    follow_saw = await follow.settle()
    check('A FOLLOW ME: other guild and civilian stare, both Claw members agree, '
          'the live follower falls in',
          has(said, "botrival stares at you") and has(said, "botwatch stares at you")
          and has(said, 'botfollow agrees to follow you') and has(said, 'botcarried agrees to follow you')
          and has(follow_saw, 'botleader leads the way'),
          ' | '.join(said))

    # botrival goes ahead to watch the leader arrive in room 42
    log(f'\n== botrival walks {FIRST_DIR} to room {MIDDLE}')
    await move(rival, FIRST_DIR, [watch, follow, leader])

    # B/C -- the group moves twice
    group = 'botfollow and botcarried'
    for label, way, came_from in (('B', FIRST_DIR, 'west'), ('C', SECOND_DIR, 'north')):
        log(f'\n== {label}: botleader moves {way} with the group')
        mark = len(leader.lines)
        seen = await move(leader, way, [watch, rival, follow])
        said = leader.lines[mark:]
        in_left = watch if label == 'B' else rival
        in_reached = rival if label == 'B' else None
        f = seen['botfollow']
        ok = (has(said, f'You leave {way}, with {group} following.')
              and has(seen[in_left.name], f'botleader leaves {way}, with {group} following.')
              and has(f, f'You follow botleader {way}.')
              and not has(f, 'botleader leaves') and not has(f, 'botleader arrives')
              and not has(f, 'botleader enters')
              # "botleader is here." / "botrival and botleader are here."
              and (has(f, 'botleader is here') or has(f, 'botleader are here')))
        if in_reached is not None:
            ok = ok and has(seen[in_reached.name],
                            f'botleader arrives from the {came_from}, with {group} following.')
        check(f'{label} one line per room for the whole group; the follower only '
              f'"follows", then sees the leader there', ok,
              f"leader: {joined(said)[:90]!r} | follower: {joined(f)[:120]!r}")

    # D -- STAY
    log('\n== D: botleader says STAY')
    mark = len(leader.lines)
    await leader.say('stay')
    await leader.until_main()
    said = leader.lines[mark:]
    follow_saw = await follow.settle()
    check('D STAY: both followers stay, the live one is told to',
          has(said, 'Dropping off followers.') and has(said, 'botfollow stays here.')
          and has(said, 'botcarried stays here.')
          and has(follow_saw, 'botleader tells you to stay here.'),
          ' | '.join(said))

    # E -- the leader moves on alone
    log(f'\n== E: botleader moves {BACK_DIR} alone')
    seen = await move(leader, BACK_DIR, [watch, rival, follow])
    check('E the leader moves on without the follower',
          not has(seen['botfollow'], 'You follow botleader')
          and has(seen['botfollow'], f'botleader moves {BACK_DIR}.')
          and has(seen['botrival'], 'botleader enters from the south.'))

    # F -- the live follower was left in room 54
    log('\n== F: everyone logs out')
    for b in (follow, leader, rival, watch):
        await b.quit()
    await asyncio.sleep(1)
    check(f'F the live follower was saved in room {STAY_ROOM}',
          saved(save_dir, 'botfollow').get('map_room') == STAY_ROOM,
          f"map_room={saved(save_dir, 'botfollow').get('map_room')}")

    # G -- the offline follower
    data = saved(save_dir, 'botcarried')
    moved = data.get('map_room') == STAY_ROOM and data.get('followed_leader_name') == 'botleader'
    log('\n== G: botcarried logs in')
    carried = Bot('botcarried')
    await carried.connect(port)
    await carried.settle(1.0)
    told = has(carried.lines, 'You followed botleader to your current location.')
    await carried.quit()
    await asyncio.sleep(1)
    cleared = not saved(save_dir, 'botcarried').get('followed_leader_name')
    check(f'G the offline follower was dropped in room {STAY_ROOM}, told at login, '
          f'and the note cleared after',
          moved and told and cleared,
          f"map_room={data.get('map_room')} followed_leader_name={data.get('followed_leader_name')!r} "
          f'told={told} cleared={cleared}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Live FOLLOW ME / STAY check')
    parser.add_argument('--port', type=int, default=34192)
    parser.add_argument('--keep-dir', action='store_true',
                        help="keep the temporary save directory (and log) afterwards")
    args = parser.parse_args()

    save_dir = Path(tempfile.mkdtemp(prefix='tada-follow-me-'))
    seed_accounts(save_dir)
    server = start_server(save_dir, args.port)
    try:
        asyncio.run(scenario(args.port, save_dir))
    finally:
        server.terminate()
        server.wait(timeout=10)
        (save_dir / 'bot_follow_me.log').write_text('\n'.join(transcript) + '\n')
        if args.keep_dir:
            print(f'\nsave dir and log kept: {save_dir}')
        else:
            shutil.rmtree(save_dir, ignore_errors=True)

    print('\nall passed' if not failures else f'\n{len(failures)} failed')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
