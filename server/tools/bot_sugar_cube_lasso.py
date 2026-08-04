#!/usr/bin/env python3
"""bot_sugar_cube_lasso.py — Reactive live test of the sugar-cube lure ->
LASSO capture flow (wild_horse_events.try_sugar_cube_drop(), SPUR.MISC.S
"d.sugar") against a real running TADA server.

This is the flow the 8/4/26 session fixed: encounters/monster.py's
_try_spontaneous_charm() used to be eligible for the wild horse (#136,
size 'large' -> yy=2, never actually gated out by the yy=0 check), so a
horse lured into the grassy meadow by dropping a Sugar Cube could get
auto-"charmed" through the generic join-offer flow the moment a bot
walked back into its room -- joining as a broken plain ally (no MOUNT
flag, no breed/colour/hit_points seeding) instead of going through
LASSO/ally_events.capture_horse.py's real mount-capture path. This
script reproduces the exact user-facing sequence end to end against a
live server to confirm that's actually fixed, not just unit-tested.

Reuses tools/bot_horse_journey.py's Bot class and reactive
perceive/update-belief/decide pattern verbatim (see that module's
docstring for why) -- only the setup (getting a Sugar Cube via
EditPlayer, finding the grassy meadow, dropping until the horse takes
the bait) is new. The actual LASSO capture once the horse is in the
room reuses dummy_leader_loop()/lasso_capture_loop() unchanged.

Setup
-----
Run tools/setup_bot_accounts.py first (creates botdummy/botlasso).
Point this at a server instance you don't mind mutating, same caveat as
bot_horse_journey.py.

Usage
-----
    .venv/bin/python tools/bot_sugar_cube_lasso.py [--host HOST] [--port PORT]
"""
from __future__ import annotations

import asyncio
import argparse
from datetime import datetime
from pathlib import Path

import bot_horse_journey as hj
from bot_horse_journey import Bot, _log, _PASSWORD

HOST = hj.HOST
PORT = hj.PORT
WIDTH = hj.WIDTH
LOG_FILE = Path(__file__).resolve().parent.parent / f'bot_sugar_cube_lasso_{datetime.now().strftime("%Y-%m-%d_%H%M%S")}.log'

# Tiny Meadow, level 5 room 204 -- the only 'grassy'-flagged room in the
# map data (checked level_*.json for every room with 'grassy' in flags).
_GRASSY_LEVEL = 5
_GRASSY_ROOM  = 204

_MAX_SUGAR_CUBES = 6   # try_sugar_cube_drop is a 50% roll per cube


async def _drain(bot: Bot, stop, *, max_msgs: int = 600, timeout: float = 5.0) -> bool:
    """Like Bot.drain_until, but auto-dismisses '-- More --'/'-- End --'
    pagination prompts (unread board postings -- this is a shared live
    server, other real accounts post to the board independently of
    anything this script does) by sending a blank line, same technique
    as bot_cast_check.py/bot_text_editor_news.py use for the same
    prompt. Without this, a backlogged mailbox desyncs every drain_until
    call after it exactly like a wrong-field prompt check would."""
    for _ in range(max_msgs):
        msg = await bot._recv_one(timeout=timeout)
        if msg is None:
            return False
        low = bot.last_prompt.lower()
        if '-- more' in low or '-- end' in low:
            await bot.say('')
            continue
        if stop(bot):
            return True
    return False


async def _get_sugar_cube(bot: Bot, count: int = 1) -> None:
    """Grant *count* Sugar Cube rations to *bot* via EditPlayer's admin
    Inventory > Ration flow (self-service -- editplayer operates on the
    caller's own ctx.player, no target-picker step)."""
    await bot.say('editplayer')
    await _drain(bot, lambda b: 'choice>' in b.last_prompt.lower())

    await bot.say('in')
    await _drain(bot, lambda b: 'command>' in b.last_prompt.lower())

    for _ in range(count):
        await bot.say('r')
        await _drain(bot, lambda b: 'ration name' in b.last_prompt.lower())
        await bot.say('sugar')
        await _drain(bot, lambda b: 'give to' in b.last_prompt.lower())
        await bot.say('')   # blank -> give to yourself
        await _drain(bot, lambda b: 'command>' in b.last_prompt.lower())

    await bot.say('')   # back to top-level editplayer menu
    await _drain(bot, lambda b: 'choice>' in b.last_prompt.lower())
    await bot.say('')   # exit editplayer entirely
    await _drain(bot, lambda b: b.is_main_prompt())
    _log(f'  [{bot.label}] granted {count}x CUBE OF SUGAR via EditPlayer')


