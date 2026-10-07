#!/usr/bin/env python3
"""bot_helpstaff.py -- live end-to-end check of HELPSTAFF (commands/
helpstaff.py and the helpstaff/ package): the login check-in, duty on/off,
#show, asking, the relay to staff, #list, #cancel, #accept's teleport and
[Helpstaff] tag, the disconnect cleanup in simple_server.py, and questions
saved while nobody is on duty being answered by mail (#queue, a saved FAQ
answer, the line editor) -- including the player's 'mail #reply'.

Two ways to run it:

  default    Self-contained, same as tools/bot_follow_me.py: seeds three
             throwaway characters into a fresh temporary save directory,
             starts its own tools/run_throwaway_server.py on it, runs the
             scenario over real sockets, then shuts the server down. Never
             touches run/server or the real server.

  --live     Connect to an already-running server (the live one, once it's
             running a build with HELPSTAFF) using existing bot accounts
             (default botdummy as staffer, botlasso as the player asking;
             passwords from tools/bot_credentials.py). Every
             setup_bot_accounts.py account is an Admin rather than a
             helpstaff member, so check C (a plain player can't go on duty)
             and the login check-in (Z, M) are skipped. The staffer is left
             off duty at the end; it does teleport to wherever the player
             asking happens to be standing, and botlasso gets a mailed
             answer.

Cast (throwaway mode, level 1):
  botstaff   helpstaff member (not an Admin), in room 41 -- goes on duty
             and answers
  botnewbie  plain player, in room 54 -- asks for help
  botwatch   plain player, in room 41 -- checks #show, tries #on

Rooms 41 and 54 are tools/bot_follow_me.py's: neutral and monster-free,
so the teleport can't be blocked by a Freeze Adventurer spell.

Checks:
  Z  login check-in: a member is asked "Go on helpstaff duty?" and Return
     leaves them off duty (throwaway mode only)
  A  #show with nobody on duty: "No one is on helpstaff duty"
  B  asking with nobody on duty saves the question for a mailed answer
  C  a plain player's #on is refused (throwaway mode only)
  D  #on: on duty, and told a saved question is waiting
  E  #show now lists the staffer
  F  asking: the "What do you need help with?" prompt (in msg['prompt'],
     see CLAUDE.md's bot notes) lists who's available; the staffer gets
     "<name> needs help (<where>): <text>" with the #accept/#decline hint;
     the player asking is told who it went to; the live request replaces
     the saved one
  G  #list shows the open request
  H  #cancel withdraws it, the staffer is told, #list is empty again
  I  #accept: the staffer is told it's heading over and lands in the
     player's room; the player sees "<staffer> [Helpstaff] appears in a
     flash of light." and "has arrived to help you", and LOOK lists
     "<staffer> [Helpstaff] is here."; a second #accept finds it no
     longer open. If a tough monster in the staffer's room blocks the
     teleport (Freeze Adventurer; seen in --live mode, where the staffer
     starts wherever its account was left, if it isn't an Admin/DM), I
     instead checks that the request reopened, skips the arrival checks,
     and cancels it.
  J  a request whose player disconnects is dropped from #list
  K  #off: off duty, #show is empty again, and (throwaway mode) the
     watcher's LOOK shows the staffer without the tag
  L  a question saved while the player is offline: #queue -> [F]AQ #2
     with a note mails it; the player's mailbox shows it from "<staffer>,
     Helpstaff member" with the question and the saved answer; their
     'mail #reply' reaches the staffer as a page
  M  (throwaway mode) the staffer logs back in, says Y to going on duty
     and Y to reviewing, answers with the line editor; the player (online)
     is told it was answered and the mail has the editor text
  N  (throwaway mode) the staffer's save still has the HELPSTAFF
     membership flag, and nothing on-duty was saved

Usage:
    .venv/bin/python tools/bot_helpstaff.py [--port 34194] [--keep-dir]
    .venv/bin/python tools/bot_helpstaff.py --live [--host HOST] [--port 34083]
                                            [--staff botdummy] [--newbie botlasso]

Written 2026-10-06.
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
sys.path.insert(0, str(_SERVER_DIR / 'tools'))

THROWAWAY_PASSWORD = 'helpstaff-bots'   # throwaway accounts in a throwaway dir
STAFF_ROOM, NEWBIE_ROOM = 41, 54
QUESTION = 'How do I find the bar?'

transcript: list[str] = []


def log(text: str = '') -> None:
    print(text)
    transcript.append(text)


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def seed_accounts(save_dir: Path) -> None:
    """Write the three characters straight into save_dir, bypassing the
    creation wizard (same approach as tools/setup_bot_accounts.py)."""
    import net_common
    net_common.run_server_dir = str(save_dir)
    from base_classes import Gender, PlayerClass
    from flags import PlayerFlags
    from player import Player

    cast = [
        ('botstaff',  STAFF_ROOM,  True),     # helpstaff member
        ('botnewbie', NEWBIE_ROOM, False),
        ('botwatch',  STAFF_ROOM,  False),
    ]
    (save_dir / 'net').mkdir(parents=True, exist_ok=True)
    for name, room, member in cast:
        player = Player(id=name, name=name, char_class=PlayerClass.FIGHTER,
                        gender=Gender.MALE, map_level=1, map_room=room)
        player.creation_done = True
        player.hit_points = 500          # survive any stray encounter
        if member:
            player.set_flag(PlayerFlags.HELPSTAFF)
        player.unsaved_changes = True
        if not player.save(force=True):
            raise RuntimeError(f'could not save {name}')
        (save_dir / 'net' / f'login-{name}.json').write_text(
            json.dumps({'password': net_common.hash_password(THROWAWAY_PASSWORD)}))


def saved(save_dir: Path, name: str) -> dict:
    return json.loads((save_dir / f'player-{name}.json').read_text())


def saved_flag(data: dict, flag_name: str) -> bool:
    entry = (data.get('flags') or {}).get(flag_name)
    if isinstance(entry, dict):
        return bool(entry.get('status'))
    return bool(entry)


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
# One connection (tools/bot_follow_me.py's Bot, with a per-bot password)
# ---------------------------------------------------------------------------

class Bot:
    def __init__(self, name: str, password: str):
        self.name = name
        self.password = password
        self.reader = self.writer = None
        self.last_prompt = ''
        self.prompts: list[str] = []    # every non-empty prompt received
        self.lines: list[str] = []      # every line received, in order
        self.closed = False

    async def connect(self, host: str, port: int, *, answer=None) -> None:
        """Log in. `answer(bot)` may return a reply for a prompt on the way
        in (e.g. the helpstaff login check-in); otherwise Return."""
        self.reader, self.writer = await asyncio.open_connection(host, port)
        self.closed = False
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
        log(f'  [{self.name}] -> connect {self.name} ****')
        await self._send({'lines': [f'connect {self.name} {self.password}'], 'mode': 'game'})
        # The login banner/welcome can page; answer anything that isn't
        # the main prompt with a bare RETURN until we get there (or with
        # whatever `answer` says, for prompts it recognizes).
        for _ in range(150):
            msg = await self.recv(timeout=6)
            if msg is None:
                raise RuntimeError(f'{self.name}: login stalled at {self.last_prompt!r}')
            if self.at_main():
                return
            if msg.get('prompt') and not self.at_marker():
                reply = answer(self) if answer else None
                await self.say(reply if reply is not None else '')
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
            self.prompts.append(self.last_prompt)
        return msg

    def at_marker(self) -> bool:
        """A bare 'main'/'login' prompt is the server announcing the input
        mode, not asking anything -- never answer it."""
        return self.last_prompt.strip() in ('main', 'login')

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
            if answer and self.last_prompt and not self.at_marker():
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

    async def run(self, line: str, *, answer=None) -> list[str]:
        """Send a command, read to the next main prompt, return its lines."""
        await self.settle(0.3)                  # drop anything older
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
    """The server wraps text to the terminal width, so a message can span
    several lines: search them as one string."""
    return ' '.join(' '.join(lines).split())


def has(lines, text: str) -> bool:
    return text in joined(lines)


def answer_question(text: str):
    """Reply to helpstaff's "What do you need help with?" prompt -- its
    text arrives in msg['prompt'], never in msg['lines']."""
    return lambda b: text if 'what do you need help with' in b.last_prompt.lower() else None


def by_prompt(**replies):
    """An `answer` callback replying by prompt text: by_prompt(duty='y')
    answers any prompt containing 'duty' with 'y'. Unmatched prompts get
    None (until_main keeps reading; connect sends Return)."""
    def _answer(bot):
        low = bot.last_prompt.lower()
        for needle, reply in replies.items():
            if needle.replace('_', ' ') in low:
                return reply
        return None
    return _answer


def in_order(*replies):
    """An `answer` callback giving `replies` one per prompt, in order --
    for a fixed walk like the #queue review and the line editor, whose
    line prompts all look alike."""
    pending = list(replies)
    def _answer(bot):
        low = bot.last_prompt.lower()
        if '-- more' in low or '-- end' in low:
            return ''
        return pending.pop(0) if pending else None
    return _answer


def newest_mail_number(lines) -> int | None:
    import re
    numbers = [int(m.group(1)) for line in lines
               for m in [re.match(r'^\s*(\d+)\.\s', line)] if m]
    return max(numbers) if numbers else None


async def ask(newbie: Bot, staff: Bot | None, text: str) -> tuple[list[str], list[str], list[str]]:
    """newbie types HELPSTAFF and answers the prompt with `text`; returns
    (newbie's lines, the prompts newbie saw, what staff received)."""
    if staff:
        await staff.settle(0.3)
    staff_mark = len(staff.lines) if staff else 0
    prompt_mark = len(newbie.prompts)
    said = await newbie.run('helpstaff', answer=answer_question(text))
    staff_saw = (await staff.settle()) if staff else []
    if staff:
        staff_saw = staff.lines[staff_mark:]
    return said, newbie.prompts[prompt_mark:], staff_saw


async def scenario(host: str, port: int, staff: Bot, newbie: Bot,
                   watch: Bot | None) -> None:
    everyone = [b for b in (staff, newbie, watch) if b]
    for b in everyone:
        log(f'\n== {b.name} logs in')
        mark = len(b.prompts)
        await b.connect(host, port)
        if b is staff and watch:
            asked = any('go on helpstaff duty' in p.lower() for p in b.prompts[mark:])
            check('Z login check-in asks a member to go on duty', asked,
                  repr(b.prompts[mark:][-4:]))
    for b in everyone:
        await b.settle(0.5)

    s, n = staff.name, newbie.name
    if watch:
        said = await watch.run('helpstaff #show')
        check('Z Return at the check-in leaves the member off duty',
              has(said, 'No one is on helpstaff duty'), joined(said))
    else:
        # Start from a known state: the live staffer may have been left on duty.
        await staff.run('helpstaff #off')
        await newbie.run('helpstaff #cancel')    # clears any saved question too

    log('\n== A: #show with nobody on duty')
    said = await newbie.run('helpstaff #show')
    check('A #show: nobody on duty', has(said, 'No one is on helpstaff duty'), joined(said))

    log('\n== B: asking with nobody on duty saves the question')
    said, prompts, _ = await ask(newbie, None, QUESTION)
    check('B asking with nobody on duty saves it for a mailed answer',
          any('what do you need help with' in p.lower() for p in prompts)
          and has(said, 'No one is on helpstaff duty right now')
          and has(said, 'Your question has been saved.'),
          joined(said))

    if watch:
        log('\n== C: a plain player tries #on')
        said = await watch.run('helpstaff #on')
        check('C a plain player cannot go on duty',
              has(said, 'Only helpstaff members, Admins and Dungeon Masters '
                        'can go on helpstaff duty.'), joined(said))
    else:
        log('\n== C: skipped (--live: every bot account is an Admin)')

    log('\n== D: the staffer goes on duty')
    said = await staff.run('helpstaff #on')
    check('D #on: on duty, told a saved question is waiting',
          has(said, 'You are now on helpstaff duty.')
          and has(said, 'saved question waiting'), joined(said))

    log('\n== E: #show lists the staffer')
    said = await newbie.run('helpstaff #show')
    check('E #show lists the staffer', has(said, f'On helpstaff duty: {s}'), joined(said))

    log('\n== F: asking for help')
    said, prompts, staff_saw = await ask(newbie, staff, QUESTION)
    check('F the question prompt was shown and answered',
          any('what do you need help with' in p.lower() for p in prompts)
          and has(said, f'Available to help: {s}'),
          f'prompts={prompts!r} | {joined(said)[:120]!r}')
    check('F the player is told who it went to',
          has(said, f'Your request has been sent to {s}.'), joined(said))
    check('F the staffer gets the request with the #accept/#decline hint',
          has(staff_saw, f'{n} needs help (') and has(staff_saw, QUESTION)
          and has(staff_saw, f'helpstaff #accept {n}')
          and has(staff_saw, f'helpstaff #decline {n}'),
          joined(staff_saw))

    log('\n== G: #list')
    said = await staff.run('helpstaff #list')
    check('G #list shows the open request (the live one replaced the saved one)',
          has(said, 'Open requests for help:') and has(said, f'{n} (') and has(said, QUESTION)
          and not has(said, 'saved question'),
          joined(said))

    log('\n== H: #cancel')
    await staff.settle(0.3)
    staff_mark = len(staff.lines)
    said = await newbie.run('helpstaff #cancel')
    staff_saw = await staff.settle()
    staff_saw = staff.lines[staff_mark:]
    listed = await staff.run('helpstaff #list')
    check('H #cancel withdraws it, the staffer is told, #list is empty',
          has(said, 'Your request for help has been withdrawn.')
          and has(staff_saw, f'{n} has withdrawn their request for help.')
          and has(listed, 'No open requests for help.'),
          f'{joined(said)!r} | staff: {joined(staff_saw)!r} | list: {joined(listed)!r}')

    log('\n== I: ask again, then #accept')
    await ask(newbie, staff, 'Can you show me around?')
    await newbie.settle(0.3)
    newbie_mark = len(newbie.lines)
    said = await staff.run(f'helpstaff #accept {n}')
    newbie_saw = await newbie.settle()
    newbie_saw = newbie.lines[newbie_mark:]
    if has(said, 'The teleport is blocked!'):
        # --live: the staffer starts wherever its account was left, which
        # can be next to a tough monster that casts Freeze Adventurer.
        check('I teleport blocked by a monster in the staffer\'s room: the request reopens',
              has(said, f"{n}'s request is still open.")
              and not has(newbie_saw, 'has arrived to help you'),
              joined(said))
        log('      (arrival checks skipped: move the staffer away from that monster to run them)')
        await newbie.run('helpstaff #cancel')
    else:
        check('I the staffer heads over and appears',
              has(said, f'Heading to {n} (Can you show me around?).')
              and (has(said, 'You appear in a flash of light.')
                   or has(said, "You're already with")),
              joined(said)[:200])
        check('I the player sees the staffer arrive, tagged [Helpstaff]',
              (has(newbie_saw, f'{s} has arrived to help you.')
               and has(newbie_saw, f'{s} [Helpstaff] appears in a flash of light.'))
              or has(newbie_saw, f'{s} is here to help you.'),
              joined(newbie_saw))
        seen = await newbie.run('look')
        check('I the player\'s LOOK lists the staffer as [Helpstaff]',
              has(seen, f'{s} [Helpstaff] is here') or has(seen, f'{s} [Helpstaff] are here')
              or has(seen, f'{s} [Helpstaff],') or has(seen, f'{s} [Helpstaff] and'),
              joined(seen)[:200])
        again = await staff.run(f'helpstaff #accept {n}')
        check('I a second #accept finds it no longer open',
              has(again, 'That request is no longer open.'), joined(again))
        here = await staff.run('look')
        check('I the staffer is standing with the player',
              has(here, n), joined(here)[:200])

    log('\n== J: a request whose player disconnects is dropped')
    await ask(newbie, staff, 'One more thing...')
    await newbie.quit()
    await asyncio.sleep(1)
    listed = await staff.run('helpstaff #list')
    check('J the disconnected player\'s request is gone',
          has(listed, 'No open requests for help.'), joined(listed))

    log('\n== K: #off')
    said = await staff.run('helpstaff #off')
    observer = watch or staff
    shown = await observer.run('helpstaff #show')
    check('K #off: off duty, #show is empty again',
          has(said, 'You are now off helpstaff duty.')
          and has(shown, 'No one is on helpstaff duty'),
          f'{joined(said)!r} | {joined(shown)!r}')
    if watch:
        # Get the staffer into botwatch's room (41) the helpstaff way:
        # back on duty, botwatch asks, the staffer accepts, then goes off
        # duty before botwatch LOOKs.
        await staff.run('helpstaff #on')
        await ask(watch, staff, 'Over here!')
        await staff.run(f'helpstaff #accept {watch.name}')
        await staff.run('helpstaff #off')
        seen = await watch.run('look')
        check('K once off duty, the staffer shows without the tag',
              has(seen, s) and not has(seen, '[Helpstaff]'), joined(seen)[:200])

    log('\n== L: a saved question answered by mail with a FAQ answer')
    await newbie.connect(host, port)
    await newbie.settle(0.5)
    await ask(newbie, None, 'I keep starving. What do I do?')
    await newbie.quit()
    await asyncio.sleep(1)
    said = await staff.run('helpstaff #queue', answer=in_order('f', '2', 'Good question!'))
    check('L #queue -> FAQ #2 with a note mails the answer',
          has(said, f'Question 1 of 1, from {n}') and has(said, f'Answer mailed to {n}.'),
          joined(said)[:240])
    await newbie.connect(host, port)
    await newbie.settle(0.5)
    listing = await newbie.run('mail', answer=lambda b: '')   # Return leaves the picker
    number = newest_mail_number(listing)
    msg_lines = await newbie.run(f'mail {number}', answer=lambda b: '') if number else []
    check('L the player\'s mail is from "<staffer>, Helpstaff member" with the '
          'question, note and saved answer',
          has(msg_lines, f'{s}, Helpstaff member') and has(msg_lines, 'I keep starving.')
          and has(msg_lines, 'Good question!') and has(msg_lines, 'needs food and water'),
          joined(msg_lines)[:300])
    await staff.settle(0.3)
    staff_mark = len(staff.lines)
    await newbie.run(f'mail #reply {number}=Thanks, that worked!')
    await staff.settle()
    check('L the player\'s mail #reply reaches the staffer',
          has(staff.lines[staff_mark:], 'Thanks, that worked!'),
          joined(staff.lines[staff_mark:]))

    if watch:
        log('\n== M: login check-in -> on duty -> review -> answer in the editor')
        await ask(newbie, None, 'Where can I buy a sword?')
        await staff.quit()
        await asyncio.sleep(1)
        await newbie.settle(0.3)
        newbie_mark = len(newbie.lines)
        staff_mark = len(staff.lines)
        flow = in_order('y', 'y', 'a', 'Try the weapon shop in town.', '.s')
        await staff.connect(host, port, answer=flow)
        await staff.settle(1.0)
        said = staff.lines[staff_mark:]
        await newbie.settle()
        check('M the check-in put the member on duty and the editor answer was mailed',
              has(said, 'You are now on helpstaff duty.')
              and has(said, f'Answer mailed to {n}.') and has(said, 'That was the last question.'),
              joined(said)[-300:])
        check('M the player, online, is told it was answered',
              has(newbie.lines[newbie_mark:], f'{s} answered your help request.'),
              joined(newbie.lines[newbie_mark:]))
        listing = await newbie.run('mail', answer=lambda b: '')   # Return leaves the picker
        number = newest_mail_number(listing)
        msg_lines = await newbie.run(f'mail {number}', answer=lambda b: '') if number else []
        check('M the mail has the editor text',
              has(msg_lines, 'Where can I buy a sword?')
              and has(msg_lines, 'Try the weapon shop in town.'), joined(msg_lines)[:300])
        await staff.run('helpstaff #off')

    for b in (staff, newbie, watch):
        if b and not b.closed:
            await b.quit()
    await asyncio.sleep(1)


def main() -> int:
    parser = argparse.ArgumentParser(description='Live HELPSTAFF check')
    parser.add_argument('--live', action='store_true',
                        help='connect to an already-running server instead of '
                             'starting a throwaway one')
    parser.add_argument('--host', default='127.0.0.1', help='(--live) server host')
    parser.add_argument('--port', type=int, default=None,
                        help='server port (default 34194 throwaway, 34083 --live)')
    parser.add_argument('--staff', default='botdummy', help='(--live) staffer account')
    parser.add_argument('--newbie', default='botlasso', help='(--live) account asking for help')
    parser.add_argument('--keep-dir', action='store_true',
                        help="keep the temporary save directory (and log) afterwards")
    args = parser.parse_args()

    if args.live:
        from bot_credentials import load_password
        port = args.port or 34083
        staff = Bot(args.staff, load_password(args.staff))
        newbie = Bot(args.newbie, load_password(args.newbie))
        asyncio.run(scenario(args.host, port, staff, newbie, None))
        log_path = _SERVER_DIR / 'tools' / 'bot_helpstaff.log'
        log_path.write_text('\n'.join(transcript) + '\n')
        print(f'\nlog: {log_path}')
    else:
        port = args.port or 34194
        save_dir = Path(tempfile.mkdtemp(prefix='tada-helpstaff-'))
        seed_accounts(save_dir)
        server = start_server(save_dir, port)
        try:
            asyncio.run(scenario('127.0.0.1', port,
                                 Bot('botstaff', THROWAWAY_PASSWORD),
                                 Bot('botnewbie', THROWAWAY_PASSWORD),
                                 Bot('botwatch', THROWAWAY_PASSWORD)))
        finally:
            server.terminate()
            server.wait(timeout=10)
        data = saved(save_dir, 'botstaff')
        check(f'N the staffer\'s save keeps HELPSTAFF membership, no on-duty state, '
              f'room {STAFF_ROOM}',
              saved_flag(data, 'Helpstaff') and 'helpstaff_on_duty' not in data
              and data.get('map_room') == STAFF_ROOM,
              f"Helpstaff={saved_flag(data, 'Helpstaff')} map_room={data.get('map_room')}")
        (save_dir / 'bot_helpstaff.log').write_text('\n'.join(transcript) + '\n')
        if args.keep_dir:
            print(f'\nsave dir and log kept: {save_dir}')
        else:
            shutil.rmtree(save_dir, ignore_errors=True)

    print('\nall passed' if not failures else f'\n{len(failures)} failed: {failures}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
