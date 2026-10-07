#!/usr/bin/env python3
"""tools/bot_read_prospecting.py — READ "Prospecting..." (objects.json #61)
on the running server and show the win-condition config beside it.

The book's text is generated from config.py's victory_type /
victory_silver_amount / victory_item_number (books.prospecting_text(),
PR #78), so this checks the live text against the live config.

botdummy (Admin) keeps the book once it has one. If it isn't carrying
it yet, it teleports to level 3 room 89 "Adventurer's Campsite", where
the book lies (a GRIZZLY BEAR is there too, but doesn't attack on
arrival), and GETs it. It never DROPs it back: taking a static map
item only hides it from that player for the session (item_history,
reset at login), so it's still there for everyone else and for this bot
next session, and a dropped copy just sits beside it as a duplicate
(server.room_items) -- the first version of this script did exactly
that. (LOOK and, since PR #80, GET also hide a static item from anyone
carrying one, so botdummy won't see the book in room 89 while it holds
a copy.) If the
GET lists several copies, it takes the last -- dropped items are listed
after the static one -- which cleans up any such leftover. Run against
the live server:

    .venv/bin/python3 tools/bot_read_prospecting.py
"""
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot_spells import Bot

HOST = '127.0.0.1'
PORT = 34083
BOOK_LEVEL, BOOK_ROOM = 3, 89


def _show(title: str, lines: list[str]) -> None:
    print(f'\n### {title}')
    for line in lines:
        print(line)


def _pick_last(bot) -> str | None:
    """GET's '(1-N, or Enter to cancel)' picker: take N, the last listed
    -- a player-dropped copy rather than the room's static one."""
    for line in reversed(bot.lines[-6:]):
        m = re.search(r'\(1-(\d+)', line)
        if m:
            return m.group(1)
    return None


async def main() -> int:
    bot = Bot('botdummy', 'puppy123')
    await bot.connect(HOST, PORT)
    try:
        # Bare CONFIG opens an interactive menu -- Enter quits it, else
        # every later command lands at its prompt as an 'Invalid choice'.
        config = await bot.run('config', answer=lambda b: '')
        _show('config (victory settings)', [l for l in config if 'Victory' in l])

        text = await bot.run('read prospecting')
        if any('not carrying' in l or 'no books' in l.lower() for l in text):
            await bot.run(f'teleport {BOOK_LEVEL} {BOOK_ROOM}')
            got = await bot.run('get prospecting', answer=_pick_last)
            _show('get prospecting', got)
            text = await bot.run('read prospecting')
        _show('read prospecting', text)
    finally:
        await bot.quit()
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