async def _lure_horse_with_sugar_cube(bot: Bot) -> bool:
    """Drop Sugar Cubes in the grassy meadow one at a time (50% chance
    each, wild_horse_events.try_sugar_cube_drop) until the wild horse
    actually shows up, or we run out of cubes. Returns True on success."""
    await bot.say(f'#{_GRASSY_LEVEL} {_GRASSY_ROOM}')
    await _drain(bot, lambda b: b.is_main_prompt())

    for attempt in range(1, _MAX_SUGAR_CUBES + 1):
        bot.monster_present = False
        await bot.say('drop sugar')
        await _drain(bot, lambda b: b.is_main_prompt())
        if bot.monster_present:
            _log(f'  [{bot.label}] *** horse lured after {attempt} sugar cube(s) ***')
            return True
        await bot.say('look')
        await _drain(bot, lambda b: b.is_main_prompt())
        if bot.monster_present:
            _log(f'  [{bot.label}] *** horse lured after {attempt} sugar cube(s) ***')
            return True

    return False


async def main(host: str, port: int) -> None:
    global hj
    hj._logfile = LOG_FILE.open('w', encoding='utf-8')
    _log(f'# bot_sugar_cube_lasso session  {datetime.now().isoformat(timespec="seconds")}')
    _log(f'# {host}:{port}')
    _log(f'\n\n{"#" * WIDTH}\n#  SUGAR CUBE LURE -> LASSO CAPTURE (live)\n{"#" * WIDTH}')

    dummy = Bot('botdummy', 'botdummy')
    lasso = Bot('botlasso', 'botlasso')
    if not await dummy.connect(host, port) or not await lasso.connect(host, port):
        return
    await dummy.say(f'connect {dummy.user} {_PASSWORD}')
    await _drain(dummy, lambda b: b.is_main_prompt())
    await lasso.say(f'connect {lasso.user} {_PASSWORD}')
    await _drain(lasso, lambda b: b.is_main_prompt())

    await _get_sugar_cube(dummy, _MAX_SUGAR_CUBES)

    lured = await _lure_horse_with_sugar_cube(dummy)
    if not lured:
        _log(f'\n  *** FAILED: horse never took the bait after {_MAX_SUGAR_CUBES} sugar cubes ***')
        await dummy.close()
        await lasso.close()
        return

    await lasso.say(f'#{_GRASSY_LEVEL} {_GRASSY_ROOM}')
    await _drain(lasso, lambda b: b.is_main_prompt())

    fight_started = asyncio.Event()
    may_stop = asyncio.Event()
    dummy_task = asyncio.create_task(hj.dummy_leader_loop(dummy, fight_started, may_stop))

    captured = await hj.lasso_capture_loop(lasso, fight_started)
    may_stop.set()
    try:
        await asyncio.wait_for(dummy_task, timeout=5)
    except asyncio.TimeoutError:
        _log('  [botdummy] leader loop did not wind down in time')

    _log(f'\n  [botlasso] *** capture {"SUCCEEDED" if captured else "FAILED"} ***')

    if captured:
        # lasso_capture_loop's drain_until stops as soon as mount_captured
        # flips True on the "STARDUST joins your party as a mount!" message
        # -- the separate prompt-only message that follows it is still
        # unread in the socket. Flush that leftover first, or the next
        # drain below reads it instead of the real reply to 'look stardust'.
        await _drain(lasso, lambda b: b.is_main_prompt())

        # Confirm it's a real MOUNT ally (breed/colour/gender line from
        # commands/look.py's _describe_ally, not a broken generic-ally
        # join) -- the whole point of excluding it from spontaneous charm.
        await lasso.say('look stardust')
        await _drain(lasso, lambda b: b.is_main_prompt())

    await dummy.close()
    await lasso.close()
    _log(f'\n{"=" * WIDTH}\n  Sugar-cube lasso test complete.\n{"=" * WIDTH}\n# log written to {LOG_FILE}')
    hj._logfile.close()
    print(f'Log saved to {LOG_FILE}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='TADA sugar-cube-lure + LASSO reactive bot test')
    parser.add_argument('--host', default=HOST)
    parser.add_argument('--port', type=int, default=PORT)
    args = parser.parse_args()
    asyncio.run(main(args.host, args.port))
