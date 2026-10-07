#!/usr/bin/env python3
"""tools/bot_read_prospecting.py — READ "Prospecting..." (objects.json #61)
on the running server and show the win-condition config beside it.

The book's text is generated from config.py's victory_type /
victory_silver_amount / victory_item_number (books.prospecting_text(),
PR #78), so this checks the live text against the live config.

botdummy (Admin) teleports to level 3 room 89 "Adventurer's Campsite",
where the book lies (a GRIZZLY BEAR is there too, but doesn't attack on
arrival), GETs it, READs it, then DROPs it back so the room is left as
found. Run against the live server:

    .venv/bin/python3 tools/bot_read_prospecting.py
"""
import asyncio
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


async def main() -> int:
    bot = Bot('botdummy', 'puppy123')
    await bot.connect(HOST, PORT)
    try:
        # Bare CONFIG opens an interactive menu -- Enter quits it, else
        # every later command lands at its prompt as an 'Invalid choice'.
        config = await bot.run('config', answer=lambda b: '')
        _show('config (victory settings)', [l for l in config if 'Victory' in l])

        await bot.run(f'teleport {BOOK_LEVEL} {BOOK_ROOM}')
        got = await bot.run('get prospecting')
        _show('get prospecting', got)

        text = await bot.run('read prospecting')
        _show('read prospecting', text)

        dropped = await bot.run('drop prospecting')
        _show('drop prospecting', dropped)
    finally:
        await bot.quit()
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
