#!/usr/bin/env python3
"""bot_live_partner.py -- a bot to play the other side of HELPSTAFF for a
real player testing on the live server (written for railbender's
2026-10-06 session, after PR #72 went live).

Two roles:

  staff   Logs in (--staff, default botlasso), goes on helpstaff duty and
          stays there for --minutes. Whenever someone's request reaches it
          ("<name> needs help (<where>): <text>"), it types
          `helpstaff #accept <name>` -- which teleports it to them -- and
          says hello, quoting their question back, then waits for the next
          one. Goes off duty and logs out at the end (or on Ctrl-C).
          A tough monster in the bot's room can block the teleport (Freeze
          Adventurer); that's logged and the request reopens for others.

  ask     Logs in (--asker, default botswarm01), types `helpstaff #ask` and asks
          --question, so a real player on duty can practise #list /
          #accept / #decline. Waits up to --wait seconds for "... has
          arrived to help you." (or "... is here to help you."), reports
          who came, then logs out. If nobody was on duty the question is
          saved for a mailed answer -- left in the #queue unless --cancel.

Every setup_bot_accounts.py account is an Administrator, which is enough to
go on duty without the helpstaff membership flag (helpstaff/duty.py's
can_go_on_duty()). Passwords come from tools/bot_credentials.py. Nothing is
seeded; nothing is written except what the game itself saves.

The transcript goes to stdout and tools/bot_live_partner.log.

Usage:
    .venv/bin/python3 tools/bot_live_partner.py staff [--staff botlasso] [--minutes 45]
    .venv/bin/python3 tools/bot_live_partner.py ask [--asker botswarm01]
                      [--question "How do I cast a spell?"] [--wait 300] [--cancel]
    (both take --host 127.0.0.1 --port 34083)

Written 2026-10-06.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SERVER_DIR))
sys.path.insert(0, str(_SERVER_DIR / 'tools'))

import bot_spells                                   # noqa: E402  (shared Bot, transcript)
from bot_credentials import load_password           # noqa: E402
from bot_spells import Bot, bare_prompt, has, joined, log   # noqa: E402

_NEEDS_HELP = re.compile(r'(\S+) needs help \((.*?)\): (.*?)(?: Type helpstaff #accept|$)')


async def staff(args) -> None:
    bot = Bot(args.staff, load_password(args.staff))
    await bot.connect(args.host, args.port)
    await bot.settle(0.5)
    said = await bot.run('helpstaff #on')
    if not (has(said, 'You are now on helpstaff duty.') or has(said, 'already on')):
        log(f'!! {bot.name} could not go on duty: {joined(said)}')
    log(f'== {bot.name} on helpstaff duty for {args.minutes} minutes -- waiting for requests')

    deadline = time.time() + args.minutes * 60
    seen = len(bot.lines)
    helped = 0
    try:
        while time.time() < deadline:
            await bot.recv(timeout=5)
            new, seen = bot.lines[seen:], len(bot.lines)
            for match in _NEEDS_HELP.finditer(joined(new)):
                name, where, text = match.group(1), match.group(2), match.group(3).strip()
                if name == bot.name:
                    continue
                log(f'== request from {name} ({where}): {text!r}')
                said = await bot.run(f'helpstaff #accept {name}')
                seen = len(bot.lines)
                if has(said, 'Heading to'):
                    helped += 1
                    await bot.run(f'say Hi {name}! {bot.name} from helpstaff here -- a test '
                                  f'bot. I got your question: "{text}"')
                    seen = len(bot.lines)
                    log(f'== accepted {name}\'s request and said hello')
                elif has(said, "'Freeze Adventurer'"):
                    log(f'!! a monster froze {bot.name} in place -- the request reopens')
                else:
                    log(f'!! #accept {name} did not go through: {joined(said)}')
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        log(f'== time up: {helped} request(s) answered; going off duty')
        try:
            await bot.run('helpstaff #off')
            await bot.quit()
        except Exception as exc:                    # connection may already be gone
            log(f'   (logout: {exc})')


async def ask(args) -> None:
    bot = Bot(args.asker, load_password(args.asker))
    await bot.connect(args.host, args.port)
    await bot.settle(0.5)
    shown = joined(await bot.run('helpstaff #show'))
    log(f'== {bot.name} sees: {shown}')

    def _answer(b):
        return args.question if bare_prompt(b).startswith('what do you need help with') else None

    # Bot accounts are Admins, i.e. staff: a bare HELPSTAFF from staff only
    # shows a #show/#list reminder now, so ask with #ask.
    said = await bot.run('helpstaff #ask', answer=_answer)
    if has(said, 'Your question has been saved.'):
        log(f'== nobody on duty: {bot.name}\'s question was saved for a mailed answer')
        if args.cancel:
            await bot.run('helpstaff #cancel')
            log('   (withdrawn again: --cancel)')
        await bot.quit()
        return

    log(f'== asked {args.question!r} -- waiting up to {args.wait}s for someone to #accept')
    mark = len(bot.lines)
    deadline = time.time() + args.wait
    arrived = None
    while time.time() < deadline and arrived is None:
        await bot.recv(timeout=5)
        m = re.search(r'(\S+) (?:has arrived|is here) to help you\.', joined(bot.lines[mark:]))
        if m:
            arrived = m.group(1)
    if arrived:
        log(f'== {arrived} came to help {bot.name}')
        await bot.run(f'say Thanks {arrived}! That was the test -- all good.')
        await asyncio.sleep(2)
    else:
        log(f'== nobody accepted within {args.wait}s; withdrawing the request')
        await bot.run('helpstaff #cancel')
    await bot.quit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('role', choices=('staff', 'ask'))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=34083)
    parser.add_argument('--staff', default='botlasso')
    parser.add_argument('--minutes', type=float, default=45)
    parser.add_argument('--asker', default='botswarm01')
    parser.add_argument('--question', default='How do I cast a spell?')
    parser.add_argument('--wait', type=int, default=300)
    parser.add_argument('--cancel', action='store_true',
                        help='ask: withdraw a saved question if nobody was on duty')
    args = parser.parse_args()
    try:
        asyncio.run(staff(args) if args.role == 'staff' else ask(args))
    finally:
        (_SERVER_DIR / 'tools' / 'bot_live_partner.log').write_text(
            '\n'.join(bot_spells.transcript) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
