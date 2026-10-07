"""books.py — SPUR book-text emulation (server/books.json).

`SPUR-data/SPUR.BOOKS.TXT` is a GBBS Pro message-base file (see
`tools/gbbsmsgtool.py`) holding the flavor text shown when a player READs
a book item. SPUR's own `read` subroutine (SPUR.MISC2.S:285) looks this up
by message number, keyed to the book's own item number (`bk$=dx$+
"spur.books":gosub read.bk`, `input #msg(a),n$` where `a` is the item's
number). `tools/gbbsmsgtool.py extract --pretty` recovered all 23 active
messages; each maps 1:1, in order, to the 23 book-type entries in
objects.json (confirmed by matching each recovered message's subject line
against the book's name -- e.g. message "SCROLL OF ANTI-MAGIC" ->
objects.json #88 "Scroll of Anti-Magic"). `server/books.json` stores that
mapping directly by item number, same shape as `server/messages.json`
({"N": ["paragraph", ...], ...}); this module loads and serves it the
same way.

One exception: item #61 "Prospecting..." is SPUR's hint book for the win
condition, and its recovered text hardcodes SPUR's default goal (5,000
gold, plus a nod to "a holy object"). Since config.py's victory_type/
victory_silver_amount/victory_item_number let the sysop change that goal,
get_book_text() builds #61's text from the live config instead (see
prospecting_text()), so the book never points players at a stale goal.
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from network_context import GameContext


def load_books(path: str) -> dict[int, list[str]]:
    """Load books.json into {item_number: [paragraph, ...]}."""
    try:
        with open(path) as f:
            data = json.load(f)
        logging.info("Loaded %d books from '%s'", len(data), path)
        return {int(k): v for k, v in data.items()}
    except FileNotFoundError:
        logging.warning("'%s' not found, book text unavailable.", path)
        return {}


PROSPECTING_ITEM_NUMBER = 61  # objects.json "Prospecting..."


def _victory_item_phrase(item_number: int) -> Optional[str]:
    """'the Holy Grail' / 'the sand dollar' for config.victory_item_number,
    or None if unset or no longer a victory-eligible treasure."""
    if not item_number:
        return None
    from item_system import victory_eligible_treasures
    from room_notices import the
    match = next((it for it in victory_eligible_treasures()
                  if it.number == item_number), None)
    return the(match.name.strip()) if match else None


def prospecting_text() -> list[str]:
    """Item #61's text, reflecting config.py's current win condition(s) --
    the same gates victory.py's evaluate_victory() actually checks
    (an item requirement with victory_item_number=0 is skipped there, so
    it's skipped here too)."""
    from config import config

    victory_type = config.victory_type
    wants_silver = victory_type in ('silver', 'both')
    item = _victory_item_phrase(config.victory_item_number) \
        if victory_type in ('item', 'both') else None

    lines = []
    if wants_silver:
        lines.append(
            "Be it known, that in older days, the sign of a true WEALTHY "
            "adventurer was the accumulation of "
            f"{config.victory_silver_amount:,} silver pieces...  It is said "
            "that without at least this amount of silver, one could not "
            "leave the LAND!")
    if item and wants_silver:
        lines.append(
            f"Be also aware: riches alone will not suffice. Without {item} "
            "in hand as well, none may pass!")
    elif item:
        lines.append(
            "Be it known, that in older days, the sign of a true adventurer "
            f"was not wealth, but the recovery of {item}...  It is said "
            "that without it, one could not leave the LAND!")
    if not lines:
        lines.append(
            "Be it known, that in these days neither riches nor relics "
            "will bar thy way...  It is said that any who slay the King of "
            "the Wraiths may leave the LAND!")
    return lines


def get_book_text(ctx: 'GameContext', item_number: int) -> Optional[list[str]]:
    """Return item_number's recovered book text from ctx.server.books, or None.

    #61 "Prospecting..." is generated from the current win-condition
    config instead (prospecting_text()) -- see module docstring."""
    if item_number == PROSPECTING_ITEM_NUMBER:
        return prospecting_text()
    books = getattr(ctx.server, 'books', None) or {}
    return books.get(item_number)
